import { createHash } from "node:crypto";
import { appendFileSync, readFileSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, relative, resolve, sep } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** CLI-only observer. No hooks or side effects outside an explicit eval process. */
export default function (pi: ExtensionAPI) {
  const configPath = process.env.SKILL_EVAL_OBSERVER_CONFIG;
  if (!configPath) return;
  const config = JSON.parse(readFileSync(configPath, "utf8"));
  const skillPath = realpathSync(config.skill_path);
  const workspace = realpathSync(config.workspace);
  // Pi redirects extension stdout to stderr in JSON mode. Keep observer evidence separate.
  const emit = (event: object) => appendFileSync(config.context_path, `${JSON.stringify(event)}\n`, "utf8");

  pi.on("agent_start", (_event, ctx) => {
    const prompt = ctx.getSystemPrompt();
    // Capture the rendered catalog, never global instructions, auth, or provider payloads.
    const catalogs = prompt.match(/<available_skills>[\s\S]*?<\/available_skills>/g) ?? [];
    emit({
      type: "skill_eval_context",
      version: 1,
      catalogs,
      system_prompt_sha256: createHash("sha256").update(prompt).digest("hex"),
      tools: pi.getActiveTools(),
      read_source: pi.getAllTools().find((tool) => tool.name === "read")?.sourceInfo.source,
      provider: ctx.model?.provider,
      model: ctx.model?.id,
      thinking: pi.getThinkingLevel(),
    });
  });

  pi.on("tool_call", (event) => {
    if (event.toolName !== "read") {
      return { block: true, reason: "Trigger probes allow only read." };
    }
    try {
      const input = event.input as { path: string };
      // Pin the actual read to the same canonical path checked by this boundary.
      const raw = input.path.replace(/^@/, "");
      const expanded = raw === "~" ? homedir() : raw.startsWith("~/") ? resolve(homedir(), raw.slice(2)) : raw;
      const path = realpathSync(resolve(workspace, expanded));
      const local = relative(workspace, path);
      const insideWorkspace = local !== ".." && !local.startsWith(`..${sep}`) && !isAbsolute(local);
      if (path !== skillPath && !insideWorkspace) {
        return { block: true, reason: "Read is outside the trigger fixture and frozen skill." };
      }
      input.path = path;
    } catch {
      return { block: true, reason: "Read path is unavailable in this trigger probe." };
    }
  });
}
