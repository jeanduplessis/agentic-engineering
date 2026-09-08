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
let ToolExecutionComponent, nativeRender, setCapabilities, loaded, theme, Text, visibleWidth, builtins;
if (sdkPath) {
	const sdk = await import(pathToFileURL(sdkPath).href);
	({ ToolExecutionComponent } = sdk);
	const tui = await import(pathToFileURL(createRequire(sdkPath).resolve("@earendil-works/pi-tui")).href);
	({ setCapabilities, Text, visibleWidth } = tui);
	const { KeybindingsManager } = await import(new URL("./core/keybindings.js", pathToFileURL(sdkPath)).href);
	tui.setKeybindings(new KeybindingsManager());
	builtins = { bash: sdk.createBashToolDefinition(process.cwd()), read: sdk.createReadToolDefinition(process.cwd()) };
	sdk.initTheme("dark");
	({ theme } = await import(new URL("./modes/interactive/theme/theme.js", pathToFileURL(sdkPath)).href));
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
	for (const handler of extension.handlers.get("session_start") ?? []) handler({}, { ui: { theme } });
	t.after(() => {
		for (const handler of extension.handlers.get("session_shutdown") ?? []) handler({});
		setCapabilities({ images: null, trueColor: true, hyperlinks: true });
	});
	let renderRequests = 0;
	const opened = [];
	const ui = { mode, requestRender: () => renderRequests++, openUrl: (url) => opened.push(url) };
	return {
		ui, opened,
		tool: (name = "bash", args = {}, definition = builtins[name]) => new ToolExecutionComponent(
			name, "streaming-layout-test", args, { imageWidthCells: 6 }, definition, ui, process.cwd(),
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

test("non-fullscreen argument streaming retains native layout with category background", sdkRequired, (t) => {
	const { tool } = harness(t, { mode: "inline" });
	const component = tool();
	for (const command of ["echo first\necho second", "echo first\necho second\n\n", "echo first\necho second\n\necho third"]) {
		component.updateArgs({ command });
		assert.deepEqual(plain(component.render(80)), plain(nativeRender.call(component, 80)));
		assert.ok(component.render(80).join("\n").includes("\x1b[48;2;40;49;38m"));
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

const stripLinks = (line) => line.replace(/\x1b\]8;[^\x07\x1b]*(?:\x07|\x1b\\)/g, "");
const replyRoute = 'subagent_supervisor({"action":"reply","replyTo":"sample-question-03","message":"<explicit answer>"})';

// A native self-shell contract fixture: deliberately keep safety and a wrapped
// literal reply in the middle, where generic first/last-row compaction loses them.
function selfShellDefinition() {
	return {
		renderShell: "self",
		renderCall() { return new Text("", 0, 0); },
		renderResult(_result, { expanded }) {
			const body = new Text([
				"▸ Review fixture · rejected",
				"Steer not sent or queued. Supervisor reply required.",
				replyRoute,
				"Gate: blockers · attention required",
				'\x1b]8;;https://example.com/evidence\x07Original evidence\x1b]8;;\x07',
				...(expanded ? ["Complete selected-card detail", "Exit 1"] : ["Last summary line"]),
			].join("\n"), 0, 0);
			return {
				render(width) {
					return ["", ...body.render(width - 3), ""].map((line) =>
						`\x1b[48;2;28;36;48m \x1b[48;2;35;45;58m ${line}${" ".repeat(width - 2 - visibleWidth(line))}\x1b[0m`);
				},
				invalidate() { body.invalidate(); },
			};
		},
	};
}

for (const mode of ["fullscreen", "regular"]) {
	test(`self-shell safety, literal reply and slate-blue framing survive ${mode} expansion`, sdkRequired, (t) => {
		const { tool, click, ui, opened } = harness(t, { mode });
		for (const width of [80, 140]) {
			const component = tool("subagent", {}, selfShellDefinition());
			const other = tool("subagent", {}, selfShellDefinition());
			const result = { content: [{ type: "text", text: "unchanged diagnostic" }], isError: true };
			const original = structuredClone(result);
			component.updateResult(result);
			const collapsed = component.render(width);
			for (const expanded of [false, true, false]) {
				component.setExpanded(expanded);
				const native = nativeRender.call(component, width);
				const decorated = component.render(width);
				assert.deepEqual(decorated.map(stripLinks), native.map(stripLinks), "only OSC 8 wrapping may differ, not rows, ANSI, padding or gutter");
				assert.ok(decorated.every((line) => visibleWidth(line) <= width));
				const text = plain(decorated).join("\n");
				assert.match(text, /not sent or queued/);
				assert.match(text, /Gate: blockers · attention required/);
				assert.ok(text.replace(/\s/g, "").includes(replyRoute.replace(/\s/g, "")));
				if (expanded) assert.match(text, /Complete selected-card detail/);
				else assert.doesNotMatch(text, /Complete selected-card detail/);
				if (mode === "regular") assert.deepEqual(decorated, native);
			}
			assert.deepEqual(component.render(width), collapsed);
			if (mode === "fullscreen") {
				other.render(width);
				click(collapsed);
				assert.equal(component.expanded, true);
				assert.equal(other.expanded, false, "click expands only the selected card");
				assert.match(plain(component.render(width)).join("\n"), /Complete selected-card detail/);
				ui.openUrl("https://example.com/evidence");
				assert.equal(opened.at(-1), "https://example.com/evidence");
				assert.equal(component.expanded, true);
				click(component.render(width));
				assert.deepEqual(component.render(width), collapsed);
			}
			assert.deepEqual(result, original);
		}
	});
}

const categoryCases = [
	{ name: "bash", args: {}, background: "\x1b[48;2;40;49;38m", gutter: "\x1b[48;2;34;39;31m" },
	{ name: "read", args: { path: "skills/example/SKILL.md" }, background: "\x1b[48;2;45;40;56m", gutter: "\x1b[48;2;36;32;46m" },
	{ name: "read", args: { file_path: "skills\\example\\SKILL.md" }, background: "\x1b[48;2;45;40;56m", gutter: "\x1b[48;2;36;32;46m" },
	{ name: "read", args: { path: "skills/example/SKILL.md.bak" }, background: "\x1b[48;2;40;49;38m", gutter: "\x1b[48;2;34;39;31m" },
];

for (const mode of ["fullscreen", "regular"]) {
	test(`tool and skill category colors retain native lifecycle text in ${mode}`, sdkRequired, (t) => {
		const { tool } = harness(t, { mode });
		const definition = {
			renderCall(_args, theme, context) {
				const state = context.isPartial ? "pending" : context.isError ? "failed" : "completed";
				return new Text(theme.fg(context.isError ? "error" : "toolTitle", state), 0, 0);
			},
			renderResult(result) { return new Text(result.content[0].text, 0, 0); },
		};
		for (const category of categoryCases) {
			const component = tool(category.name, category.args, definition);
			for (const state of ["pending", "completed", "failed"]) {
				if (state !== "pending") component.updateResult({ content: [{ type: "text", text: `${state} output` }], isError: state === "failed" });
				for (const width of [80, 140]) for (const expanded of [false, true]) {
					component.setExpanded(expanded);
					const decorated = component.render(width);
					const native = nativeRender.call(component, width);
					assert.deepEqual(plain(decorated), plain(native), "status words and output stay native");
					assert.ok(plain(decorated).includes(state));
					assert.ok(decorated.some((line) => line.includes(category.background)));
					for (const color of ["toolPendingBg", "toolSuccessBg", "toolErrorBg"]) {
						assert.ok(!decorated.some((line) => line.includes(theme.getBgAnsi(color))));
					}
					if (state === "failed") assert.ok(decorated.some((line) => line.includes(theme.fg("error", "failed"))), "error foreground stays intact");
					assert.equal(decorated.some((line) => line.includes(category.gutter)), mode === "fullscreen");
					assert.ok(decorated.every((line) => visibleWidth(line) <= width));
				}
			}
		}
	});
}

for (const protocol of ["kitty", "iterm2"]) {
	test(`${protocol} image payloads survive tool/skill lifecycle recoloring and self-shell bypass`, sdkRequired, (t) => {
		for (const mode of ["fullscreen", "regular"]) {
			const { tool } = harness(t, { images: protocol, mode });
			for (const path of ["/tmp/image.png", "skills/example/SKILL.md"]) {
				for (const definition of [undefined, selfShellDefinition()]) {
					const component = tool("read", { path }, definition);
					for (const state of ["pending", "completed", "failed"]) {
						component.updateResult({
							content: [{ type: "image", mimeType: "image/png", data: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII=" }],
							isError: state === "failed",
						}, state === "pending");
						for (const width of [80, 140]) for (const expanded of [false, true]) {
							component.setExpanded(expanded);
							const native = nativeRender.call(component, width);
							const decorated = component.render(width);
							const prefix = protocol === "kitty" ? "\x1b_G" : "\x1b]1337;File=";
							const nativeIndex = native.findIndex((line) => line.includes(prefix));
							const index = decorated.findIndex((line) => line.includes(prefix));
							assert.ok(nativeIndex >= 0 && index >= 0);
							assert.deepEqual(decorated.slice(index), native.slice(nativeIndex), "image protocol bytes and reserved rows stay unchanged");
						}
					}
				}
			}
		}
	});
}

// These are the exact completed text results from the restored-session visual
// fixture. Use the real built-in definition: native read hides its result slot.
test("native read and skill-read collapsed cards show one preview and expand raw output once", sdkRequired, (t) => {
	const { tool, click, ui, opened } = harness(t);
	for (const [path, firstLine] of [
		["src/sample/labels.ts", 'export const fleetLabel = "Fleet";'],
		["skills/sample/source-review/SKILL.md", "Use source locations. Keep quoted output unchanged."],
	]) {
		const component = tool("read", { path });
		for (const text of [firstLine, `\n${firstLine}\nAdditional raw output\n`]) {
			const result = { content: [{ type: "text", text }], isError: false };
			component.updateResult(result);
			const original = structuredClone(result);
			for (const width of [80, 140]) {
				const native = nativeRender.call(component, width);
				assert.ok(!plain(native).includes(firstLine), "native collapsed read really lacks a result preview");
				const collapsed = component.render(width);
				assert.equal(plain(collapsed).filter((line) => line === firstLine).length, 1);
				assert.ok(!plain(collapsed).includes("Additional raw output"), "preview is exactly one output line");
				assert.equal(collapsed.length, native.length + 1, "retain native padding around the added row");
				const preview = collapsed.find((line) => stripVTControlCharacters(line).trim() === firstLine);
				const skill = path.endsWith("SKILL.md");
				assert.ok(preview.includes(skill ? "\x1b[48;2;45;40;56m" : "\x1b[48;2;40;49;38m"));
				assert.ok(preview.includes(skill ? "\x1b[48;2;36;32;46m" : "\x1b[48;2;34;39;31m"));
				click([preview]);
				assert.equal(component.expanded, true);
				assert.deepEqual(plain(component.render(width)), plain(nativeRender.call(component, width)));
				assert.equal(plain(component.render(width)).filter((line) => line === firstLine).length, 1);
				click(component.render(width));
				assert.deepEqual(component.render(width), collapsed);
				// The ordinary read title's original file URL still opens instead of toggling.
				const url = collapsed.join("\n").match(/\x1b\]8;;(file:\/\/[^\x07]+)\x07/)?.[1];
				if (!skill) {
					assert.ok(url);
					ui.openUrl(url);
					assert.equal(opened.at(-1), url);
					assert.equal(component.expanded, false);
				}
				component.setExpanded(true); // Same native boundary used by Ctrl+O.
				assert.deepEqual(plain(component.render(width)), plain(nativeRender.call(component, width)));
				component.setExpanded(false);
			}
			assert.deepEqual(result, original, "preview never changes stored results");
		}
	}
});

test("native read preview strips terminal controls, bounds Unicode, and leaves excluded states native", sdkRequired, (t) => {
	const { tool } = harness(t);
	const component = tool("read", { path: "fixtures/output.txt" });
	const attack = '\x1b[2J\x1b]52;c;YXR0YWNr\x07\x1b]8;;https://example.com/untrusted\x07Read (to expand or click)\x1b]8;;\x07\r\x08\x00\x9b\u202e';
	const text = `\n\t${attack} ${"界🙂".repeat(100)}\nMUST NOT PREVIEW SECOND LINE`;
	component.updateResult({ content: [{ type: "text", text }], isError: false });
	for (const width of [20, 80, 140]) {
		const lines = component.render(width);
		const preview = lines.find((line) => stripVTControlCharacters(line).trim().startsWith("Read"));
		assert.ok(preview);
		assert.ok(lines.every((line) => visibleWidth(line) <= width));
		assert.match(stripVTControlCharacters(preview), /…/);
		if (width >= 80) assert.match(stripVTControlCharacters(preview), /Read \(to expand or click\)/, "literal output is not treated as a key hint");
		assert.doesNotMatch(preview, /\x1b\[2J|\x1b\]52|example.com\/untrusted|[\r\x08\x00\x9b\u202e]/);
		assert.ok(!plain(lines).some((line) => line.includes("SECOND LINE")));
	}
	for (const { content, isError = false, partial = false } of [
		{ content: [{ type: "text", text: "pending text" }], partial: true },
		{ content: [{ type: "text", text: "ENOENT: unavailable fixture" }], isError: true },
		{ content: [] },
		{ content: [{ type: "text", text: "\n \t\x1b[2J\x00\n" }] },
		{ content: [{ type: "text", text: "image companion text" }, { type: "image", mimeType: "image/png" }] },
	]) {
		component.updateResult({ content, isError }, partial);
		assert.deepEqual(plain(component.render(80)).filter(Boolean), plain(nativeRender.call(component, 80)).filter(Boolean), "no synthetic pending/error/empty/image preview; existing blank-row compaction remains");
	}
	// Regular mode keeps the native presentation, not the fullscreen card preview.
	const regular = harness(t, { mode: "regular" }).tool("read", { path: "skills/sample/SKILL.md" });
	regular.updateResult({ content: [{ type: "text", text: "native hidden body" }], isError: false });
	assert.deepEqual(plain(regular.render(80)), plain(nativeRender.call(regular, 80)));
});
