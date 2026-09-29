import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { chmod, mkdir, mkdtemp, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolveScope, runProcess, searchCode, UnavailableError } from "../jg.ts";
import { createPolicy, HINT, TOOL } from "../policy.ts";

const result = { schemaVersion: 1, matches: [{ path: "src/a.ts", startLine: 1, endLine: 2, text: "x" }],
	coverage: { mode: "shortlist" }, truncated: false, omittedMatches: 0 };

async function repo(t) {
	const root = await realpath(await mkdtemp(join(tmpdir(), "code-search-")));
	t.after(() => rm(root, { recursive: true, force: true }));
	execFileSync("git", ["init", "-q"], { cwd: root });
	await mkdir(join(root, "src/deep"), { recursive: true });
	await mkdir(join(root, ".secrets"));
	await mkdir(join(root, "build"));
	await writeFile(join(root, ".gitignore"), "build/\n");
	await writeFile(join(root, "src/a.ts"), "export const a = 1;\n");
	return root;
}

/** Real git for scope checks; a recorded fake for jg. */
function fakeJg(reply) {
	const calls = [];
	const run = async (command, args, options) => {
		if (command === "git") return runProcess(command, args, options);
		calls.push({ command, args, options });
		return reply;
	};
	return { run, calls };
}

test("search passes the query literally after --, runs at the workspace root, and scopes to root-relative paths", async (t) => {
	const root = await repo(t);
	const jg = fakeJg({ code: 0, stdout: JSON.stringify(result), stderr: "" });
	const query = 'login $(touch SHOULD_NOT_EXIST) "quoted"';
	const out = await searchCode({ query, limit: 7, broad: true }, join(root, "src"), undefined, { run: jg.run, env: { PATH: process.env.PATH } });
	assert.equal(jg.calls.length, 1);
	assert.equal(jg.calls[0].command, "jg");
	assert.deepEqual(jg.calls[0].args, ["--json", "--limit", "7", "--broad", "--", query, "src"]);
	assert.equal(jg.calls[0].options.cwd, root);
	assert.equal(out.details.matches, 1);
	assert.ok(out.content[0].text.includes(JSON.stringify(root)));
	assert.deepEqual(JSON.parse(out.content[0].text.split("\n")[1]), result);
});

test("scope rejects paths outside the workspace, symlink escapes, hidden paths, ignored paths, and the home root", async (t) => {
	const root = await repo(t);
	const outside = await realpath(await mkdtemp(join(tmpdir(), "code-search-outside-")));
	t.after(() => rm(outside, { recursive: true, force: true }));
	await symlink(outside, join(root, "src/escape"));
	for (const [path, pattern] of [["..", /outside/], [outside, /outside/], ["src/escape", /outside/],
		[".secrets", /hidden/], ["build", /ignored/], ["missing", /does not exist/]]) {
		await assert.rejects(resolveScope(root, [path]), pattern, path);
	}
	assert.deepEqual((await resolveScope(root, ["src", "src/../src", "."])).paths, ["src", "."]);
	await assert.rejects(resolveScope(root, undefined, runProcess, root), /home or filesystem root/);
});

test("no-match exit is a normal result; login and binary failures are UnavailableError; bad output is not echoed", async (t) => {
	const root = await repo(t);
	const none = await searchCode({ query: "q" }, root, undefined,
		{ run: fakeJg({ code: 1, stdout: JSON.stringify({ ...result, matches: [] }), stderr: "" }).run });
	assert.match(none.content[0].text, /does not prove/);
	assert.equal(none.details.exitCode, 1);
	await assert.rejects(searchCode({ query: "q" }, root, undefined,
		{ run: fakeJg({ code: 2, stdout: "", stderr: "jg: Run jg login before searching" }).run }),
		(error) => error instanceof UnavailableError && /not logged in/.test(error.message));
	await assert.rejects(searchCode({ query: "q" }, root, undefined,
		{ run: fakeJg({ code: 2, stdout: "", stderr: "boom\x1b[31m" }).run }),
		(error) => !(error instanceof UnavailableError) && /code 2/.test(error.message) && !error.message.includes("\x1b"));
	await assert.rejects(searchCode({ query: "q" }, root, undefined,
		{ run: fakeJg({ code: 0, stdout: "SECRET not json", stderr: "" }).run }),
		(error) => /invalid JSON/.test(error.message) && !error.message.includes("SECRET"));
	await assert.rejects(searchCode({ query: "q" }, root, undefined,
		{ run: fakeJg({ code: 0, stdout: JSON.stringify({ schemaVersion: 2, matches: [] }), stderr: "" }).run }), /schema/);
	await assert.rejects(searchCode({ query: "q" }, root, undefined, { env: { PI_JG_BIN: "jg" } }), UnavailableError);
	await assert.rejects(searchCode({ query: "q" }, root, undefined, { env: { PATH: process.env.PATH, PI_JG_BIN: join(root, "no-such-jg") } }),
		(error) => error instanceof UnavailableError && /not installed/.test(error.message));
});

test("a real stub executable receives argv without a shell and closed stdin", { skip: process.platform === "win32" }, async (t) => {
	const root = await repo(t);
	const stub = join(root, "jg-stub.sh");
	await writeFile(stub, `#!/bin/sh\nif [ -t 0 ]; then exit 9; fi\nprintf '{"schemaVersion":1,"matches":[],"argv":"%s|%s"}' "$3" "$4"\nexit 1\n`);
	await chmod(stub, 0o755);
	const out = await searchCode({ query: "a; touch PWNED" }, root, undefined, { env: { PATH: process.env.PATH, PI_JG_BIN: stub } });
	assert.equal(out.details.exitCode, 1);
	assert.equal(JSON.parse(out.content[0].text.split("\n")[1]).argv, "a; touch PWNED|.");
});

function fakePi(active = ["read", "bash", TOOL]) {
	const handlers = new Map();
	return {
		on: (event, handler) => handlers.set(event, handler),
		getActiveTools: () => active,
		emit: (event, fields) => handlers.get(event)?.({ type: event, ...fields }),
	};
}
const bash = (command) => ({ toolName: "bash", input: { command }, content: [{ type: "text", text: "out" }] });

test("policy appends one hint to the first search per prompt and never blocks", () => {
	const pi = fakePi();
	createPolicy(pi);
	pi.emit("before_agent_start", {});
	assert.equal(pi.emit("tool_result", bash("ls -la")), undefined);
	const hinted = pi.emit("tool_result", bash("cd src && rg -n 'session'"));
	assert.deepEqual(hinted.content, [{ type: "text", text: "out" }, { type: "text", text: HINT }]);
	assert.equal(pi.emit("tool_result", { toolName: "grep", input: {}, content: [] }), undefined);
	pi.emit("before_agent_start", {});
	assert.ok(pi.emit("tool_result", { toolName: "find", input: {}, content: [] }));
});

test("policy stays silent after code_search or jg use, when unavailable, or when the tool is inactive", () => {
	const pi = fakePi();
	const policy = createPolicy(pi);
	policy.markUsed();
	assert.equal(pi.emit("tool_result", bash("rg foo")), undefined);
	pi.emit("before_agent_start", {});
	assert.equal(pi.emit("tool_result", bash("jg --json 'expired sessions' src")), undefined);
	assert.equal(pi.emit("tool_result", bash("rg foo")), undefined);
	pi.emit("before_agent_start", {});
	policy.markUnavailable("not logged in");
	assert.equal(pi.emit("tool_result", bash("rg foo")), undefined);
	const inactive = fakePi(["read", "bash"]);
	createPolicy(inactive);
	assert.equal(inactive.emit("tool_result", bash("rg foo")), undefined);
	assert.equal(pi.emit("tool_result", bash("echo grepping")), undefined);
});

function sdkPath() {
	const require = createRequire(import.meta.url);
	const candidates = [() => require.resolve("@earendil-works/pi-coding-agent"),
		() => require.resolve(join(execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim(), "@earendil-works/pi-coding-agent")),
		() => {
			// Homebrew-style installs: resolve the package next to the real `pi` executable.
			const script = execFileSync("sh", ["-c", "command -v pi"], { encoding: "utf8" }).trim();
			const target = execFileSync("sh", ["-c", `grep -o '"/[^"]*/bin/pi"' "${script}" || true`], { encoding: "utf8" }).trim().replaceAll('"', "") || script;
			return require.resolve(join(dirname(dirname(target)), "lib/node_modules/@earendil-works/pi-coding-agent"));
		}];
	for (const candidate of candidates) { try { return candidate(); } catch { /* next */ } }
	return undefined;
}
const sdk = sdkPath();

test("Pi's real loader registers only code_search and the nudge/reset hooks", { skip: !sdk && "Pi SDK is not installed" }, async () => {
	const { loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdk)).href);
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	const extension = loaded.extensions[0];
	assert.deepEqual([...extension.tools.keys()], [TOOL]);
	assert.deepEqual([...extension.handlers.keys()].sort(), ["before_agent_start", "tool_result"]);
	assert.equal(extension.commands.size, 0);
	const definition = extension.tools.get(TOOL).definition;
	assert.ok(definition.promptSnippet && definition.promptGuidelines.length >= 3);
});
