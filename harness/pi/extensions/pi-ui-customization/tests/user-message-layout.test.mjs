import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { stripVTControlCharacters } from "node:util";

// Exercise native message layout, links, and input offline with the installed SDK.
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
let sdk, tui, loadExtensions, nativeRender;
if (sdkPath) {
	sdk = await import(pathToFileURL(sdkPath).href);
	tui = await import(pathToFileURL(createRequire(sdkPath).resolve("@earendil-works/pi-tui")).href);
	sdk.initTheme("dark");
	nativeRender = sdk.UserMessageComponent.prototype.render;
	({ loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href));
}

async function extension(t) {
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	t.after(() => loaded.runtime.invalidate());
	tui.setCapabilities({ images: null, trueColor: true, hyperlinks: true });
}

const plain = (lines) => lines.map(stripVTControlCharacters);
const withoutZones = (lines) => lines.map((line) => line.replace(/^(?:\x1b\]133;[ABC](?:\x07|\x1b\\))+/, ""));

function assertNativeBlock(component, width, blockWidth) {
	const lines = component.render(width);
	const inset = width - blockWidth;
	assert.deepEqual(withoutZones(lines).map((line) => line.slice(inset)), withoutZones(nativeRender.call(component, blockWidth)));
	assert.ok(lines[0].startsWith("\x1b]133;A\x07"), "prompt start stays at byte zero");
	assert.ok(lines.at(-1).startsWith("\x1b]133;B\x07\x1b]133;C\x07"), "prompt end stays at byte zero");
	assert.ok(withoutZones(lines).every((line) => line.startsWith(" ".repeat(inset) + "\x1b")), "inset is outside the native background");
	return lines;
}
const assistantMessage = {
	role: "assistant", content: [{ type: "text", text: "Assistant stays on the left." }],
	api: "anthropic-messages", provider: "anthropic", model: "offline-fixture", stopReason: "stop", timestamp: 0,
	usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
};

test("user blocks sit on the right with left-aligned multiline text; other messages stay unchanged", sdkRequired, async (t) => {
	const assistant = new sdk.AssistantMessageComponent(assistantMessage);
	const custom = new sdk.CustomMessageComponent({ role: "custom", customType: "fixture", content: "Custom stays on the left.", display: true, timestamp: 0 });
	const before = [assistant.render(100), custom.render(100)];
	await extension(t);
	const component = new sdk.UserMessageComponent("First line\nSecond, longer line\n\n```ts\nconst value = 1;\n  console.log(value);\n```");
	const lines = assertNativeBlock(component, 100, 25);
	const text = plain(lines);
	assert.equal(text.find((line) => line.includes("First line")).indexOf("First line"), 76);
	assert.equal(text.find((line) => line.includes("Second, longer line")).indexOf("Second"), 76);
	assert.equal(text.find((line) => line.includes("console.log(value);")).indexOf("console"), 80, "code indentation survives content sizing");
	assert.deepEqual([assistant.render(100), custom.render(100)], before);
});

test("user wrapping follows terminal resize, preserves Unicode/ANSI/links, and keeps narrow terminals full width", sdkRequired, async (t) => {
	await extension(t);
	const content = "中文 café e\u0301 👩‍💻 \x1b[1mbold\x1b[22m and readable prose that wraps across several lines.\n\n[Open example](https://example.com/user)\n\n" + "longword".repeat(30);
	const component = new sdk.UserMessageComponent(content);
	for (const [width, blockWidth] of [[100, 80], [160, 88], [80, 64], [50, 40], [40, 40], [20, 20], [4, 4], [100, 80]]) {
		const lines = assertNativeBlock(component, width, blockWidth);
		assert.ok(lines.every((line) => tui.visibleWidth(line) <= width), `no overflow at ${width} columns`);
		assert.ok(lines.join("").includes("\x1b[1m"), "ANSI styling survives");
		if (width >= 40) {
			const linkedLine = lines.find((line) => stripVTControlCharacters(line).includes("Open example"));
			const labelColumn = tui.visibleWidth(linkedLine.slice(0, linkedLine.indexOf("Open example")));
			assert.equal(tui.getOsc8LinkAtColumn(linkedLine, labelColumn), "https://example.com/user");
			assert.equal(tui.getOsc8LinkAtColumn(linkedLine, 0), undefined, "left margin is not linked");
			assert.ok(plain(lines).join("").includes("中文 café e\u0301 👩‍💻"));
		}
	}
	component.setOutputPad(2);
	component.invalidate();
	assertNativeBlock(component, 100, 80);
	assert.equal(component.text, content, "layout does not rewrite the user message");
});

for (const protocol of ["kitty", "iterm2"]) {
	test(`user layout does not prefix ${protocol} image controls or drop image-height rows`, sdkRequired, async (t) => {
		await extension(t);
		tui.setCapabilities({ images: protocol, trueColor: true, hyperlinks: true });
		t.after(() => tui.setCapabilities({ images: null, trueColor: true, hyperlinks: true }));
		const component = new sdk.UserMessageComponent("Image caption");
		// Native user messages currently contain Markdown only. Add a real SDK Image
		// child to exercise protocol preservation without manufacturing escape strings.
		component.addChild(new tui.Image(
			"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII=",
			"image/png", { fallbackColor: (text) => text }, { maxWidthCells: 6 },
		));
		const native = nativeRender.call(component, 80);
		const lines = component.render(100);
		const prefix = protocol === "kitty" ? "\x1b_G" : "\x1b]1337;File=";
		const imageRow = native.findIndex((line) => line.includes(prefix));
		assert.ok(imageRow >= 0);
		assert.equal(lines.length, native.length);
		assert.equal(lines[imageRow], native[imageRow], "protocol line is byte-for-byte native");
		for (let i = imageRow + 1; i < native.length; i++) {
			assert.equal(stripVTControlCharacters(lines[i]).trim(), "", "reserved image rows remain blank");
		}
	});
}

test("right-aligned user URLs click at their visible position and native input still works after reload", sdkRequired, async (t) => {
	await extension(t);
	const component = new sdk.UserMessageComponent("[Open example](https://example.com/user)");
	const before = component.render(100);
	for (let reload = 0; reload < 3; reload++) {
		await extension(t);
		assert.deepEqual(component.render(100), before, "reload does not stack insets or padding");
	}
	assert.deepEqual(new sdk.UserMessageComponent("[Open example](https://example.com/user)").render(100), before);

	const opened = [];
	let onInput;
	const terminal = {
		columns: 100, rows: 12, kittyProtocolActive: false,
		start(input) { onInput = input; }, stop() {}, write() {},
		hideCursor() {}, showCursor() {}, moveBy() {}, clearLine() {}, clearFromCursor() {}, clearScreen() {}, setTitle() {},
	};
	const renderer = new tui.TuiAltScreen(terminal, false, undefined, { mouse: true, copyOnSelect: false, openUrl: (url) => opened.push(url) });
	const input = new tui.Input();
	renderer.addChild(component);
	renderer.addChild(new sdk.AssistantMessageComponent(assistantMessage));
	renderer.addChild(input);
	renderer.setFocus(input);
	renderer.start();
	t.after(() => renderer.stop({ preserveScreen: true }));
	renderer.renderNow();
	const y = plain(before).findIndex((line) => line.includes("Open example"));
	const x = plain(before)[y].indexOf("Open example");
	const click = (column) => {
		onInput(`\x1b[<0;${column + 1};${y + 1}M`);
		onInput(`\x1b[<0;${column + 1};${y + 1}m`);
	};
	click(0);
	assert.deepEqual(opened, []);
	click(x);
	assert.deepEqual(opened, ["https://example.com/user"]);
	onInput("native input");
	assert.equal(input.getValue(), "native input");
});

test("short user bubbles fit display cells plus padding, including styled Unicode and resize", sdkRequired, async (t) => {
	await extension(t);
	for (const content of ["Short message", "\x1b[1m中文 e\u0301 👩‍💻\x1b[22m"]) {
		const component = new sdk.UserMessageComponent(content);
		const textWidth = tui.visibleWidth(stripVTControlCharacters(content));
		for (const width of [100, 40, 20, 160, 100]) {
			const lines = assertNativeBlock(component, width, textWidth + 2);
			assert.equal(lines.length, 3, "exactly one top row, one text row, and one bottom row");
			assert.equal(plain(lines)[1].trim(), stripVTControlCharacters(content));
			assert.ok(plain(lines)[1].endsWith(stripVTControlCharacters(content) + " "), "only native right padding follows the longest text row");
		}
		component.setOutputPad(2);
		assertNativeBlock(component, 100, textWidth + 4);
	}
	assert.deepEqual(new sdk.UserMessageComponent("").render(100), [], "empty messages gain no padding-only bubble");
});

test("fullscreen keeps balanced visible padding and native prompt navigation without emitting OSC 133", sdkRequired, async (t) => {
	await extension(t);
	function navigate(width, native) {
		let onInput;
		const writes = [];
		const terminal = {
			columns: width, rows: 6, kittyProtocolActive: false,
			start(input) { onInput = input; }, stop() {}, write(data) { writes.push(data); },
			hideCursor() {}, showCursor() {}, moveBy() {}, clearLine() {}, clearFromCursor() {}, clearScreen() {}, setTitle() {},
		};
		const document = new tui.Container();
		for (let n = 0; n < 5; n++) {
			const user = new sdk.UserMessageComponent(`Prompt ${n}`);
			document.addChild(native ? { render: (w) => nativeRender.call(user, w), invalidate: () => user.invalidate() } : user);
			document.addChild(new tui.Text(`Assistant ${n}\nsecond\nthird`, 0, 0));
		}
		const scroll = new tui.ScrollView(document, { primary: true, follow: "end" });
		const renderer = new tui.TuiAltScreen(terminal, false, undefined, { mouse: true });
		renderer.setLayoutRoot(scroll);
		renderer.start();
		try {
			renderer.renderNow();
			const start = scroll.scrollTop;
			onInput("\x1b[1;5A"); // Ctrl+Up: previous user prompt
			renderer.renderNow();
			const previous = scroll.scrollTop;
			renderer.scrollToTop();
			renderer.renderNow();
			// Inspect the actual composed fullscreen frame, not just component output.
			const frame = renderer.previousScreen;
			assert.equal(plain(frame)[0].trim(), "");
			assert.equal(plain(frame)[1].trim(), "Prompt 0");
			assert.equal(plain(frame)[2].trim(), "");
			assert.equal(plain(frame)[3].trim(), "Assistant 0", "bottom padding stays one row");
			const background = frame[1].match(/\x1b\[48;[^m]*m/)[0];
			assert.ok(frame[0].includes(background), "visible top padding has the user background");
			assert.ok(frame[2].includes(background), "visible bottom padding has the user background");
			if (!native) {
				const bubbleWidth = "Prompt 0".length + 2;
				assert.ok(frame[0].startsWith(" ".repeat(width - bubbleWidth) + background + " ".repeat(bubbleWidth)), "top padding spans only the right-anchored bubble");
				assert.equal(plain(frame)[1].indexOf("Prompt 0"), width - bubbleWidth + 1);
			}
			onInput("\x1b[1;5B"); // Ctrl+Down: next user prompt
			renderer.renderNow();
			return { start, previous, next: scroll.scrollTop, markersEmitted: writes.join("").includes("\x1b]133;") };
		} finally {
			renderer.stop({ preserveScreen: true });
		}
	}
	for (const width of [100, 40]) {
		const native = navigate(width, true);
		assert.deepEqual(native, { start: 24, previous: 18, next: 6, markersEmitted: false });
		assert.deepEqual(navigate(width, false), native, `native navigation and marker stripping at width ${width}`);
	}
});
