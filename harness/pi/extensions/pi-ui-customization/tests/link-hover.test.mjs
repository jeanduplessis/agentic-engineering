import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

// Real Pi rendering and input routing with an in-memory terminal; no model/browser.
const require = createRequire(import.meta.url);
let sdkPath;
try {
	sdkPath = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
} catch {
	try {
		const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
		sdkPath = require.resolve(join(globalRoot, "@earendil-works/pi-coding-agent"));
	} catch { /* Report an explicit skip when Pi is unavailable. */ }
}
const sdkRequired = { skip: !sdkPath && "Pi SDK is not installed" };
let TuiAltScreen, TuiMainScreen, ToolExecutionComponent, setCapabilities, loadExtensions, createInteractiveTuiReference;
if (sdkPath) {
	const sdk = await import(pathToFileURL(sdkPath).href);
	({ ToolExecutionComponent } = sdk);
	sdk.initTheme("dark");
	({ TuiAltScreen, TuiMainScreen, setCapabilities } = await import(pathToFileURL(createRequire(sdkPath).resolve("@earendil-works/pi-tui")).href));
	({ loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href));
	({ createInteractiveTuiReference } = await import(new URL("./modes/interactive/interactive-mode.js", pathToFileURL(sdkPath)).href));
}

const POINTER = "\x1b]22;pointer\x1b\\";
const DEFAULT = "\x1b]22;default\x1b\\";
const EXAMPLE_URL = "https://example.com";
const link = (text = "Open example", url = EXAMPLE_URL) => `\x1b]8;;${url}\x07${text}\x1b]8;;\x07`;
const mouse = (x, y, button = 35, release = false) => `\x1b[<${button};${x + 1};${y + 1}${release ? "m" : "M"}`;

function environment(t, overrides = {}) {
	for (const key of ["TERM", "TERM_PROGRAM", "TMUX", "ZELLIJ", "STY"]) {
		const previous = process.env[key];
		t.after(() => { if (previous === undefined) delete process.env[key]; else process.env[key] = previous; });
		delete process.env[key];
	}
	Object.assign(process.env, { TERM: "xterm-ghostty" }, overrides);
}

async function extension(t, mode = "tui") {
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	const emit = (event) => {
		for (const handler of loaded.extensions[0].handlers.get(event) ?? []) handler({}, { ui: {}, mode });
	};
	t.after(() => { emit("session_shutdown"); loaded.runtime.invalidate(); });
	emit("session_start");
	return emit;
}

function terminalHarness(t, { regular = false, mouseEnabled = true } = {}) {
	setCapabilities({ images: null, trueColor: true, hyperlinks: true });
	const writes = [], opened = [], keys = [];
	let onInput;
	const terminal = {
		columns: 40, rows: 6, kittyProtocolActive: false,
		start(input) { onInput = input; }, stop() {},
		write(data) { writes.push(data); },
		hideCursor() {}, showCursor() {}, moveBy() {},
		clearLine() {}, clearFromCursor() {}, clearScreen() {}, setTitle() {},
	};
	const Renderer = regular ? TuiMainScreen : TuiAltScreen;
	const tui = new Renderer(terminal, false, undefined, { mouse: mouseEnabled, copyOnSelect: false, openUrl: (url) => opened.push(url) });
	let lines = [link(), "plain text"];
	const component = { render: () => lines, invalidate() {}, handleInput: (data) => keys.push(data) };
	tui.addChild(component);
	tui.setFocus(component);
	tui.start();
	tui.renderNow();
	t.after(() => tui.stop({ preserveScreen: true }));
	return {
		tui, terminal, opened, keys, writes,
		input: (data) => onInput(data),
		shapes: () => writes.filter((data) => data.startsWith("\x1b]22;")),
		setLines(next) { lines = next; tui.invalidate(); tui.renderNow(); },
	};
}

test("links show a hand on hover without changing clicks, keyboard input, or selection", sdkRequired, async (t) => {
	environment(t);
	await extension(t);
	const h = terminalHarness(t);
	h.setLines([`中 ${link()} plain`, "plain text"]);
	h.input(mouse(0, 0));
	assert.deepEqual(h.shapes(), []);
	h.input(mouse(3, 0));
	h.input(mouse(4, 0));
	assert.deepEqual(h.shapes(), [POINTER], "wide text is measured in terminal cells; repeated hover does not write");
	assert.deepEqual(h.opened, [], "hover never activates a link");
	h.input(mouse(4, 0, 0));
	assert.equal(h.shapes().at(-1), DEFAULT, "press restores normal pointer for text selection");
	h.input(mouse(4, 0, 0, true));
	assert.deepEqual(h.opened, [EXAMPLE_URL]);
	assert.equal(h.shapes().at(-1), POINTER);
	h.input(mouse(0, 1));
	assert.equal(h.shapes().at(-1), DEFAULT);
	h.input("a");
	assert.deepEqual(h.keys, ["a"], "mouse events stay consumed by Pi while keys pass through");

	h.setLines([link("drag this text"), "plain"]);
	h.input(mouse(1, 0, 0));
	h.input(mouse(7, 0, 32));
	assert.equal(h.shapes().at(-1), DEFAULT);
	h.input(mouse(7, 0, 0, true));
	assert.deepEqual(h.opened, [EXAMPLE_URL], "drag selection does not open the link");
	assert.equal(h.tui.hasActiveSelection(), true);
});

test("stationary hover follows output changes, scrolling, overlays, and resize", sdkRequired, async (t) => {
	environment(t);
	await extension(t);
	const h = terminalHarness(t);
	h.input(mouse(1, 0));
	assert.equal(h.shapes().at(-1), POINTER);
	h.setLines(["plain", link()]);
	assert.equal(h.shapes().at(-1), DEFAULT, "streamed redraw rechecks the cell without mouse movement");
	h.input(mouse(1, 1));
	assert.equal(h.shapes().at(-1), POINTER);

	const overlay = h.tui.showOverlay({ render: () => ["plain overlay", "plain overlay"], invalidate() {} },
		{ anchor: "top-left", width: 40 });
	h.tui.renderNow();
	assert.equal(h.shapes().at(-1), DEFAULT, "covered links are not hover targets");
	overlay.hide();
	h.tui.renderNow();
	assert.equal(h.shapes().at(-1), POINTER);
	h.terminal.rows = 1;
	h.tui.renderNow();
	assert.equal(h.shapes().at(-1), DEFAULT, "pointer position outside resized screen is cleared");

	h.terminal.rows = 3;
	h.setLines([link(), "plain 1", "plain 2", "plain 3", "plain 4", "plain 5"]);
	h.tui.scrollToTop();
	h.tui.renderNow();
	h.input(mouse(1, 0));
	assert.equal(h.shapes().at(-1), POINTER);
	h.input(mouse(1, 0, 65)); // wheel down
	h.tui.renderNow();
	assert.equal(h.shapes().at(-1), DEFAULT);
	h.tui.scrollToTop();
	h.tui.renderNow();
	assert.equal(h.shapes().at(-1), POINTER, "keyboard/programmatic scroll also refreshes hover");
	h.input(mouse(100, 0));
	assert.equal(h.shapes().at(-1), DEFAULT);
});

test("clickable tool rows show a hand and still toggle through Pi's real proxy", sdkRequired, async (t) => {
	environment(t);
	await extension(t);
	const h = terminalHarness(t);
	h.tui.clear();
	const ui = createInteractiveTuiReference(() => h.tui);
	const tool = new ToolExecutionComponent("bash", "hover-tool", { command: "echo test" }, {}, undefined, ui, process.cwd());
	h.tui.addChild(tool);
	h.tui.renderNow();
	h.input(mouse(3, 1));
	assert.equal(h.shapes().at(-1), POINTER);
	const expanded = tool.expanded;
	h.input(mouse(3, 1, 0));
	h.input(mouse(3, 1, 0, true));
	assert.equal(tool.expanded, !expanded);
	assert.deepEqual(h.opened, []);
});

test("focus loss, reload, session reset, and terminal stop restore the default pointer", sdkRequired, async (t) => {
	environment(t);
	const emit = await extension(t);
	const h = terminalHarness(t);
	h.input(mouse(1, 0));
	h.input("\x1b[O");
	assert.deepEqual(h.shapes(), [POINTER, DEFAULT]);
	h.tui.renderNow();
	assert.deepEqual(h.shapes(), [POINTER, DEFAULT], "redraw while unfocused does not restore a stale hand");
	h.input("\x1b[I");
	h.input(mouse(1, 0));
	emit("session_start");
	assert.equal(h.shapes().at(-1), DEFAULT);
	h.input(mouse(1, 0));
	assert.equal(h.shapes().at(-1), POINTER);

	const wrappedInput = TuiAltScreen.prototype.handleViewportInput;
	const replacement = await extension(t);
	assert.equal(h.shapes().at(-1), DEFAULT);
	assert.equal(TuiAltScreen.prototype.handleViewportInput, wrappedInput, "reload does not stack wrappers");
	emit("session_shutdown"); // Late teardown of the previous owner.
	h.input(mouse(1, 0));
	assert.equal(h.shapes().at(-1), POINTER);
	h.tui.stop({ preserveScreen: true });
	assert.equal(h.shapes().at(-1), DEFAULT);
	h.tui.start();
	h.tui.renderNow();
	h.input(mouse(1, 0));
	assert.equal(h.shapes().at(-1), POINTER);
	replacement("session_shutdown");
	assert.equal(h.shapes().at(-1), DEFAULT);
	const count = h.shapes().length;
	h.input(mouse(1, 0));
	assert.equal(h.shapes().length, count, "disabled extension leaves no active hover handler");
});

test("regular mode, disabled mouse, and non-TUI sessions do not write pointer controls", sdkRequired, async (t) => {
	environment(t);
	const emit = await extension(t);
	for (const options of [{ regular: true }, { mouseEnabled: false }]) {
		const h = terminalHarness(t, options);
		h.input(mouse(1, 0));
		assert.deepEqual(h.shapes(), []);
	}
	emit("session_shutdown");
	for (const mode of ["rpc", "json", "print"]) {
		await extension(t, mode);
		const h = terminalHarness(t);
		h.input(mouse(1, 0));
		assert.deepEqual(h.shapes(), []);
	}
});

test("unsupported terminals and multiplexers keep their existing pointer behavior", sdkRequired, async (t) => {
	for (const overrides of [
		{ TERM: "xterm-256color", TERM_PROGRAM: "iTerm.app" },
		{ TERM: "dumb" },
		{ TMUX: "/tmp/tmux-test" }, { ZELLIJ: "1" }, { STY: "screen-test" },
		{ TERM: "screen-256color", TERM_PROGRAM: "ghostty" },
		{ TERM: "tmux-256color", TERM_PROGRAM: "ghostty" },
	]) {
		await t.test(JSON.stringify(overrides), async (t) => {
			environment(t, overrides);
			await extension(t);
			const h = terminalHarness(t);
			h.input(mouse(1, 0));
			assert.deepEqual(h.shapes(), []);
		});
	}
});
