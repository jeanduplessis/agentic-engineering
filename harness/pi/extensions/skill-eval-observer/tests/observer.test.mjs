import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import observer from "../index.ts";

test("observer is inert unless an eval configuration is supplied", () => {
  const old = process.env.SKILL_EVAL_OBSERVER_CONFIG;
  delete process.env.SKILL_EVAL_OBSERVER_CONFIG;
  try {
    observer({ on() { assert.fail("No hooks should be installed"); } });
  } finally {
    if (old !== undefined) process.env.SKILL_EVAL_OBSERVER_CONFIG = old;
  }
});

test("captures only catalog and profile metadata; limits reads to fixture and target", () => {
  const root = mkdtempSync(join(tmpdir(), "skill-eval-observer-"));
  const old = process.env.SKILL_EVAL_OBSERVER_CONFIG;
  const workspace = join(root, "workspace");
  mkdirSync(workspace);
  const skill = join(root, "SKILL.md");
  const local = join(workspace, "design.md");
  const outside = join(root, "private.txt");
  writeFileSync(skill, "skill body");
  writeFileSync(local, "fixture");
  writeFileSync(outside, "synthetic private data");
  symlinkSync(outside, join(workspace, "escape"));
  symlinkSync(skill, join(workspace, "target-alias"));
  const config = join(root, "config.json");
  const contextPath = join(root, "observer-context.jsonl");
  writeFileSync(config, JSON.stringify({ skill_path: skill, workspace, context_path: contextPath }));
  process.env.SKILL_EVAL_OBSERVER_CONFIG = config;
  try {
    const handlers = new Map();
    observer({
      on(name, handler) { handlers.set(name, handler); },
      getActiveTools() { return ["read"]; },
      getAllTools() { return [{ name: "read", sourceInfo: { source: "builtin" } }]; },
      getThinkingLevel() { return "high"; },
    });
    const catalog = `<available_skills><skill><name>demo</name><description>Demo</description><location>${skill}</location></skill></available_skills>`;
    let captured = "";
    const write = process.stdout.write;
    process.stdout.write = (chunk) => { captured += chunk; return true; };
    try {
      handlers.get("agent_start")({}, {
        getSystemPrompt() { return `private instructions\n${catalog}`; },
        model: { id: "demo", provider: "fake" },
      });
    } finally {
      process.stdout.write = write;
    }
    assert.equal(captured, "", "Pi redirects extension stdout; observer must use its own file");
    const record = readFileSync(contextPath, "utf8");
    const event = JSON.parse(record);
    assert.deepEqual(event.catalogs, [catalog]);
    assert.equal(event.read_source, "builtin");
    assert.equal(event.system_prompt_sha256.length, 64);
    assert.ok(!record.includes("private instructions"));
    const read = handlers.get("tool_call");
    for (const path of [skill, local, "@design.md", "target-alias"]) {
      const event = { toolName: "read", input: { path } };
      assert.equal(read(event), undefined);
      assert.ok(event.input.path.startsWith("/"));
    }
    for (const path of [outside, "escape", "../private.txt", "missing.md"]) {
      assert.equal(read({ toolName: "read", input: { path } }).block, true);
    }
    assert.equal(read({ toolName: "bash", input: { command: "pwd" } }).block, true);
  } finally {
    if (old === undefined) delete process.env.SKILL_EVAL_OBSERVER_CONFIG;
    else process.env.SKILL_EVAL_OBSERVER_CONFIG = old;
    rmSync(root, { recursive: true, force: true });
  }
});
