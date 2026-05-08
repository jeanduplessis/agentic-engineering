import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const KNOWN_FRONTMATTER_FIELDS = new Set(["description", "argument-hint", "model", "thinking", "skill", "skills", "restore"]);
const VALID_THINKING_LEVELS = new Set(["off", "minimal", "low", "medium", "high", "xhigh"]);

export type ParsedCommand = {
	name: string;
	path: string;
	description?: string;
	argumentHint?: string;
	body: string;
	frontmatter: Record<string, string>;
	skills: string[];
	warnings: string[];
};

export function parseArgs(input: string): string[] {
	const args: string[] = [];
	let current = "";
	let quote: "'" | '"' | undefined;
	let escaping = false;

	for (const char of input) {
		if (escaping) {
			current += char;
			escaping = false;
			continue;
		}
		if (char === "\\") {
			escaping = true;
			continue;
		}
		if (quote) {
			if (char === quote) quote = undefined;
			else current += char;
			continue;
		}
		if (char === "'" || char === '"') {
			quote = char;
			continue;
		}
		if (/\s/.test(char)) {
			if (current.length > 0) {
				args.push(current);
				current = "";
			}
			continue;
		}
		current += char;
	}
	if (escaping) current += "\\";
	if (current.length > 0) args.push(current);
	return args;
}

export function substituteArguments(body: string, rawArgs: string): string {
	const parsedArgs = parseArgs(rawArgs);
	return body.replace(/\$(ARGUMENTS|@|[1-9][0-9]*)/g, (_match, token: string) => {
		if (token === "ARGUMENTS") return rawArgs;
		if (token === "@") return parsedArgs.join(" ");
		const index = Number.parseInt(token, 10) - 1;
		return parsedArgs[index] ?? "";
	});
}

export function parseCommandFile(path: string, name: string, content: string): ParsedCommand {
	const warnings: string[] = [];
	const frontmatter: Record<string, string> = {};
	let frontmatterSkills: string[] = [];
	let body = content;

	if (content.startsWith("---\n")) {
		const end = content.indexOf("\n---", 4);
		if (end >= 0) {
			const rawFrontmatter = content.slice(4, end).trim();
			body = content.slice(end + 4).replace(/^\r?\n/, "");
			frontmatterSkills = parseFrontmatter(rawFrontmatter, name, frontmatter, warnings);
		} else {
			warnings.push(`Unclosed frontmatter in /${name}; treating file as a plain prompt body.`);
		}
	}

	warnings.push(...unsupportedSyntaxWarnings(name, body));
	return {
		name,
		path,
		description: frontmatter.description,
		argumentHint: frontmatter["argument-hint"],
		body,
		frontmatter,
		skills: declaredSkills(frontmatter, frontmatterSkills),
		warnings,
	};
}

export function discoverCommands(commandDir: string): ParsedCommand[] {
	let entries;
	try {
		entries = readdirSync(commandDir, { withFileTypes: true });
	} catch {
		return [];
	}
	const commands: ParsedCommand[] = [];
	for (const entry of entries) {
		if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
		const path = join(commandDir, entry.name);
		const name = entry.name.slice(0, -3);
		commands.push(parseCommandFile(path, name, readFileSync(path, "utf8")));
	}
	return commands.sort((a, b) => a.name.localeCompare(b.name));
}

export function getDefaultCommandDir(): string {
	const sourceDir = realpathSync(dirname(fileURLToPath(import.meta.url)));
	return resolve(sourceDir, "..", "..", "commands");
}

export function resolveDeclaredSkill(skillName: string, cwd: string | undefined, commandDir: string): { content?: string; path?: string; error?: string } {
	const candidates = skillCandidates(skillName, cwd, commandDir);
	for (const path of candidates) {
		if (!existsSync(path)) continue;
		try {
			return { content: readFileSync(path, "utf8"), path };
		} catch {
			return { error: `Declared skill is not readable: ${skillName}` };
		}
	}
	return { error: `Declared skill does not resolve to a readable local skill: ${skillName}` };
}

export function resolveDeclaredModel(modelRef: string, modelRegistry: any): { model?: any; error?: string } {
	if (modelRef.includes("/")) {
		const [provider, ...rest] = modelRef.split("/");
		const id = rest.join("/");
		const model = modelRegistry.find?.(provider, id);
		if (!model) return { error: `Model is not available: ${modelRef}` };
		return { model };
	}
	const matches = (modelRegistry.getAll?.() ?? []).filter((model: any) => model.id === modelRef);
	if (matches.length === 1) return { model: matches[0] };
	if (matches.length > 1) {
		const refs = matches.map((model: any) => `${model.provider}/${model.id}`).join(", ");
		return { error: `Bare model id is ambiguous: ${modelRef}. Use one of: ${refs}` };
	}
	return { error: `Model is not available: ${modelRef}` };
}

export function registerExtendedCommands(pi: ExtensionAPI, commandDir = getDefaultCommandDir()): ParsedCommand[] {
	const commands = discoverCommands(commandDir);
	let pendingRestore: { model?: any; thinking?: string } | undefined;
	(pi as any).on?.("agent_end", async () => {
		if (!pendingRestore) return;
		const restore = pendingRestore;
		pendingRestore = undefined;
		if (restore.model) await (pi as any).setModel?.(restore.model);
		if (restore.thinking !== undefined) (pi as any).setThinkingLevel?.(restore.thinking);
	});
	for (const command of commands) {
		pi.registerCommand(command.name, {
			description: command.description,
			handler: async (args, ctx) => {
				for (const warning of command.warnings) ctx.ui.notify(warning, "warning");
				const restore = command.frontmatter.restore !== "false";
				const previousModel = (ctx as any).model;
				const previousThinking = (pi as any).getThinkingLevel?.();
				const skillContexts: Array<{ name: string; content: string; path?: string }> = [];

				for (const skill of command.skills) {
					const resolvedSkill = resolveDeclaredSkill(skill, (ctx as any).cwd, commandDir);
					if (!resolvedSkill.content) {
						ctx.ui.notify(resolvedSkill.error ?? `Could not resolve skill: ${skill}`, "error");
						return;
					}
					skillContexts.push({ name: skill, content: resolvedSkill.content, path: resolvedSkill.path });
				}

				if (command.frontmatter.model) {
					const resolved = resolveDeclaredModel(command.frontmatter.model, (ctx as any).modelRegistry);
					if (!resolved.model) {
						ctx.ui.notify(resolved.error ?? `Could not resolve model: ${command.frontmatter.model}`, "error");
						return;
					}
					if (restore) pendingRestore = { model: previousModel, thinking: previousThinking };
					const ok = await (pi as any).setModel(resolved.model);
					if (!ok) {
						pendingRestore = undefined;
						ctx.ui.notify(`Model is unavailable or missing API credentials: ${command.frontmatter.model}`, "error");
						return;
					}
				}

				if (command.frontmatter.thinking) {
					if (!VALID_THINKING_LEVELS.has(command.frontmatter.thinking)) {
						ctx.ui.notify(`Invalid thinking level: ${command.frontmatter.thinking}`, "error");
						return;
					}
					if (restore && !pendingRestore) pendingRestore = { model: previousModel, thinking: previousThinking };
					(pi as any).setThinkingLevel?.(command.frontmatter.thinking);
				}

				for (const skillContext of skillContexts) {
					(pi as any).sendMessage?.({
						customType: "extended-command-skill",
						content: `Skill context for /${command.name} (${skillContext.name})\nSource: ${skillContext.path ?? "unknown"}\n\n${skillContext.content}`,
						display: true,
						details: { command: command.name, skill: skillContext.name, path: skillContext.path },
					});
				}

				const rendered = substituteArguments(command.body, args ?? "");
				if (ctx.isIdle()) pi.sendUserMessage(rendered);
				else pi.sendUserMessage(rendered, { deliverAs: "followUp" });
			},
		});
	}
	return commands;
}

export default function extendedCommands(pi: ExtensionAPI) {
	registerExtendedCommands(pi);
}

function parseFrontmatter(rawFrontmatter: string, name: string, frontmatter: Record<string, string>, warnings: string[]): string[] {
	const skills: string[] = [];
	const lines = rawFrontmatter.split(/\r?\n/);
	for (let index = 0; index < lines.length; index++) {
		const line = lines[index];
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith("#")) continue;
		const match = trimmed.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
		if (!match) {
			warnings.push(`Unsupported frontmatter line in /${name}: ${trimmed}`);
			continue;
		}
		const key = match[1];
		const value = unquoteScalar(match[2] ?? "");
		frontmatter[key] = value;
		if (!KNOWN_FRONTMATTER_FIELDS.has(key)) warnings.push(`Unknown frontmatter field in /${name}: ${key}`);
		if (key !== "skills") continue;
		if (value) {
			warnings.push(`Unsupported skills frontmatter in /${name}; use an indented YAML list.`);
			continue;
		}
		while (index + 1 < lines.length) {
			const nextLine = lines[index + 1];
			const nextTrimmed = nextLine.trim();
			if (!nextTrimmed || nextTrimmed.startsWith("#")) {
				index++;
				continue;
			}
			if (!/^\s+/.test(nextLine)) break;
			index++;
			if (!nextTrimmed.startsWith("-")) {
				warnings.push(`Unsupported frontmatter line in /${name}: ${nextTrimmed}`);
				continue;
			}
			const skill = unquoteScalar(nextTrimmed.slice(1).trim());
			if (skill) skills.push(skill);
		}
	}
	return skills;
}

function declaredSkills(frontmatter: Record<string, string>, frontmatterSkills: string[]): string[] {
	const skills = [frontmatter.skill, ...frontmatterSkills].filter((skill): skill is string => Boolean(skill));
	return [...new Set(skills)];
}

function skillCandidates(skillName: string, cwd: string | undefined, commandDir: string): string[] {
	const candidates: string[] = [];
	const addAncestorSkills = (start: string | undefined, dirName: ".pi" | ".agents") => {
		if (!start) return;
		let current = resolve(start);
		while (true) {
			candidates.push(join(current, dirName, "skills", skillName, "SKILL.md"));
			const parent = dirname(current);
			if (parent === current) break;
			current = parent;
		}
	};
	candidates.push(resolve(commandDir, "..", "skills", skillName, "SKILL.md"));
	addAncestorSkills(cwd, ".pi");
	addAncestorSkills(cwd, ".agents");
	candidates.push(resolve(process.env.HOME ?? "", ".agents", "skills", skillName, "SKILL.md"));
	candidates.push(resolve(process.env.HOME ?? "", ".pi", "agent", "skills", skillName, "SKILL.md"));
	candidates.push(resolve(process.env.HOME ?? "", ".pi", "agent", "skills", `${skillName}.md`));
	return [...new Set(candidates)];
}

function unquoteScalar(value: string): string {
	const trimmed = value.trim();
	if (trimmed.length >= 2) {
		const first = trimmed[0];
		const last = trimmed[trimmed.length - 1];
		if ((first === '"' && last === '"') || (first === "'" && last === "'")) return trimmed.slice(1, -1);
	}
	return trimmed;
}

function unsupportedSyntaxWarnings(name: string, body: string): string[] {
	const warnings: string[] = [];
	if (/!`[^`]*`/.test(body)) warnings.push(`Unsupported shell expansion syntax is passed through in /${name}.`);
	if (/(^|\s)@[A-Za-z0-9_./~-]+/.test(body)) warnings.push(`Unsupported file expansion syntax is passed through in /${name}.`);
	return warnings;
}
