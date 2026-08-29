import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { stripVTControlCharacters } from "node:util";

// Exercise the extension with Pi's real renderers, offline and without a model.
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
let ToolExecutionComponent, nativeRender, setCapabilities, loaded;
if (sdkPath) {
	const sdk = await import(pathToFileURL(sdkPath).href);
	({ ToolExecutionComponent } = sdk);
	({ setCapabilities } = await import(pathToFileURL(createRequire(sdkPath).resolve("@earendil-works/pi-tui")).href));
	sdk.initTheme("dark");
	nativeRender = ToolExecutionComponent.prototype.render;
	const { loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href);
	loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	after(() => loaded.runtime.invalidate());
}

function harness(t, { mode = "fullscreen", images = null } = {}) {
	setCapabilities({ images, trueColor: true, hyperlinks: true });
	const extension = loaded.extensions[0];
	for (const handler of extension.handlers.get("session_start") ?? []) handler({}, { ui: {} });
	t.after(() => {
		for (const handler of extension.handlers.get("session_shutdown") ?? []) handler({});
		setCapabilities({ images: null, trueColor: true, hyperlinks: true });
	});
	let renderRequests = 0;
	const ui = { mode, requestRender: () => renderRequests++ };
	return {
		tool: (name = "bash", args = {}) => new ToolExecutionComponent(
			name, "streaming-layout-test", args, { imageWidthCells: 6 }, undefined, ui, process.cwd(),
		),
		click(lines) {
			const link = lines.join("\n").match(/\x1b\]8;;(pi:\/\/tool-output-expand\/\d+)\x07/);
			assert.ok(link, "tool block is clickable");
			const before = renderRequests;
			ui.openUrl(link[1]);
			assert.equal(renderRequests, before + 1);
		},
	};
}

const plain = (lines) => lines.map((line) => stripVTControlCharacters(line).trim());

test("collapsed streaming commands do not grow and shrink at trailing newlines", sdkRequired, (t) => {
	const { tool } = harness(t);
	for (const width of [40, 80, 120]) {
		const component = tool();
		const header = "node --input-type=module <<'EOF'";
		for (const tail of ["console.log('first');", `console.log('${"x".repeat(160)}');`]) {
			const command = `${header}\n${tail}`;
			component.updateArgs({ command });
			const baseline = plain(component.render(width));
			assert.ok(baseline.some((line) => line.includes("console.log") || line.includes("xxx")));
			for (const suffix of ["\n", "\n\n", "\n  ", "\n  \n\n"]) {
				component.updateArgs({ command: command + suffix });
				assert.deepEqual(plain(component.render(width)), baseline, `width ${width}, suffix ${JSON.stringify(suffix)}`);
				component.updateArgs({ command: command + suffix + "next" });
				const next = plain(component.render(width));
				assert.equal(next.length, baseline.length);
				assert.ok(next.includes("next"), "preview follows the latest nonblank line");
			}
		}
	}
});

test("click and native expansion preserve complete command and result lines", sdkRequired, (t) => {
	const { tool, click } = harness(t);
	const component = tool();
	component.updateArgs({ command: "node <<'EOF'\nfirst\n\nsecond\n\n" });
	const collapsed = component.render(80);
	click(collapsed);
	assert.deepEqual(plain(component.render(80)), plain(nativeRender.call(component, 80)));
	assert.ok(plain(component.render(80)).includes("first"));
	click(component.render(80));
	assert.deepEqual(component.render(80), collapsed);

	component.setArgsComplete();
	component.updateResult({ content: [{ type: "text", text: "output one\noutput two\noutput three" }], isError: false }, true);
	assert.ok(plain(component.render(80)).includes("output three"));
	component.updateResult({ content: [{ type: "text", text: "output one\noutput two\noutput three" }], isError: false });
	const resultCollapsed = component.render(80);
	assert.ok(plain(resultCollapsed).includes("output three"));
	assert.ok(!plain(resultCollapsed).includes("output two"));
	// Ctrl+O uses this same native expansion API.
	component.setExpanded(true);
	assert.deepEqual(plain(component.render(80)), plain(nativeRender.call(component, 80)));
	assert.ok(plain(component.render(80)).includes("output two"));
	component.setExpanded(false);
	assert.deepEqual(component.render(80), resultCollapsed);
});

test("non-fullscreen rendering remains native during argument streaming", sdkRequired, (t) => {
	const { tool } = harness(t, { mode: "inline" });
	const component = tool();
	for (const command of ["echo first\necho second", "echo first\necho second\n\n", "echo first\necho second\n\necho third"]) {
		component.updateArgs({ command });
		assert.deepEqual(component.render(80), nativeRender.call(component, 80));
	}
});

for (const protocol of ["kitty", "iterm2"]) {
	test(`${protocol} image sequences and trailing image-height rows remain intact`, sdkRequired, (t) => {
		const { tool } = harness(t, { images: protocol });
		const component = tool("read", { path: "/tmp/fixture.png" });
		component.updateResult({
			content: [{ type: "image", mimeType: "image/png", data: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII=" }],
			isError: false,
		});
		const native = nativeRender.call(component, 80);
		const decorated = component.render(80);
		const prefix = protocol === "kitty" ? "\x1b_G" : "\x1b]1337;File=";
		const nativeImage = native.findIndex((line) => line.includes(prefix));
		const decoratedImage = decorated.findIndex((line) => line.includes(prefix));
		assert.ok(nativeImage >= 0 && decoratedImage >= 0);
		assert.deepEqual(decorated.slice(decoratedImage), native.slice(nativeImage));
		if (protocol === "kitty") assert.ok(native.length - nativeImage > 2, "fixture reserves multiple image rows");
	});
}
