import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import promptStash from "../index.ts";

function harness() {
	const handlers = new Map();
	const shortcuts = new Map();
	const notices = [];
	const statuses = new Map();
	let text = "";
	promptStash({
		on: (event, handler) => handlers.set(event, handler),
		registerShortcut: (key, shortcut) => shortcuts.set(key, shortcut),
	});
	assert.deepEqual([...shortcuts.keys()], ["super+shift+s"]);
	const ctx = {
		mode: "tui", hasUI: true,
		ui: {
			getEditorText: () => text,
			setEditorText: (value) => { text = value; },
			notify: (message, level) => notices.push({ message, level }),
			setStatus: (key, value) => value === undefined ? statuses.delete(key) : statuses.set(key, value),
		},
	};
	return {
		ctx, notices, statuses,
		get text() { return text; },
		set text(value) { text = value; },
		press: () => shortcuts.get("super+shift+s").handler(ctx),
		emit: (type, fields = {}) => handlers.get(type)?.({ type, ...fields }, ctx),
		input: (fields = {}) => handlers.get("input")({ type: "input", text: "Quick question", source: "interactive", ...fields }, ctx),
	};
}

test("prompt-stash preserves exact drafts and restores once without changing the submitted payload", () => {
	for (const draft of ["  Draft\n\n  second line 🙂 e\u0301\n  ", " \n\t ", "long text ".repeat(200)]) {
		const h = harness();
		h.text = draft;
		h.press();
		assert.equal(h.text, "");
		assert.ok(h.statuses.has("prompt-stash"));
		assert.equal(h.statuses.size, 1);
		assert.ok(!h.statuses.get("prompt-stash").includes(draft), "footer status must not expose draft text");
		const images = Object.freeze([Object.freeze({ type: "image", data: "test-only", mimeType: "image/png" })]);
		const event = Object.freeze({ text: "  Quick question  ", source: "interactive", images });
		assert.equal(h.input(event), undefined);
		assert.equal(h.text, draft);
		assert.equal(event.text, "  Quick question  ");
		assert.equal(event.images, images);
		assert.equal(h.statuses.size, 0);
		h.text = "";
		h.input();
		assert.equal(h.text, "");
		assert.deepEqual(h.notices, []);
	}
});

test("repeat shortcuts toggle manual restore; occupied editors preserve both texts", () => {
	const h = harness();
	h.text = "Private draft";
	for (let i = 0; i < 4; i++) {
		h.press();
		assert.equal(h.text, "");
		h.press();
		assert.equal(h.text, "Private draft");
	}
	h.press();
	h.text = "New writing";
	h.press();
	h.press();
	assert.equal(h.text, "New writing");
	assert.ok(h.statuses.has("prompt-stash"));
	// An earlier async input hook or delayed queue can leave new writing in the editor.
	assert.equal(h.input(), undefined);
	assert.equal(h.text, "New writing");
	assert.equal(h.notices.length, 3);
	assert.ok(h.notices.every(({ message, level }) => level === "warning" && !message.includes("Private draft") && !message.includes("New writing")));
	h.text = "";
	h.press();
	assert.equal(h.text, "Private draft");
	assert.equal(h.statuses.size, 0);
});

test("empty input is harmless and only interactive chat can consume a stash", () => {
	const h = harness();
	h.press();
	h.input({ text: "" });
	h.input();
	assert.equal(h.text, "");
	assert.equal(h.statuses.size, 0);
	h.text = "Draft";
	h.press();
	for (const source of ["rpc", "extension", undefined]) h.input({ source });
	for (const text of ["", "  \n "]) h.input({ text });
	assert.equal(h.text, "");
	assert.ok(h.statuses.has("prompt-stash"));
	h.input({ text: "", images: [{ type: "image", data: "test-only", mimeType: "image/png" }] });
	assert.equal(h.text, "Draft");
});

test("RPC, headless and unavailable UI contexts never touch the editor or consume the stash", () => {
	const h = harness();
	h.text = "Draft";
	h.press();
	const ui = h.ctx.ui;
	h.ctx.ui = new Proxy({}, { get() { assert.fail("UI must not be accessed"); } });
	for (const [mode, hasUI] of [["rpc", true], ["print", false], ["json", false], ["tui", false]]) {
		h.ctx.mode = mode;
		h.ctx.hasUI = hasUI;
		h.press();
		h.input();
	}
	Object.assign(h.ctx, { mode: "tui", hasUI: true, ui });
	h.press();
	assert.equal(h.text, "Draft");
});

test("failed editor writes retain the stash and never expose exception details", () => {
	for (const failure of ["throw", "ignore", "alter"]) {
		const h = harness();
		h.text = "Private draft\n  ";
		h.press();
		const setText = h.ctx.ui.setEditorText;
		h.ctx.ui.setEditorText = () => {
			if (failure === "throw") throw new Error("Private draft in editor exception");
			if (failure === "alter") h.text = "Changed by custom editor";
		};
		h.input();
		assert.ok(h.statuses.has("prompt-stash"));
		assert.equal(h.notices.length, 1);
		assert.ok(!h.notices[0].message.includes("Private draft"));
		h.ctx.ui.setEditorText = setText;
		h.text = "";
		h.press();
		assert.equal(h.text, "Private draft\n  ");
		assert.equal(h.statuses.size, 0);
	}
	const h = harness();
	h.text = "Draft before failed clear";
	const setText = h.ctx.ui.setEditorText;
	h.ctx.ui.setEditorText = () => { throw new Error("Private editor details"); };
	h.press();
	assert.equal(h.text, "Draft before failed clear");
	assert.ok(h.statuses.has("prompt-stash"));
	h.ctx.ui.setEditorText = setText;
	h.text = "";
	h.press();
	assert.equal(h.text, "Draft before failed clear");
});

test("extension instances and session lifecycle boundaries do not share drafts", () => {
	const first = harness();
	const second = harness();
	first.text = "First session only";
	first.press();
	second.input();
	second.press();
	assert.equal(second.text, "");
	first.press();
	assert.equal(first.text, "First session only");
	for (const type of ["session_shutdown", "session_start"]) {
		for (const reason of ["startup", "reload", "new", "resume", "fork", "quit"]) {
			const h = harness();
			h.text = "Old session draft";
			h.press();
			h.emit(type, { reason });
			h.input();
			h.press();
			assert.equal(h.text, "");
			assert.equal(h.statuses.size, 0);
		}
	}
});

// Locate an existing SDK only: no dependency install, user settings, credentials or live model.
const require = createRequire(import.meta.url);
let sdkPath;
try {
	sdkPath = require.resolve("@earendil-works/pi-coding-agent");
} catch {
	try {
		const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
		sdkPath = require.resolve(join(globalRoot, "@earendil-works/pi-coding-agent"));
	} catch { /* Handler tests still run without Pi; runtime checks report explicit skips. */ }
}
const sdkRequired = { skip: !sdkPath && "Pi SDK is not installed" };

async function nativeHarness(t, { streaming = false } = {}) {
	const sdk = await import(pathToFileURL(sdkPath).href);
	const { loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)));
	const { KeybindingsManager } = await import(new URL("./core/keybindings.js", pathToFileURL(sdkPath)));
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	t.after(() => loaded.runtime.invalidate());
	const sessionManager = { getCwd: () => process.cwd() };
	const runner = new sdk.ExtensionRunner(loaded.extensions, loaded.runtime, process.cwd(), sessionManager, {});
	const errors = [];
	runner.onError((error) => errors.push(error));
	t.after(() => assert.deepEqual(errors, []));
	const statuses = new Map();
	const notices = [];
	const deliveries = [];
	const ui = { requestRender() {} };
	const keybindings = new KeybindingsManager();
	const editor = new sdk.CustomEditor(ui, { borderColor: (text) => text }, keybindings);
	let pending;
	// Use native prompt preflight and native interactive/editor handlers. Only the final
	// agent/queue delivery and unrelated UI are fakes; nothing can make a model request.
	const deliver = (kind, content) => deliveries.push({ kind, content, editorText: editor.getExpandedText() });
	const session = {
		isStreaming: streaming, isCompacting: false, agent: { state: {} }, sessionManager,
		model: { provider: "offline-test" }, extensionRunner: runner, _extensionRunner: runner,
		_modelRuntime: { hasConfiguredAuth: () => true },
		promptTemplates: [], _pendingNextTurnMessages: [], _baseSystemPrompt: "", _baseSystemPromptOptions: {},
		_flushPendingBashMessages() {}, _flushPendingCustomMessages() {}, _findLastAssistantMessage() {},
		_expandSkillCommand: sdk.AgentSession.prototype._expandSkillCommand,
		_tryExecuteExtensionCommand: sdk.AgentSession.prototype._tryExecuteExtensionCommand,
		steer: sdk.AgentSession.prototype.steer,
		followUp: sdk.AgentSession.prototype.followUp,
		_queueSteer: async (text) => deliver("steer", text),
		_queueFollowUp: async (text) => deliver("followUp", text),
		_runAgentPrompt: async (messages) => deliver("prompt", messages),
		prompt(text, options) {
			pending = sdk.AgentSession.prototype.prompt.call(this, text, options);
			return pending;
		},
	};
	const mode = Object.assign(Object.create(sdk.InteractiveMode.prototype), {
		editor, defaultEditor: editor, keybindings, runtimeHost: { session }, ui,
		setExtensionStatus: (key, value) => value === undefined ? statuses.delete(key) : statuses.set(key, value),
		showExtensionNotify: (message, level) => notices.push({ message, level }),
		showError: (error) => errors.push(error),
		flushPendingBashComponents() {}, updatePendingMessagesDisplay() {},
		onInputCallback: (text) => session.prompt(text),
	});
	runner.setUIContext(mode.createExtensionUIContext(), "tui");
	mode.setupExtensionShortcuts(runner);
	mode.setupEditorSubmitHandler();
	editor.onAction("app.message.followUp", () => mode.handleFollowUp());
	return {
		editor, mode, runner, loaded, statuses, notices, deliveries,
		press: (key = "\x1b[115;10u") => editor.handleInput(key), // Kitty Shift (1) + Super (8) + 1
		waitForDelivery: () => pending,
		async submit(key = "\r") { editor.handleInput(key); await pending; },
	};
}

for (const [name, streaming, key] of [["idle", false, "\r"], ["steering", true, "\r"], ["follow-up", true, "\x1b[13;3u"]]) {
	test(`native Pi ${name} submission keeps its own payload and restores expanded paste before delivery`, sdkRequired, async (t) => {
		const h = await nativeHarness(t, { streaming });
		const draft = `  Start\n${"pasted line 🙂\n".repeat(12)}  End\n  `;
		h.editor.handleInput(`\x1b[200~${draft}\x1b[201~`);
		assert.notEqual(h.editor.getText(), draft, "fixture must exercise a collapsed paste");
		assert.equal(h.editor.getExpandedText(), draft);
		h.press();
		assert.equal(h.editor.getExpandedText(), "");
		assert.ok(h.statuses.has("prompt-stash"));
		h.editor.handleInput("Quick question");
		await h.submit(key);
		assert.equal(h.editor.getExpandedText(), draft);
		assert.equal(h.deliveries.length, 1);
		assert.equal(h.deliveries[0].editorText, draft, "restore precedes agent/queue delivery");
		if (streaming) {
			assert.equal(h.deliveries[0].kind, name === "steering" ? "steer" : "followUp");
			assert.equal(h.deliveries[0].content, "Quick question");
		} else {
			assert.equal(h.deliveries[0].kind, "prompt");
			assert.deepEqual(h.deliveries[0].content.map(({ role, content }) => ({ role, content })), [
				{ role: "user", content: [{ type: "text", text: "Quick question" }] },
			]);
		}
		assert.equal(h.statuses.size, 0);
		h.editor.setText("Another question");
		await h.submit(key);
		assert.equal(h.editor.getExpandedText(), "");
		assert.deepEqual(h.notices, []);
	});
}

test("native Pi shortcut matching requires Super+Shift+S and manual restore preserves whitespace", sdkRequired, async (t) => {
	const h = await nativeHarness(t);
	for (const key of ["s", "S", "\x1b[115;2u", "\x1b[115;9u", "\x1b[115;6u"]) {
		h.editor.setText("Draft");
		h.press(key);
		assert.equal(h.statuses.size, 0);
		assert.ok(h.editor.getExpandedText().startsWith("Draft"));
	}
	h.editor.setText("  \n  ");
	h.press("\x1b[115:83;10u"); // Kitty alternate shifted key code
	assert.equal(h.editor.getExpandedText(), "");
	h.press();
	assert.equal(h.editor.getExpandedText(), "  \n  ");
});

test("native delayed input never overwrites text typed while an earlier hook waits", sdkRequired, async (t) => {
	const h = await nativeHarness(t);
	let release;
	const gate = new Promise((resolve) => { release = resolve; });
	h.loaded.extensions[0].handlers.get("input").unshift(() => gate);
	h.editor.setText("Private draft");
	h.press();
	h.editor.setText("Quick question");
	const submitted = h.submit();
	h.editor.handleInput("New writing");
	release();
	await submitted;
	assert.equal(h.editor.getExpandedText(), "New writing");
	assert.ok(h.statuses.has("prompt-stash"));
	assert.equal(h.notices.length, 1);
	assert.equal(h.deliveries[0].content[0].content[0].text, "Quick question");
	h.editor.setText("");
	h.press();
	assert.equal(h.editor.getExpandedText(), "Private draft");
});

test("native compaction queues delay restoration, while retry queue paths keep it pending", sdkRequired, async (t) => {
	for (const willRetry of [false, true]) {
		const h = await nativeHarness(t);
		h.mode.compactionQueuedMessages = [];
		h.mode.showStatus = () => {};
		h.mode.session.isCompacting = true;
		h.editor.setText("Private draft");
		h.press();
		h.editor.setText("Queued question");
		await h.submit();
		assert.equal(h.editor.getExpandedText(), "");
		assert.ok(h.statuses.has("prompt-stash"));
		assert.deepEqual(h.deliveries, []);
		h.mode.session.isCompacting = false;
		await h.mode.flushCompactionQueue({ willRetry });
		await h.waitForDelivery();
		assert.equal(h.deliveries.length, 1);
		assert.equal(h.editor.getExpandedText(), willRetry ? "" : "Private draft");
		assert.equal(h.statuses.has("prompt-stash"), willRetry);
		if (willRetry) {
			h.press();
			assert.equal(h.editor.getExpandedText(), "Private draft");
		}
	}
});

test("native local commands and earlier handled input hooks leave the stash pending", sdkRequired, async (t) => {
	const h = await nativeHarness(t);
	h.editor.setText("Draft");
	h.press();
	let localCommands = 0;
	h.mode.handleHotkeysCommand = () => localCommands++;
	h.mode.handleBashCommand = async () => localCommands++;
	h.mode.updateEditorBorderColor = () => {};
	for (const text of ["/hotkeys", "!echo offline-fixture"]) {
		h.editor.setText(text);
		await h.submit();
		assert.equal(h.editor.getExpandedText(), "");
		assert.ok(h.statuses.has("prompt-stash"));
	}
	assert.equal(localCommands, 2);
	h.loaded.extensions[0].commands.set("offline", { name: "offline", handler: async () => localCommands++ });
	h.editor.setText("/offline");
	await h.submit();
	assert.equal(localCommands, 3);
	assert.equal(h.editor.getExpandedText(), "");
	const inputHandlers = h.loaded.extensions[0].handlers.get("input");
	inputHandlers.unshift(() => ({ action: "handled" }));
	h.editor.setText("Handled locally");
	await h.submit();
	assert.equal(h.editor.getExpandedText(), "");
	assert.ok(h.statuses.has("prompt-stash"));
	assert.deepEqual(h.deliveries, []);
	h.press();
	assert.equal(h.editor.getExpandedText(), "Draft");
});
