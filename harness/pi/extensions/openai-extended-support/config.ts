import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import { existsSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import {
  DEFAULT_SERVICE_TIER,
  PACKAGE_NAME,
  SUPPORTED_PROVIDERS,
  type OpenAIExtendedSupportConfig,
  type PriorityTarget,
  type ResolvedConfigPath,
} from "./types";

export const DEFAULT_USAGE_CONFIG = {
  enabled: true,
  refreshIntervalMs: 60_000,
  showOnlyOnSubscriptionModels: true,
  showResetTimes: true,
  showStatus: true,
} as const;

export const DEFAULT_CONFIG: OpenAIExtendedSupportConfig = {
  enabled: false,
  persistState: true,
  targets: [
    { provider: "openai", model: "gpt-5.4", serviceTier: DEFAULT_SERVICE_TIER },
    { provider: "openai", model: "gpt-5.5", serviceTier: DEFAULT_SERVICE_TIER },
    { provider: "openai", model: "gpt-5.6", serviceTier: DEFAULT_SERVICE_TIER },
    {
      provider: "openai",
      model: "gpt-5.6-sol",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai",
      model: "gpt-5.6-terra",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai",
      model: "gpt-5.6-luna",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.4",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.5",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.6",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.6-sol",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.6-terra",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
    {
      provider: "openai-codex",
      model: "gpt-5.6-luna",
      serviceTier: DEFAULT_SERVICE_TIER,
    },
  ],
  usage: { ...DEFAULT_USAGE_CONFIG },
};

const SUPPORTED_PROVIDER_SET = new Set<string>(SUPPORTED_PROVIDERS);

type RecordLike = Record<string, unknown>;

function isRecord(value: unknown): value is RecordLike {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function cloneTarget(target: PriorityTarget): PriorityTarget {
  return {
    provider: target.provider,
    model: target.model,
    serviceTier: target.serviceTier ?? DEFAULT_SERVICE_TIER,
  };
}

function cloneUsage(
  usage: OpenAIExtendedSupportConfig["usage"] | undefined,
): OpenAIExtendedSupportConfig["usage"] {
  const source = usage ?? DEFAULT_USAGE_CONFIG;
  return {
    enabled: source.enabled,
    refreshIntervalMs: source.refreshIntervalMs,
    showOnlyOnSubscriptionModels: source.showOnlyOnSubscriptionModels,
    showResetTimes: source.showResetTimes,
    showStatus: source.showStatus,
  };
}

export function cloneConfig(
  config: OpenAIExtendedSupportConfig = DEFAULT_CONFIG,
): OpenAIExtendedSupportConfig {
  return {
    enabled: config.enabled,
    persistState: config.persistState ?? true,
    targets: config.targets.map(cloneTarget),
    usage: cloneUsage(config.usage),
  };
}

/** Preserve explicitly configured targets; defaults are applied only when absent. */
export function syncSupportedTargets(
  config: OpenAIExtendedSupportConfig,
): OpenAIExtendedSupportConfig {
  return cloneConfig(config);
}

const SAFE_SERVICE_TIER_PATTERN = /^[a-z0-9][a-z0-9_-]{0,31}$/i;

function normalizeServiceTier(rawServiceTier: unknown): string {
  if (typeof rawServiceTier !== "string") return DEFAULT_SERVICE_TIER;
  const serviceTier = rawServiceTier.trim().toLowerCase();
  return SAFE_SERVICE_TIER_PATTERN.test(serviceTier)
    ? serviceTier
    : DEFAULT_SERVICE_TIER;
}

function normalizeTarget(
  rawTarget: unknown,
): PriorityTarget | undefined {
  if (!isRecord(rawTarget)) return undefined;

  const rawProvider = rawTarget.provider;
  const rawModel = rawTarget.model;

  if (typeof rawProvider !== "string" || typeof rawModel !== "string") {
    return undefined;
  }

  const provider = rawProvider.trim().toLowerCase();
  const model = rawModel.trim();

  if (
    !provider ||
    !model ||
    model.length > 200 ||
    /[\u0000-\u001f\u007f-\u009f]/.test(model) ||
    !SUPPORTED_PROVIDER_SET.has(provider)
  ) {
    return undefined;
  }

  return {
    provider,
    model,
    serviceTier: normalizeServiceTier(rawTarget.serviceTier),
  };
}

export function normalizeTargets(
  rawTargets: unknown,
): PriorityTarget[] | undefined {
  if (!Array.isArray(rawTargets)) return undefined;

  const normalized: PriorityTarget[] = [];
  const seen = new Set<string>();

  for (const rawTarget of rawTargets) {
    const target = normalizeTarget(rawTarget);
    if (!target) continue;

    const key = `${target.provider}\u0000${target.model}`;
    if (seen.has(key)) continue;

    seen.add(key);
    normalized.push(target);
  }

  return normalized;
}

/**
 * Convert arbitrary config input into a safe priority-mode config.
 *
 * Invalid top-level values fall back entirely. Invalid or missing fields fall
 * back field-by-field, while an explicit empty targets array is preserved so a
 * user can opt out of every target in a scoped config.
 */
function normalizeUsage(
  rawUsage: unknown,
  fallback: OpenAIExtendedSupportConfig["usage"],
): OpenAIExtendedSupportConfig["usage"] {
  const safeFallback = cloneUsage(fallback);
  if (!isRecord(rawUsage)) return safeFallback;

  const rawRefreshInterval = rawUsage.refreshIntervalMs;
  const refreshIntervalMs =
    typeof rawRefreshInterval === "number" && Number.isFinite(rawRefreshInterval)
      ? Math.min(10 * 60_000, Math.max(15_000, Math.round(rawRefreshInterval)))
      : safeFallback.refreshIntervalMs;

  return {
    enabled:
      typeof rawUsage.enabled === "boolean"
        ? rawUsage.enabled
        : safeFallback.enabled,
    refreshIntervalMs,
    showOnlyOnSubscriptionModels:
      typeof rawUsage.showOnlyOnSubscriptionModels === "boolean"
        ? rawUsage.showOnlyOnSubscriptionModels
        : safeFallback.showOnlyOnSubscriptionModels,
    showResetTimes:
      typeof rawUsage.showResetTimes === "boolean"
        ? rawUsage.showResetTimes
        : safeFallback.showResetTimes,
    showStatus:
      typeof rawUsage.showStatus === "boolean"
        ? rawUsage.showStatus
        : safeFallback.showStatus,
  };
}

export function normalizeConfig(
  raw: unknown,
  fallback: OpenAIExtendedSupportConfig = DEFAULT_CONFIG,
): OpenAIExtendedSupportConfig {
  const safeFallback = cloneConfig(fallback);

  if (!isRecord(raw)) return safeFallback;

  const enabled =
    typeof raw.enabled === "boolean" ? raw.enabled : safeFallback.enabled;
  const persistState =
    typeof raw.persistState === "boolean"
      ? raw.persistState
      : safeFallback.persistState;
  const targets = normalizeTargets(raw.targets) ?? safeFallback.targets;
  const usage = normalizeUsage(raw.usage, safeFallback.usage);

  return { enabled, persistState, targets, usage };
}

export function parseConfigJson(
  json: string,
  fallback: OpenAIExtendedSupportConfig = DEFAULT_CONFIG,
): OpenAIExtendedSupportConfig {
  try {
    return normalizeConfig(JSON.parse(json), fallback);
  } catch {
    return cloneConfig(fallback);
  }
}

export function getUserConfigPath(agentDir: string = getAgentDir()): string {
  return join(agentDir, "extensions", PACKAGE_NAME, "config.json");
}

export function getProjectConfigPath(cwd: string): string {
  return join(resolve(cwd), ".pi", PACKAGE_NAME, "config.json");
}

export function isProjectLocalExtension(
  extensionDir: string | undefined,
  cwd: string,
): boolean {
  if (!extensionDir) return false;

  const projectPiDir = resolve(cwd, ".pi");
  const resolvedExtensionDir = resolve(extensionDir);

  return (
    resolvedExtensionDir === projectPiDir ||
    resolvedExtensionDir.startsWith(
      projectPiDir.endsWith(sep) ? projectPiDir : `${projectPiDir}${sep}`,
    )
  );
}

export type SelectConfigPathOptions = {
  cwd: string;
  extensionDir?: string;
  agentDir?: string;
  exists?: (path: string) => boolean;
};

export function selectConfigPath({
  cwd,
  extensionDir,
  agentDir,
  exists = existsSync,
}: SelectConfigPathOptions): ResolvedConfigPath {
  const projectPath = getProjectConfigPath(cwd);
  if (exists(projectPath)) {
    return { scope: "project", path: projectPath };
  }

  if (isProjectLocalExtension(extensionDir, cwd)) {
    return { scope: "project", path: projectPath };
  }

  return { scope: "user", path: getUserConfigPath(agentDir) };
}

export type LoadConfigOptions = Omit<SelectConfigPathOptions, "exists"> & {
  fallback?: OpenAIExtendedSupportConfig;
};

export type LoadedConfig = ResolvedConfigPath & {
  config: OpenAIExtendedSupportConfig;
};

export async function loadConfigFromPath(
  configPath: string,
  fallback: OpenAIExtendedSupportConfig = DEFAULT_CONFIG,
): Promise<OpenAIExtendedSupportConfig> {
  try {
    const json = await fs.readFile(configPath, "utf8");
    return parseConfigJson(json, fallback);
  } catch {
    return cloneConfig(fallback);
  }
}

export async function loadConfigForScope(
  options: LoadConfigOptions,
): Promise<LoadedConfig> {
  const selected = selectConfigPath(options);
  const fallback = options.fallback ?? DEFAULT_CONFIG;
  const globalConfig = await loadConfigFromPath(
    getUserConfigPath(options.agentDir),
    fallback,
  );
  const config =
    selected.scope === "project"
      ? await loadConfigFromPath(selected.path, globalConfig)
      : globalConfig;
  return { ...selected, config };
}

async function readExistingConfig(configPath: string): Promise<RecordLike> {
  try {
    const json = await fs.readFile(configPath, "utf8");
    const parsed: unknown = JSON.parse(json);
    return isRecord(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export async function saveConfigToPath(
  configPath: string,
  config: OpenAIExtendedSupportConfig,
): Promise<void> {
  const normalized = normalizeConfig(config);
  const existing = await readExistingConfig(configPath);
  const existingUsage = isRecord(existing.usage) ? existing.usage : {};
  const next = {
    ...existing,
    enabled: normalized.enabled,
    persistState: normalized.persistState,
    targets: normalized.targets,
    usage: { ...existingUsage, ...normalized.usage },
  };

  await fs.mkdir(dirname(configPath), { recursive: true });
  const temporaryPath = `${configPath}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await fs.writeFile(
      temporaryPath,
      `${JSON.stringify(next, null, 2)}\n`,
      "utf8",
    );
    await fs.rename(temporaryPath, configPath);
  } catch (error) {
    await fs.unlink(temporaryPath).catch(() => undefined);
    throw error;
  }
}

export async function saveConfigForScope(
  options: SelectConfigPathOptions,
  config: OpenAIExtendedSupportConfig,
): Promise<ResolvedConfigPath> {
  const selected = selectConfigPath(options);
  await saveConfigToPath(selected.path, config);
  return selected;
}
