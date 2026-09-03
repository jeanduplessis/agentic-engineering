import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { stripVTControlCharacters } from "node:util";

// Use Pi's real proxy and tool renderer, but never start a terminal or browser.
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
let ToolExecutionComponent, CompactionSummaryMessageComponent, getOsc8LinkAtColumn, loadExtensions, createInteractiveTuiReference;
if (sdkPath) {
	const sdk = await import(pathToFileURL(sdkPath).href);
	({ ToolExecutionComponent, CompactionSummaryMessageComponent } = sdk);
	sdk.initTheme("dark");
	const tui = await import(pathToFileURL(createRequire(sdkPath).resolve("@earendil-works/pi-tui")).href);
	({ getOsc8LinkAtColumn } = tui);
	tui.setCapabilities({ images: null, trueColor: true, hyperlinks: true });
	({ loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href));
	({ createInteractiveTuiReference } = await import(new URL("./modes/interactive/interactive-mode.js", pathToFileURL(sdkPath)).href));
}

async function loadExtension(t) {
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	const emit = (event) => {
		for (const handler of loaded.extensions[0].handlers.get(event) ?? []) handler({}, { ui: {} });
	};
	t.after(() => {
		emit("session_shutdown");
		loaded.runtime.invalidate();
	});
	emit("session_start");
	return emit;
}

function tool(ui) {
	return new ToolExecutionComponent("bash", "url-forwarding-test", { command: "echo test" }, {}, undefined, ui, process.cwd());
}

function toggle(renderer, component) {
	const lines = component.render(80);
	const link = lines.join("\n").match(/\x1b\]8;;(pi:\/\/tool-output-expand\/\d+)\x07/);
	assert.ok(link, "expandable block has an expansion link");
	const wasExpanded = component.expanded;
	renderer.openUrl(link[1]);
	assert.equal(component.expanded, !wasExpanded, "internal URL toggles the block");
	return link[1];
}

test("external links still open after many tool redraws through Pi's TUI proxy", sdkRequired, async (t) => {
	await loadExtension(t);
	const opened = [];
	const renderer = { mode: "fullscreen", openUrl: (url) => opened.push(url), requestRender() {} };
	const ui = createInteractiveTuiReference(() => renderer);
	const component = tool(ui);
	component.render(80);
	renderer.openUrl("http://localhost:3000/before");
	assert.deepEqual(opened, ["http://localhost:3000/before"]);

	// Exercise enough redraws to overflow the old callback chain.
	for (let i = 0; i < 40_000; i++) component.render(80);
	renderer.openUrl("http://localhost:3000/after");
	renderer.openUrl("file:///tmp/preview.html");
	toggle(renderer, component);
	toggle(renderer, component);
	assert.deepEqual(opened, ["http://localhost:3000/before", "http://localhost:3000/after", "file:///tmp/preview.html"]);

	const summary = new CompactionSummaryMessageComponent({
		tokensBefore: 1000,
		summary: "[Open preview](http://localhost:3000/summary)",
	});
	toggle(renderer, summary);
	const linkLine = summary.render(80).find((line) => stripVTControlCharacters(line).includes("Open preview"));
	assert.ok(linkLine);
	const link = getOsc8LinkAtColumn(linkLine, stripVTControlCharacters(linkLine).indexOf("Open preview"));
	assert.equal(link, "http://localhost:3000/summary", "existing OSC 8 links are not replaced by expansion links");
	renderer.openUrl(link);
	assert.equal(opened.at(-1), link);
	assert.equal(summary.expanded, true, "external link does not collapse the summary");
	toggle(renderer, summary);
});

test("external links survive session reset, shutdown, and extension reload", sdkRequired, async (t) => {
	const emit = await loadExtension(t);
	const opened = [];
	const renderer = { mode: "fullscreen", openUrl: (url) => opened.push(url), requestRender() {} };
	const ui = createInteractiveTuiReference(() => renderer);
	const component = tool(ui);
	component.render(80);

	emit("session_start");
	// No tool render is needed for native links to work after a reset.
	renderer.openUrl("https://example.com/reset");
	toggle(renderer, component);
	emit("session_shutdown");
	renderer.openUrl("https://example.com/shutdown");
	emit("session_start");
	component.render(80);

	await loadExtension(t);
	const internalUrl = toggle(renderer, component);
	renderer.openUrl("https://example.com/reloaded");
	// A late shutdown from the previous instance must not detach the new owner.
	emit("session_shutdown");
	const wasExpanded = component.expanded;
	renderer.openUrl(internalUrl);
	assert.equal(component.expanded, !wasExpanded, "new owner stays active without another render");
	assert.deepEqual(opened, ["https://example.com/reset", "https://example.com/shutdown", "https://example.com/reloaded"]);
});

test("URL forwarding follows fullscreen renderer replacement without changing regular mode", sdkRequired, async (t) => {
	await loadExtension(t);
	const opened = [];
	let renderer = { mode: "fullscreen", openUrl: (url) => opened.push(["first", url]), requestRender() {} };
	const ui = createInteractiveTuiReference(() => renderer);
	const component = tool(ui);
	toggle(renderer, component);
	renderer.openUrl("https://example.com/first");

	const regularOpenUrl = (url) => opened.push(["regular", url]);
	renderer = { mode: "regular", openUrl: regularOpenUrl, requestRender() {} };
	assert.ok(!component.render(80).join("\n").includes("pi://tool-output-expand/"));
	assert.equal(renderer.openUrl, regularOpenUrl);
	renderer.openUrl("https://example.com/regular");

	renderer = { mode: "fullscreen", openUrl: (url) => opened.push(["second", url]), requestRender() {} };
	toggle(renderer, component);
	renderer.openUrl("https://example.com/second");
	assert.deepEqual(opened, [
		["first", "https://example.com/first"],
		["regular", "https://example.com/regular"],
		["second", "https://example.com/second"],
	]);
});
