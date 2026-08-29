import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, rm, symlink, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

// Use Pi's installed parsers and loader without installing dependencies or calling a model.
const require = createRequire(import.meta.url);
let sdkPath;
try {
	sdkPath = require.resolve("@earendil-works/pi-coding-agent");
} catch {
	try {
		const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
		sdkPath = require.resolve(join(globalRoot, "@earendil-works/pi-coding-agent"));
	} catch { /* Report an explicit skip when Pi is unavailable. */ }
}
const sdkRequired = { skip: !sdkPath && "Pi SDK is not installed" };
let sdk, loadExtensions, visibleWidth, collectLoadedSkillNames, explicitSkillName;
if (sdkPath) {
	const sdkRequire = createRequire(sdkPath);
	const { createJiti } = sdkRequire("jiti");
	const jiti = createJiti(import.meta.url, {
		alias: { "@earendil-works/pi-coding-agent": sdkPath },
	});
	({ collectLoadedSkillNames, explicitSkillName } = await jiti.import("../loaded-skills.ts"));
	sdk = await import(pathToFileURL(sdkPath).href);
	({ loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href));
	({ visibleWidth } = await import(pathToFileURL(sdkRequire.resolve("@earendil-works/pi-tui")).href));
}

const messageEntry = (message) => ({ type: "message", message });
const user = (content) => messageEntry({ role: "user", content, timestamp: 0 });
const toolCall = (id, path, args = {}) => messageEntry({
	role: "assistant",
	content: [{ type: "toolCall", id, name: "read", arguments: { path, ...args } }],
	provider: "test", model: "test", stopReason: "toolUse", timestamp: 0,
});
const toolResult = (id, text = "Instructions", isError = false) => messageEntry({
	role: "toolResult", toolCallId: id, toolName: "read", isError,
	content: [{ type: "text", text }], timestamp: 0,
});
const skillText = (name) => `---\nname: ${name}\ndescription: Fixture skill instructions\n---\nDo the fixture task.\n`;
const skillBlock = (name) => `<skill name="${name}" location="/skills/${name}/SKILL.md">\nInstructions\n</skill>`;

async function footerHarness(t, sessionManager, getCommands = () => [], theme = {
	fg: (_color, text) => text, italic: (text) => text,
}) {
	const loaded = await loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], process.cwd());
	assert.deepEqual(loaded.errors, []);
	assert.equal(loaded.extensions.length, 1);
	loaded.runtime.getCommands = getCommands;
	loaded.runtime.getSessionName = () => undefined;
	let footer;
	let renderRequests = 0;
	const ctx = {
		mode: "tui", cwd: sessionManager.getCwd(), sessionManager,
		getContextUsage: () => undefined,
		ui: {
			setFooter(factory) {
				footer?.dispose();
				footer = factory(
					{ requestRender: () => renderRequests++ },
					theme,
					{ getGitBranch: () => null, getExtensionStatuses: () => new Map(), onBranchChange: () => () => {} },
				);
			},
			notify() {},
		},
	};
	const extension = loaded.extensions[0];
	const emit = async (type, event = {}) => {
		const before = renderRequests;
		for (const handler of extension.handlers.get(type) ?? []) await handler(event, ctx);
		return renderRequests - before;
	};
	t.after(() => { footer?.dispose(); loaded.runtime.invalidate(); });
	await emit("session_start");
	await emit("resources_discover");
	return {
		emit,
		reinstall: () => extension.commands.get("custom-footer").handler("", ctx),
		render: (width = 120) => footer.render(width),
		skillRows: () => footer.render(120).filter((line) => line.trimStart().startsWith("◈ ")).map((line) => line.trim()),
	};
}

function commandsFor(catalog) {
	return catalog.map((skill) => ({ name: `skill:${skill.name}`, source: "skill", sourceInfo: { path: skill.filePath } }));
}

test("skill marker shares the metric symbol accent without recoloring skill names", sdkRequired, async (t) => {
	const sm = sdk.SessionManager.inMemory("/workspace");
	sm.appendMessage(user(skillBlock("example")).message);
	const colors = { thinkingLow: "\x1b[34m", dim: "\x1b[90m", text: "\x1b[37m" };
	const theme = {
		fg: (color, text) => `${colors[color] ?? colors.text}${text}\x1b[39m`,
		italic: (text) => text,
	};
	const h = await footerHarness(t, sm, () => [], theme);
	const lines = h.render();
	const rendered = lines.join("\n");
	assert.ok(rendered.includes(theme.fg("thinkingLow", "↑")));
	assert.ok(rendered.includes(theme.fg("thinkingLow", "◈ ")));
	assert.ok(rendered.includes(theme.fg("text", "example")));
	const skillsIndex = lines.findIndex((line) => line.includes("◈"));
	assert.ok(lines[skillsIndex - 1].includes(theme.fg("dim", "─".repeat(118))));
});

test("section dividers fill the footer width without stretching the model table", sdkRequired, async (t) => {
	const sm = sdk.SessionManager.inMemory("/workspace");
	const h = await footerHarness(t, sm);
	const dividerIndices = (lines) => lines.flatMap((line, index) => /^─+$/.test(line.trim()) ? [index] : []);
	assert.equal(dividerIndices(h.render()).length, 0);
	sm.appendMessage(user(skillBlock("example-with-a-long-name")).message);
	assert.equal(dividerIndices(h.render()).length, 1, "Skills get a divider even without a model table");
	for (const model of ["first", "second"]) {
		sm.appendMessage({ role: "assistant", content: [{ type: "text", text: "Done" }], provider: "test", model, stopReason: "stop", timestamp: 0 });
	}
	const compactLines = h.render(122);
	const compactModelsIndex = compactLines.findIndex((line) => line.trimStart().startsWith("Model"));
	const compactModelRows = compactLines.slice(compactModelsIndex).map((line) => line.trimEnd());
	for (const width of [20, 80, 160]) {
		const lines = h.render(width);
		const dividers = dividerIndices(lines);
		const skillsIndex = lines.findIndex((line) => line.trimStart().startsWith("◈"));
		const modelsIndex = lines.findIndex((line) => line.trimStart().startsWith("Model"));
		assert.deepEqual(dividers, [skillsIndex - 1, modelsIndex - 1]);
		assert.equal(lines[dividers[0]], lines[dividers[1]], "Both dividers have the same width and padding");
		assert.equal(lines[dividers[0]].trim(), "─".repeat(width - 2));
		assert.ok(lines.every((line) => visibleWidth(line) <= width), `width ${width}`);
		if (width > 122) {
			assert.deepEqual(lines.slice(modelsIndex).map((line) => line.trimEnd()), compactModelRows);
		}
	}
	sm.resetLeaf();
	await h.emit("session_tree");
	assert.deepEqual(h.skillRows(), []);
	const modelOnly = h.render(160);
	const remainingDividers = dividerIndices(modelOnly);
	assert.equal(remainingDividers.length, 1, "Only the model divider remains when skills leave context");
	assert.equal(modelOnly[remainingDividers[0]].trim(), "─".repeat(158));
});

test("reports explicit and successfully read skills once in first-load order", sdkRequired, () => {
	const cwd = "/workspace/project";
	const catalog = [
		{ name: "testing-principles", filePath: "/skills/testing-principles/SKILL.md" },
		{ name: "human-writing", filePath: `${cwd}/skills/human-writing/SKILL.md` },
	];
	const explicit = `${skillBlock("human-writing")}\n\nDraft the release notes`;
	const entries = [
		user([{ type: "text", text: explicit }]),
		toolCall("read-success", "/skills/testing-principles/SKILL.md"), toolResult("read-success"),
		toolCall("read-duplicate", "@skills/human-writing/SKILL.md"), toolResult("read-duplicate"),
	];
	assert.deepEqual(collectLoadedSkillNames(entries, catalog, cwd), ["human-writing", "testing-principles"]);
	assert.equal(explicitSkillName(skillBlock("known")), "known");
	assert.equal(explicitSkillName(`${skillBlock("known")}\n\nDo the work`), "known");
});

test("recognizes uncatalogued skills from returned frontmatter, not their directory name or current file", sdkRequired, async (t) => {
	const root = await mkdtemp(join(tmpdir(), "footer-uncatalogued-"));
	t.after(() => rm(root, { recursive: true, force: true }));
	const path = join(root, "SKILL.md");
	const text = '\uFEFF---\r\nname: "pi-subagents" # package skill\r\ndescription: >\r\n  Route work to subagents.\r\n---\r\nInstructions\r\n';
	await writeFile(path, text);
	const output = await sdk.createReadToolDefinition(root).execute("uncatalogued", { path });
	// Context contains the old read even if the file is later edited or removed.
	await rm(path);
	const entries = [
		toolCall("known", "/skills/testing-principles/SKILL.md"), toolResult("known"),
		toolCall("uncatalogued", path), toolResult("uncatalogued", output.content[0].text),
		toolCall("duplicate", path), toolResult("duplicate", text),
	];
	assert.deepEqual(collectLoadedSkillNames(entries, [{ name: "testing-principles", filePath: "/skills/testing-principles/SKILL.md" }], root), [
		"testing-principles", "pi-subagents",
	]);
});

test("ignores failed, unfinished, unrelated, malformed, and non-header reads", sdkRequired, () => {
	const path = "/skills/known/SKILL.md";
	const catalog = [{ name: "known", filePath: path }];
	const entries = [
		user("Please use the known skill"),
		user('<skill name="known">partial'),
		toolCall("failed", path), toolResult("failed", "Error", true),
		toolCall("unfinished", path),
		toolResult("orphan", skillText("orphan")),
	];
	for (const [id, readPath, text, args, failed] of [
		["invalid", "/other/SKILL.md", "---\nname: [invalid\ndescription: test\n---"],
		["not-skill", "/other/README.md", skillText("not-skill")],
		["no-name", "/other/SKILL.md", "---\ndescription: Only a description\n---\nText"],
		["no-description", "/other/SKILL.md", "---\nname: unnamed\n---\nText"],
		["empty", "/other/SKILL.md", ""],
		["non-header", "/other/SKILL.md", skillText("example-in-body"), { offset: 20 }],
		["unknown-failure", "/other/SKILL.md", skillText("failed"), {}, true],
		["control-name", "/other/SKILL.md", '---\nname: "bad\\u001b[31m"\ndescription: test\n---\nText'],
	]) {
		entries.push(toolCall(id, readPath, args), toolResult(id, text, failed));
	}
	assert.deepEqual(collectLoadedSkillNames(entries, catalog, "/workspace"), []);
});

test("matches symlink and target reads, including excerpts without frontmatter", sdkRequired, async (t) => {
	const root = await mkdtemp(join(tmpdir(), "footer-symlink-"));
	t.after(() => rm(root, { recursive: true, force: true }));
	await mkdir(join(root, "source"));
	const target = join(root, "source", "SKILL.md");
	const alias = join(root, "linked", "SKILL.md");
	await writeFile(target, skillText("example"));
	await symlink(join(root, "source"), join(root, "linked"), process.platform === "win32" ? "junction" : "dir");
	const read = sdk.createReadToolDefinition(root);
	for (const [advertised, requested] of [[alias, target], [target, alias]]) {
		const output = await read.execute("excerpt", { path: requested, offset: 5 });
		const entries = [toolCall("excerpt", requested, { offset: 5 }), toolResult("excerpt", output.content[0].text)];
		const catalog = [{ name: "example", filePath: advertised }];
		assert.deepEqual(collectLoadedSkillNames(entries, catalog, root), ["example"]);
	}
	await rm(target);
	assert.deepEqual(collectLoadedSkillNames([toolCall("missing", alias), toolResult("missing")], [{ name: "example", filePath: alias }], root), ["example"]);
});

test("footer sees skills contributed after discovery and refreshes when only the catalog changes", sdkRequired, async (t) => {
	const sm = sdk.SessionManager.inMemory("/workspace");
	const skill = { name: "contributed", filePath: "/skills/contributed/SKILL.md" };
	sm.appendMessage(toolCall("resumed-read", skill.filePath, { offset: 5 }).message);
	sm.appendMessage(toolResult("resumed-read").message);
	let commands = [];
	const h = await footerHarness(t, sm, () => commands);
	assert.deepEqual(h.skillRows(), []);
	// Pi applies returned skillPaths only after every resources_discover handler has run.
	commands = commandsFor([skill]);
	assert.deepEqual(h.skillRows(), ["◈ contributed"]);
	await h.reinstall();
	assert.deepEqual(h.skillRows(), ["◈ contributed"]);
	assert.ok(await h.emit("before_agent_start", { systemPromptOptions: { skills: [skill] } }) > 0);
	commands = [];
	assert.deepEqual(h.skillRows(), [], "Catalog removal must invalidate cached names without a new context leaf");
	commands = commandsFor([skill]);
	assert.deepEqual(h.skillRows(), ["◈ contributed"]);
	for (const width of [0, 1, 2, 3, 10, 20, 40, 80, 120]) {
		assert.ok(h.render(width).every((line) => visibleWidth(line) <= width), `width ${width}`);
	}
});

test("footer follows completed reads, compaction, tree navigation, and fresh session restoration", sdkRequired, async (t) => {
	const sm = sdk.SessionManager.inMemory("/workspace");
	const skill = { name: "testing-principles", filePath: "/skills/testing-principles/SKILL.md" };
	const getCommands = () => commandsFor([skill]);
	const h = await footerHarness(t, sm, getCommands);
	assert.deepEqual(h.skillRows(), []);
	sm.appendMessage(user("Use testing-principles").message);
	sm.appendMessage(toolCall("known", skill.filePath).message);
	assert.deepEqual(h.skillRows(), []);
	const beforeUnknown = sm.appendMessage(toolResult("known").message);
	assert.ok(await h.emit("turn_end") > 0);
	assert.deepEqual(h.skillRows(), ["◈ testing-principles"]);
	const firstKept = sm.appendMessage(toolCall("unknown", "/package/pi-subagents/SKILL.md").message);
	sm.appendMessage(toolResult("unknown", skillText("pi-subagents")).message);
	await h.emit("turn_end");
	assert.deepEqual(h.skillRows(), ["◈ testing-principles • pi-subagents"]);
	sm.appendMessage(user(skillBlock("explicit")).message);
	assert.ok(await h.emit("turn_start") > 0);
	assert.deepEqual(h.skillRows(), ["◈ testing-principles • pi-subagents • explicit"]);
	const compacted = sm.appendCompaction("Previously used testing-principles", firstKept, 10000);
	assert.ok(await h.emit("session_compact") > 0);
	assert.deepEqual(h.skillRows(), ["◈ pi-subagents • explicit"]);
	sm.branch(beforeUnknown);
	assert.ok(await h.emit("session_tree") > 0);
	assert.deepEqual(h.skillRows(), ["◈ testing-principles"]);
	sm.branch(compacted);
	await h.emit("session_tree");
	const restored = await footerHarness(t, sm, getCommands);
	assert.deepEqual(restored.skillRows(), ["◈ pi-subagents • explicit"]);
	const next = sm.appendMessage(user("Unrelated next request").message);
	sm.appendCompaction("All earlier skills summarized", next, 10000);
	await restored.emit("session_compact");
	assert.deepEqual(restored.skillRows(), []);
	const fresh = await footerHarness(t, sdk.SessionManager.inMemory("/workspace"), getCommands);
	assert.deepEqual(fresh.skillRows(), []);
});
