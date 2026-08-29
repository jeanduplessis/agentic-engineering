import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { basename, resolve, sep } from "node:path";
import { parseFrontmatter, parseSkillBlock } from "@earendil-works/pi-coding-agent";

export type LoadedSkillCatalogEntry = {
	name: string;
	filePath: string;
};

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
	return typeof value === "object" && value !== null;
}

function messageText(content: unknown): string | undefined {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return undefined;
	return content
		.filter((part): part is UnknownRecord => isRecord(part) && part.type === "text")
		.map((part) => (typeof part.text === "string" ? part.text : ""))
		.join("");
}

/** Extract the name using Pi's expanded /skill:name format. */
export function explicitSkillName(text: string): string | undefined {
	return parseSkillBlock(text)?.name;
}

function normalizeReadPath(path: string, cwd: string): string {
	let normalized = path.startsWith("@") ? path.slice(1) : path;
	if (normalized === "~") {
		normalized = homedir();
	} else if (normalized.startsWith(`~${sep}`) || normalized.startsWith("~/")) {
		normalized = resolve(homedir(), normalized.slice(2));
	}
	return resolve(cwd, normalized);
}

function skillNameFromRead(content: unknown): string | undefined {
	const text = messageText(content);
	if (!text) return undefined;
	try {
		const { frontmatter } = parseFrontmatter<UnknownRecord>(text);
		if (
			isRecord(frontmatter) &&
			typeof frontmatter.name === "string" &&
			typeof frontmatter.description === "string" &&
			frontmatter.description.trim()
		) {
			return frontmatter.name;
		}
	} catch {
		// A malformed or truncated header is not evidence of a loaded skill.
	}
	return undefined;
}

/**
 * Return skills whose instructions are represented in the supplied context entries.
 * Entries should come from SessionManager.buildContextEntries() so compaction and tree
 * navigation are already reflected. Only path identity is read from disk; uncatalogued
 * skill names come from the saved tool output, not the file's current contents.
 */
export function collectLoadedSkillNames(
	entries: readonly unknown[],
	catalog: readonly LoadedSkillCatalogEntry[],
	cwd: string,
): string[] {
	const canonicalPaths = new Map<string, string>();
	const canonicalPath = (path: string): string => {
		const cached = canonicalPaths.get(path);
		if (cached !== undefined) return cached;
		let canonical = path;
		try {
			canonical = realpathSync(path);
		} catch {
			// Historical reads still count when their original path no longer exists.
		}
		canonicalPaths.set(path, canonical);
		return canonical;
	};
	const skillByPath = new Map<string, string>();
	for (const skill of catalog) {
		if (!skill.name || !skill.filePath) continue;
		const path = normalizeReadPath(skill.filePath, cwd);
		skillByPath.set(path, skill.name);
		skillByPath.set(canonicalPath(path), skill.name);
	}

	const loaded: string[] = [];
	const seen = new Set<string>();
	const pendingReads = new Map<string, { name?: string }>();
	const add = (name: string) => {
		name = name.trim();
		// Names from read output must not inject terminal controls or extra rows.
		if (!name || /[\x00-\x1f\x7f-\x9f]/.test(name) || seen.has(name)) return;
		seen.add(name);
		loaded.push(name);
	};

	for (const entry of entries) {
		if (!isRecord(entry) || entry.type !== "message" || !isRecord(entry.message)) continue;
		const message = entry.message;

		if (message.role === "user") {
			const name = explicitSkillName(messageText(message.content) ?? "");
			if (name) add(name);
			continue;
		}

		if (message.role === "assistant" && Array.isArray(message.content)) {
			for (const part of message.content) {
				if (
					!isRecord(part) ||
					part.type !== "toolCall" ||
					part.name !== "read" ||
					typeof part.id !== "string" ||
					!isRecord(part.arguments) ||
					typeof part.arguments.path !== "string"
				) {
					continue;
				}
				const path = normalizeReadPath(part.arguments.path, cwd);
				const name = skillByPath.get(path) ?? skillByPath.get(canonicalPath(path));
				const offset = part.arguments.offset;
				const fromStart = offset === undefined || (typeof offset === "number" && offset <= 1);
				if (name || (basename(path) === "SKILL.md" && fromStart)) {
					pendingReads.set(part.id, { name });
				}
			}
			continue;
		}

		if (
			message.role === "toolResult" &&
			message.toolName === "read" &&
			typeof message.toolCallId === "string"
		) {
			const read = pendingReads.get(message.toolCallId);
			pendingReads.delete(message.toolCallId);
			if (read && message.isError === false) {
				const name = read.name ?? skillNameFromRead(message.content);
				if (name) add(name);
			}
		}
	}

	return loaded;
}
