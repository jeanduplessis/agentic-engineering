import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { COMPACTION_REASONS, THINKING_LEVELS, loadConfig, resolveConfig } from "../config.ts";
import { registerCompactionModel } from "../index.ts";

const configured = { compactionModel: { model: "test/vendor/summary", thinkingLevel: "low" } };

async function settingsFixture(t, settings = configured) {
	const root = await mkdtemp(join(tmpdir(), "compaction-model-test-"));
	t.after(() => rm(root, { recursive: true, force: true }));
	const agentDir = join(root, "agent");
	const cwd = join(root, "project");
	await mkdir(agentDir);
	await mkdir(join(cwd, ".custom-pi"), { recursive: true });
	const globalPath = join(agentDir, "settings.json");
	const projectPath = join(cwd, ".custom-pi", "settings.json");
	await writeFile(globalPath, JSON.stringify(settings));
	return { agentDir, cwd, globalPath, projectPath, configDirName: ".custom-pi" };
}

function preparation() {
	return {
		firstKeptEntryId: "kept",
		messagesToSummarize: [{ role: "user", content: "Old work", timestamp: 1 }],
		turnPrefixMessages: [],
		isSplitTurn: false,
		tokensBefore: 12000,
		previousSummary: "Previous work",
		fileOps: { read: new Set(["read.ts"]), edited: new Set(["edit.ts"]), written: new Set() },
		settings: { enabled: true, reserveTokens: 1000, keepRecentTokens: 2000 },
	};
}

async function harness(t, compact, settings = configured) {
	const files = await settingsFixture(t, settings);
	let handler;
	registerCompactionModel({ on(name, callback) {
		assert.equal(name, "session_before_compact");
		assert.equal(handler, undefined);
		handler = callback;
	} }, { ...files, compact });
	const notifications = [];
	const model = { provider: "test", id: "vendor/summary", api: "openai-completions", reasoning: true, maxTokens: 4096, baseUrl: "https://unused.invalid" };
	const auth = { ok: true, apiKey: "test-only", headers: { "x-test": "header", "x-remove": null }, env: { TEST_ONLY: "value" }, baseUrl: "https://resolved.invalid" };
	const provider = { streamSimple() { throw new Error("Unexpected provider request"); } };
	const controller = new AbortController();
	const event = { preparation: preparation(), branchEntries: [], reason: "manual", customInstructions: "Keep decisions", signal: controller.signal };
	const ctx = {
		cwd: files.cwd,
		hasUI: true,
		isProjectTrusted: () => false,
		ui: { notify(message, level) { notifications.push({ message, level }); } },
		model: { provider: "active", id: "conversation" },
		modelRegistry: {
			find(p, id) { assert.equal(p, "test"); assert.equal(id, "vendor/summary"); return model; },
			getProvider(id) { assert.equal(id, "test"); return provider; },
			async getApiKeyAndHeaders() { return auth; },
		},
	};
	return { ...files, run: () => handler(event, ctx), event, ctx, notifications, controller, model, auth, provider };
}

const noRequest = () => assert.fail("Should defer to Pi without a model request");

test("configuration merges trusted fields, keeps slash-containing model IDs, and supports every thinking level", () => {
	assert.deepEqual(resolveConfig(configured, { compactionModel: { reasons: ["overflow", "overflow"] } }), {
		provider: "test", modelId: "vendor/summary", thinkingLevel: "low", reasons: ["overflow"],
	});
	for (const level of THINKING_LEVELS) {
		assert.equal(resolveConfig(configured, { compactionModel: { thinkingLevel: level } }).thinkingLevel, level);
	}
	assert.equal(resolveConfig(configured, { compactionModel: { thinkingLevel: null } }).thinkingLevel, undefined);
	assert.deepEqual(resolveConfig(configured).reasons, COMPACTION_REASONS);
	assert.equal(resolveConfig({ compactionModel: false }, configured).provider, "test");
	assert.equal(resolveConfig(configured, { compactionModel: false }), null);
	assert.equal(resolveConfig(configured, { compactionModel: { enabled: false } }), null);
	assert.equal(resolveConfig({}), null);
});

test("invalid configuration cannot silently broaden routing", () => {
	for (const value of [true, [], "model", null]) {
		assert.throws(() => resolveConfig({ compactionModel: value }));
	}
	for (const fields of [
		{ model: "no-provider" }, { model: "/model" }, { model: "provider/" }, { model: "provider/white space" },
		{ thinkingLevel: "extreme" }, { enabled: "false" }, { reasons: ["manual", "typo"] }, { reasons: "manual" }, { reasons: null },
	]) {
		assert.throws(() => resolveConfig(configured, { compactionModel: fields }));
	}
});

test("settings are read-only, reloaded each time, and untrusted project settings are not read", async (t) => {
	const f = await settingsFixture(t);
	const original = await readFile(f.globalPath, "utf8");
	const load = (trusted) => loadConfig(f.agentDir, f.cwd, trusted, f.configDirName);
	await writeFile(f.projectPath, "{invalid: SECRET}");
	assert.equal((await load(false)).provider, "test");
	await assert.rejects(load(true), (error) => !error.message.includes("SECRET"));
	await writeFile(f.projectPath, JSON.stringify({ compactionModel: { reasons: ["threshold"] } }));
	assert.deepEqual((await load(true)).reasons, ["threshold"]);
	assert.equal(await readFile(f.globalPath, "utf8"), original);
	await writeFile(f.globalPath, JSON.stringify({ compactionModel: false }));
	assert.equal(await load(false), null);
	await rm(f.globalPath);
	assert.equal(await load(false), null);
});

test("disabled, absent, and filtered configurations leave native compaction in control", async (t) => {
	const h = await harness(t, noRequest);
	for (const settings of [{}, { compactionModel: false }, { compactionModel: { enabled: false } },
		{ compactionModel: { model: "test/vendor/summary", reasons: [] } },
		{ compactionModel: { model: "test/vendor/summary", reasons: ["threshold", "overflow"] } }]) {
		await writeFile(h.globalPath, JSON.stringify(settings));
		assert.equal(await h.run(), undefined);
	}
	assert.deepEqual(h.notifications, []);
});

test("all native reasons route without changing the conversation model or preparation", async (t) => {
	const calls = [];
	const result = { summary: "Summary", firstKeptEntryId: "kept", tokensBefore: 12000, usage: { totalTokens: 31 }, details: { readFiles: ["read.ts"], modifiedFiles: ["edit.ts"] } };
	const h = await harness(t, async (...args) => { calls.push(args); return result; });
	for (const reason of COMPACTION_REASONS) {
		h.event.reason = reason;
		const routed = await h.run();
		assert.deepEqual(routed.compaction, { ...result, details: { ...result.details, compactionModel: true } });
	}
	for (const args of calls) {
		assert.equal(args[0], h.event.preparation);
		assert.deepEqual(args[1], { ...h.model, baseUrl: h.auth.baseUrl });
		assert.equal(args[2], h.auth.apiKey);
		assert.equal(args[3], undefined);
		assert.equal(args[4], "Keep decisions");
		assert.equal(args[5], h.event.signal);
		assert.equal(args[6], "low");
		assert.equal(typeof args[7], "function");
		assert.equal(args[8], h.auth.env);
	}
	assert.equal(h.model.baseUrl, "https://unused.invalid");
	assert.deepEqual(h.ctx.model, { provider: "active", id: "conversation" });
	assert.deepEqual(h.notifications, []);
});

test("missing models, auth failures, bad JSON, and provider failures defer without leaking error details", async (t) => {
	const h = await harness(t, () => { throw new Error("SECRET provider payload"); });
	assert.equal(await h.run(), undefined);
	h.auth.ok = false;
	h.auth.error = "SECRET auth payload";
	assert.equal(await h.run(), undefined);
	h.ctx.modelRegistry.getApiKeyAndHeaders = async () => { throw new Error("SECRET exception"); };
	assert.equal(await h.run(), undefined);
	h.ctx.modelRegistry.find = () => undefined;
	assert.equal(await h.run(), undefined);
	await writeFile(h.globalPath, "{ SECRET invalid json");
	assert.equal(await h.run(), undefined);
	assert.equal(h.notifications.length, 5);
	assert.ok(h.notifications.every(({ message, level }) => level === "warning" && !message.includes("SECRET")));
});

test("headless fallback warns on stderr rather than using UI", async (t) => {
	const h = await harness(t, noRequest, { compactionModel: true });
	h.ctx.hasUI = false;
	const messages = [];
	t.mock.method(console, "warn", (message) => messages.push(message));
	assert.equal(await h.run(), undefined);
	assert.equal(messages.length, 1);
	assert.match(messages[0], /^\[compaction-model\]/);
	assert.deepEqual(h.notifications, []);
});

test("cancellation before work, during auth, or during compaction cancels instead of requesting fallback", async (t) => {
	const before = await harness(t, noRequest);
	before.controller.abort();
	assert.deepEqual(await before.run(), { cancel: true });
	const auth = await harness(t, noRequest);
	auth.ctx.modelRegistry.getApiKeyAndHeaders = async () => { auth.controller.abort(); return auth.auth; };
	assert.deepEqual(await auth.run(), { cancel: true });
	for (const throws of [true, false]) {
		const h = await harness(t, async () => {
			h.controller.abort();
			if (throws) throw new Error("aborted");
			return { summary: "partial" };
		});
		assert.deepEqual(await h.run(), { cancel: true });
		assert.deepEqual(h.notifications, []);
	}
	assert.deepEqual(before.notifications, []);
	assert.deepEqual(auth.notifications, []);
});

test("file tracking survives later default compaction but ignores unrelated hook details and old branches", async (t) => {
	const h = await harness(t, noRequest, {});
	h.event.branchEntries = [
		{ type: "compaction", details: { compactionModel: true, readFiles: ["stale.ts"] } },
		{ type: "compaction", fromHook: true, details: { compactionModel: true, readFiles: ["old.ts", 42], modifiedFiles: ["old-edit.ts", null] } },
	];
	assert.equal(await h.run(), undefined);
	assert.deepEqual([...h.event.preparation.fileOps.read], ["read.ts", "old.ts"]);
	assert.deepEqual([...h.event.preparation.fileOps.edited], ["edit.ts", "old-edit.ts"]);
	h.event.preparation = preparation();
	h.event.branchEntries.push({ type: "compaction", fromHook: true, details: { readFiles: ["other.ts"] } });
	assert.equal(await h.run(), undefined);
	assert.deepEqual([...h.event.preparation.fileOps.read], ["read.ts"]);
});

// Resolve the installed SDK without installing dependencies or starting a Pi/model session.
const require = createRequire(import.meta.url);
let sdkPath;
try {
	sdkPath = require.resolve("@earendil-works/pi-coding-agent");
} catch {
	try {
		const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
		sdkPath = require.resolve(join(globalRoot, "@earendil-works/pi-coding-agent"));
	} catch { /* Unit tests still run when Pi is not installed. */ }
}

test("Pi's real loader discovers the entry point without dependencies or session side effects", { skip: !sdkPath && "Pi SDK is not installed" }, async () => {
	const { loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href);
	const entry = fileURLToPath(new URL("../index.ts", import.meta.url));
	const loaded = await loadExtensions([entry], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	assert.deepEqual([...loaded.extensions[0].handlers.keys()], ["session_before_compact"]);
});

test("native compact integration preserves split summaries, budgets, auth, usage, and cumulative files", { skip: !sdkPath && "Pi SDK is not installed" }, async (t) => {
	const { compact } = await import(pathToFileURL(sdkPath).href);
	const h = await harness(t, compact);
	const usage = { input: 10, output: 5, cacheRead: 0, cacheWrite: 0, totalTokens: 15, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
	const requests = [];
	h.provider.streamSimple = (model, context, options) => {
		requests.push({ model, context, options });
		return { result: async () => ({ role: "assistant", content: [{ type: "text", text: `Summary ${requests.length}` }], stopReason: "stop", usage }) };
	};
	h.event.preparation.isSplitTurn = true;
	h.event.preparation.turnPrefixMessages = [{ role: "user", content: "Split-turn work", timestamp: 2 }];
	const first = (await h.run()).compaction;
	assert.equal(requests.length, 2);
	assert.match(requests[0].context.messages[0].content[0].text, /Previous work/);
	assert.match(requests[0].context.messages[0].content[0].text, /Keep decisions/);
	assert.match(requests[1].context.messages[0].content[0].text, /Split-turn work/);
	assert.deepEqual(requests.map((r) => r.options.maxTokens), [800, 500]);
	for (const r of requests) {
		assert.equal(r.model.baseUrl, h.auth.baseUrl);
		assert.equal(r.options.apiKey, h.auth.apiKey);
		assert.deepEqual(r.options.headers, h.auth.headers);
		assert.deepEqual(r.options.env, h.auth.env);
		assert.equal(r.options.signal, h.event.signal);
		assert.equal(r.options.reasoning, "low");
		assert.equal(r.options.cacheRetention, "none");
		// Pi versions differ in toolChoice; the contract is that summaries expose no tools.
		assert.equal(r.context.tools?.length ?? 0, 0, "summary requests must not offer tools");
		assert.ok(r.options.sessionId);
	}
	assert.match(first.summary, /Summary 1/);
	assert.match(first.summary, /Summary 2/);
	assert.equal(first.firstKeptEntryId, "kept");
	assert.equal(first.usage.totalTokens, 30);
	assert.deepEqual(first.details, { readFiles: ["read.ts"], modifiedFiles: ["edit.ts"], compactionModel: true });
	h.event.branchEntries = [{ type: "compaction", ...first, fromHook: true }];
	h.event.preparation = preparation();
	h.event.preparation.fileOps.read = new Set(["new.ts"]);
	h.event.preparation.fileOps.edited = new Set();
	h.event.preparation.previousSummary = first.summary;
	const second = (await h.run()).compaction;
	assert.deepEqual(second.details.readFiles, ["new.ts", "read.ts"]);
	assert.deepEqual(second.details.modifiedFiles, ["edit.ts"]);
	assert.equal(second.usage.totalTokens, 15);

	// Reject unusable provider output before native compact appends file tags or merges split summaries.
	for (const response of [
		{ stopReason: "aborted", content: [{ type: "text", text: "partial" }] },
		{ stopReason: "error", content: [{ type: "text", text: "partial" }] },
		{ stopReason: "stop", content: [] },
		{ stopReason: "stop", content: [{ type: "text", text: "  " }] },
		{ stopReason: "toolUse", content: [{ type: "text", text: "Summary" }, { type: "toolCall", name: "bash", arguments: {} }] },
	]) {
		h.provider.streamSimple = () => ({ result: async () => ({ ...response, usage }) });
		assert.equal(await h.run(), undefined);
	}
	assert.equal(h.notifications.length, 5);
});
