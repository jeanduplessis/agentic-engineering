import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const COMPACTION_REASONS = ["manual", "threshold", "overflow"] as const;
export const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"] as const;

export interface CompactionModelConfig {
	provider: string;
	modelId: string;
	thinkingLevel?: (typeof THINKING_LEVELS)[number];
	reasons: (typeof COMPACTION_REASONS)[number][];
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function section(settings: unknown): Record<string, unknown> | false | undefined {
	if (!isRecord(settings)) throw new Error("Settings must be a JSON object");
	const value = settings.compactionModel;
	if (value === undefined || value === false || isRecord(value)) return value;
	throw new Error("compactionModel must be an object or false");
}

export function resolveConfig(globalSettings: unknown, projectSettings: unknown = {}): CompactionModelConfig | null {
	const project = section(projectSettings);
	if (project === false) return null;
	const global = section(globalSettings);
	const config = { ...(global || {}), ...(project || {}) };
	if (config.enabled === false || (!global && !project)) return null;
	if (config.enabled !== undefined && config.enabled !== true) {
		throw new Error("compactionModel.enabled must be a boolean");
	}
	if (typeof config.model !== "string") throw new Error("compactionModel.model must be provider/model");
	const reference = config.model.trim();
	const separator = reference.indexOf("/");
	const provider = reference.slice(0, separator).trim();
	const modelId = reference.slice(separator + 1).trim();
	if (separator < 1 || !provider || !modelId || /\s/.test(provider + modelId)) {
		throw new Error("compactionModel.model must be provider/model");
	}

	const thinkingLevel = config.thinkingLevel ?? undefined;
	if (thinkingLevel !== undefined && !THINKING_LEVELS.some((level) => level === thinkingLevel)) {
		throw new Error("Invalid compactionModel.thinkingLevel");
	}
	const reasons = config.reasons === undefined ? COMPACTION_REASONS : config.reasons;
	if (!Array.isArray(reasons) || !reasons.every((reason) => COMPACTION_REASONS.includes(reason))) {
		throw new Error("compactionModel.reasons must contain only manual, threshold, or overflow");
	}
	return {
		provider,
		modelId,
		thinkingLevel: thinkingLevel as CompactionModelConfig["thinkingLevel"],
		reasons: [...new Set(reasons)],
	};
}

async function readSettings(path: string): Promise<unknown> {
	let text: string;
	try {
		text = await readFile(path, "utf8");
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return {};
		throw new Error("Could not read compaction model settings");
	}
	try {
		return JSON.parse(text);
	} catch {
		// Do not include parser errors: they can quote unrelated settings/secrets.
		throw new Error("Compaction model settings must be valid JSON");
	}
}

export async function loadConfig(
	agentDir: string,
	cwd: string,
	projectTrusted: boolean,
	configDirName: string,
): Promise<CompactionModelConfig | null> {
	const globalSettings = await readSettings(join(agentDir, "settings.json"));
	// Do not even read project-local configuration before Pi grants trust.
	const projectSettings = projectTrusted ? await readSettings(join(cwd, configDirName, "settings.json")) : {};
	return resolveConfig(globalSettings, projectSettings);
}
