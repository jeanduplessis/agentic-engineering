import assert from "node:assert/strict";
import { watch } from "node:fs";
import { access, mkdtemp, readFile, realpath, rm, stat } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { graphStatus, OUTPUT_BYTES, queryGraph, runProcess } from "../cli.ts";
import { loadGraphExtension, sdkPath } from "./sdk.mjs";

const searchResponse = {
	results: [{ file_path: "src/routes.ts", start_line: 4, end_line: 8, snippet: "export function route() {}" }],
	stats: { index_cache_hit: false },
	warnings: [{ code: "W_WORKTREE_SNAPSHOT" }], partial_failures: [],
	completeness: { languages: { TypeScript: { files: 1, symbols: 1 } }, relations: { CALLS: 1 } },
};
const impactResponse = {
	commit: "fixture-commit", tree: "fixture-tree",
	focus_matches_total: 2, disambiguation_required: true,
	definitions: [{ file_path: "src/routes.ts", name: "route" }, { file_path: "src/other.ts", name: "route" }],
	callers: { total: 0, entries: [] }, index_cache_hit: true,
	stats: { completeness_level: "degraded" },
	warnings: [{ code: "W_FILE_LIMIT", detail: "Not every file was indexed" }],
	partial_failures: [{ code: "E_PARSE_ERROR", file_path: "src/broken.ts" }],
};

function resultData(result) { return JSON.parse(result.content[0].text); }

async function directory(t) {
	const root = await mkdtemp(join(tmpdir(), "graph-test-"));
	t.after(() => rm(root, { recursive: true, force: true }));
	return root;
}

test("search uses argv, an explicit repository and working-tree/full defaults; replay state is not inherited", async () => {
	const env = {
		PATH: process.env.PATH, ENTIRE_GRAPH_PRESEARCH: "private-payload", EG_PRESEARCH: "alias-payload",
		EG_SEARCH_SESSION: "previous-session", EG_MAX_SEARCHES: "1", ENTIRE_REPO_ROOT: "/wrong/repository",
		ENTIRE_GRAPH_REFERENCE_BLOCKS: "all", ENTIRE_GRAPH_MAX_FILES: "500",
	};
	const original = { ...env };
	const query = 'route matching; $(touch SHOULD_NOT_EXIST) "quoted"';
	let called = false;
	const result = await queryGraph("search", { query }, process.cwd(), undefined, { env, run: async (command, args, options) => {
		called = true;
		assert.equal(command, "entire");
		assert.deepEqual(args, ["graph", "search", "--repo", process.cwd(), "--format", "json", "--profile", "full",
			"--query", query, "--top-k", "5", "--max-context-bytes", "12000"]);
		assert.equal(options.cwd, process.cwd());
		assert.deepEqual(options.env, { PATH: process.env.PATH, ENTIRE_GRAPH_MAX_FILES: "500" });
		return JSON.stringify(searchResponse);
	} });
	assert.equal(called, true);
	assert.deepEqual(env, original);
	assert.deepEqual(resultData(result).response, searchResponse);
	assert.equal(result.details.requestedView, "worktree");
	assert.equal(result.details.cacheHit, false);
});

test("standalone impact supports explicit HEAD and disambiguation without losing coverage or unknown fields", async () => {
	const binary = join(tmpdir(), "graph binary");
	const response = { ...impactResponse, future_additive_field: { useful: true } };
	const result = await queryGraph("impact", { symbol: "route", file: "src/routes.ts", head: true, depth: 1, limit: 3 },
		process.cwd(), undefined, { env: { PI_ENTIRE_GRAPH_BIN: binary }, run: async (command, args) => {
			assert.equal(command, binary);
			assert.deepEqual(args, ["impact", "--repo", process.cwd(), "--format", "json", "--profile", "full", "--head",
				"--symbol", "route", "--depth", "1", "--limit", "3", "--file", "src/routes.ts"]);
			return JSON.stringify(response);
		} });
	assert.deepEqual(resultData(result).response, response);
	assert.equal(resultData(result).diagnostics.partial_failures, 1);
	assert.deepEqual(resultData(result).diagnostics.warning_codes, ["W_FILE_LIMIT"]);
	assert.equal(result.details.cacheHit, true);
	assert.equal(result.details.requestedView, "head");
});

test("configuration and invalid responses fail explicitly rather than masquerading as empty results", async () => {
	await assert.rejects(queryGraph("search", { query: "test" }, process.cwd(), undefined, {
		env: { PI_ENTIRE_GRAPH_BIN: "./untrusted-binary --flag" }, run: () => assert.fail("Must not spawn"),
	}), /absolute standalone binary path/);
	for (const output of ["SECRET malformed output", "[]", '{"error":"failure"}']) {
		await assert.rejects(queryGraph("search", { query: "test" }, process.cwd(), undefined, {
			run: async () => output,
		}), (error) => /JSON|shape/.test(error.message) && !error.message.includes("SECRET"));
	}
	await assert.rejects(queryGraph("impact", { symbol: "test" }, process.cwd(), undefined, {
		run: async () => JSON.stringify(searchResponse),
	}), /shape/);
	const empty = await queryGraph("search", { query: "missing" }, process.cwd(), undefined, {
		run: async () => '{"results":null}',
	});
	assert.equal(resultData(empty).response.results, null);
});

test("explicit HEAD queries reject upstream working-tree fallback, including mixed provenance", async () => {
	for (const response of [searchResponse, { ...searchResponse, commit: "commit", tree: "tree" }]) {
		await assert.rejects(queryGraph("search", { query: "test", head: true }, process.cwd(), undefined, {
			env: {}, run: async () => JSON.stringify(response),
		}), /committed HEAD view/);
	}
});

test("large results stay bounded, expose diagnostic counts, and preserve full UTF-8 output in a private file", async (t) => {
	const response = { ...searchResponse, results: [{ snippet: "世界".repeat(20_000) }],
		warnings: impactResponse.warnings, partial_failures: impactResponse.partial_failures };
	const result = await queryGraph("search", { query: "test" }, process.cwd(), undefined, {
		run: async () => JSON.stringify(response),
	});
	const { fullOutputPath } = result.details;
	t.after(() => rm(dirname(fullOutputPath), { recursive: true, force: true }));
	assert.equal(result.details.truncated, true);
	assert.ok(Buffer.byteLength(result.content[0].text) <= OUTPUT_BYTES);
	assert.ok(result.content[0].text.split("\n").length <= 1000);
	assert.ok(result.content[0].text.includes("W_FILE_LIMIT"));
	assert.ok(result.content[0].text.includes('"partial_failures":1'));
	assert.ok(!result.content[0].text.includes("\uFFFD"));
	assert.deepEqual(JSON.parse(await readFile(fullOutputPath, "utf8")).response, response);
	if (process.platform !== "win32") {
		assert.equal((await stat(fullOutputPath)).mode & 0o777, 0o600);
		assert.equal((await stat(dirname(fullOutputPath))).mode & 0o777, 0o700);
	}
});

test("line-heavy results are also bounded even below the byte limit", async (t) => {
	const response = { results: Array.from({ length: 500 }, () => ({ x: 1 })) };
	const result = await queryGraph("search", { query: "test" }, process.cwd(), undefined, { run: async () => JSON.stringify(response) });
	t.after(() => rm(dirname(result.details.fullOutputPath), { recursive: true, force: true }));
	assert.equal(result.details.truncated, true);
	assert.ok(result.content[0].text.split("\n").length <= 1000);
});

test("status checks version and capabilities without querying, installing, or initializing the repository", async () => {
	const calls = [];
	const status = await graphStatus(process.cwd(), { env: {}, run: async (_command, args) => {
		calls.push(args);
		return JSON.stringify(args.includes("version") ? { version: "spike-test" } : { semantic_languages: ["Go", "TypeScript"] });
	} });
	assert.deepEqual(calls, [["graph", "version", "--json"], ["graph", "capabilities", "--json"]]);
	assert.deepEqual(status, { version: "spike-test", semanticLanguages: 2 });
});

test("process execution keeps shell syntax literal and uses the requested cwd", async (t) => {
	const cwd = await directory(t);
	const argument = '$(touch sentinel); echo "not a command"';
	const output = await runProcess(process.execPath, ["-e", "console.log(JSON.stringify({args:process.argv.slice(1),cwd:process.cwd()}))", argument], { cwd });
	assert.deepEqual(JSON.parse(output), { args: [argument], cwd: await realpath(cwd) });
	await assert.rejects(access(join(cwd, "sentinel")));
});

test("missing executables and nonzero exits fail; stderr cannot inject terminal control sequences", async (t) => {
	const cwd = await directory(t);
	await assert.rejects(runProcess(join(cwd, "missing"), [], { cwd }), /Cannot start Entire Graph/);
	await assert.rejects(runProcess(process.execPath, ["-e", 'process.stdout.write("{}");process.stderr.write("\\x1b[31mBAD\\n");process.exit(2)'], { cwd }),
		(error) => /code 2/.test(error.message) && !error.message.includes("\x1b") && !error.message.includes("\n"));
});

test("timeouts, cancellation, and output limits terminate the query instead of returning partial JSON", async (t) => {
	const cwd = await directory(t);
	const waiting = ["-e", "setInterval(() => {}, 1000)"];
	await assert.rejects(runProcess(process.execPath, waiting, { cwd, timeoutMs: 150 }), /timed out/);
	await assert.rejects(runProcess(process.execPath, waiting, { cwd, signal: AbortSignal.timeout(150) }), /cancelled/);
	await assert.rejects(runProcess(process.execPath, ["-e", 'process.stdout.write("x".repeat(10000));setInterval(() => {}, 1000)'],
		{ cwd, maxBytes: 1024 }), /output limit/);
	await assert.rejects(runProcess(process.execPath, ["-e", 'process.stderr.write("x".repeat(10000));setInterval(() => {}, 1000)'],
		{ cwd, maxBytes: 1024 }), /output limit/);
	await assert.rejects(runProcess(process.execPath, ["-e", 'require("fs").writeFileSync("sentinel", "unexpected")'],
		{ cwd, signal: AbortSignal.abort() }), /cancelled/);
	await assert.rejects(access(join(cwd, "sentinel")));
});

test("source controls are escaped for display while JSON retains the original evidence", async () => {
	const response = { ...searchResponse, results: [{ snippet: "literal \u009b31m \u001b[31m source" }] };
	const result = await queryGraph("search", { query: "test" }, process.cwd(), undefined, {
		env: {}, run: async () => JSON.stringify(response),
	});
	assert.ok(!result.content[0].text.includes("\u009b"));
	assert.ok(!result.content[0].text.includes("\u001b"));
	assert.deepEqual(resultData(result).response, response);
});

test("POSIX cancellation also terminates spawned descendants", { skip: process.platform === "win32", timeout: 5000 }, async (t) => {
	const cwd = await directory(t);
	const controller = new AbortController();
	t.after(() => controller.abort());
	let watcher;
	const ready = new Promise((resolve) => {
		watcher = watch(cwd, (_event, name) => { if (name === "ready") resolve(); });
	});
	t.after(() => watcher.close());
	const descendant = 'setTimeout(() => require("fs").writeFileSync("survived", "unexpected"), 600)';
	const parent = `const {spawn}=require('child_process'); const fs=require('fs');
		spawn(process.execPath, ['-e', ${JSON.stringify(descendant)}], {stdio:'ignore'});
		fs.writeFileSync('ready.tmp','yes');fs.renameSync('ready.tmp','ready');setInterval(()=>{},1000);`;
	const rejected = assert.rejects(runProcess(process.execPath, ["-e", parent], { cwd, signal: controller.signal }), /cancelled/);
	await ready;
	controller.abort();
	await rejected;
	await delay(800);
	await assert.rejects(access(join(cwd, "survived")));
});

test("Pi's real loader registers exactly two tools and a status command with no background hooks", {
	skip: !sdkPath && "Pi SDK is not installed",
}, async () => {
	const loaded = await loadGraphExtension(process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	const extension = loaded.extensions[0];
	assert.deepEqual([...extension.tools.keys()], ["graph_search", "graph_impact"]);
	assert.deepEqual([...extension.commands.keys()], ["graph"]);
	assert.equal(extension.handlers.size, 0);
	const notifications = [];
	await extension.commands.get("graph").handler("invalid-action", {
		hasUI: true, ui: { notify(message, level) { notifications.push({ message, level }); } },
	});
	assert.equal(notifications[0].level, "error");
});
