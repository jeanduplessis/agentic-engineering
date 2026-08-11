import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import {
  CONFIG_DIR_NAME,
  getAgentDir,
} from "@earendil-works/pi-coding-agent";

export const CONFIG_BASENAME = "openai-images.json";
export const IMAGE_SAVE_MODES = ["none", "project", "global", "custom"] as const;
export const IMAGE_OUTPUT_FORMATS = ["png", "jpeg", "webp"] as const;

export type ImageSaveMode = (typeof IMAGE_SAVE_MODES)[number];
export type ImageOutputFormat = (typeof IMAGE_OUTPUT_FORMATS)[number];

export type ImageConfig = {
  enabled?: boolean;
  defaultModel?: string;
  defaultSave?: ImageSaveMode;
  outputFormat?: ImageOutputFormat;
  timeoutMs?: number;
};

export type ConfigFile = {
  image?: ImageConfig;
};

export type ResolvedConfig = {
  configPath: string;
  projectConfigPath: string;
  globalConfigPath: string;
  projectConfigExists: boolean;
  globalConfigExists: boolean;
  image: Required<ImageConfig>;
};

export const DEFAULT_IMAGE_CONFIG: Required<ImageConfig> = {
  enabled: true,
  defaultModel: "gpt-5.5",
  defaultSave: "project",
  outputFormat: "png",
  timeoutMs: 180_000,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validModel(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  const model = value.trim();
  if (!model || model.length > 200 || /[\u0000-\u001f\u007f-\u009f]/.test(model)) {
    return fallback;
  }
  return model;
}

function validTimeout(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(30_000, Math.min(5 * 60_000, Math.round(value)));
}

export function configPaths(cwd: string, agentDir = getAgentDir()): {
  project: string;
  global: string;
} {
  const project = join(resolve(cwd), CONFIG_DIR_NAME, "extensions", CONFIG_BASENAME);
  const global = join(agentDir, "extensions", CONFIG_BASENAME);
  return { project, global };
}

export function readConfig(path: string): ConfigFile {
  if (!existsSync(path)) return {};
  try {
    const parsed = JSON.parse(readFileSync(path, "utf8")) as unknown;
    if (!isRecord(parsed) || !isRecord(parsed.image)) return {};
    const image = parsed.image;
    const result: ImageConfig = {};
    if (typeof image.enabled === "boolean") result.enabled = image.enabled;
    if (typeof image.defaultModel === "string") result.defaultModel = image.defaultModel;
    if (
      typeof image.defaultSave === "string" &&
      (IMAGE_SAVE_MODES as readonly string[]).includes(image.defaultSave)
    ) {
      result.defaultSave = image.defaultSave as ImageSaveMode;
    }
    if (
      typeof image.outputFormat === "string" &&
      (IMAGE_OUTPUT_FORMATS as readonly string[]).includes(image.outputFormat)
    ) {
      result.outputFormat = image.outputFormat as ImageOutputFormat;
    }
    if (typeof image.timeoutMs === "number") result.timeoutMs = image.timeoutMs;
    return { image: result };
  } catch {
    return {};
  }
}

function mergeImageConfig(
  ...configs: Array<ImageConfig | undefined>
): Required<ImageConfig> {
  const merged = Object.assign({}, DEFAULT_IMAGE_CONFIG, ...configs);
  const defaultSave = IMAGE_SAVE_MODES.includes(merged.defaultSave)
    ? merged.defaultSave
    : DEFAULT_IMAGE_CONFIG.defaultSave;
  const outputFormat = IMAGE_OUTPUT_FORMATS.includes(merged.outputFormat)
    ? merged.outputFormat
    : DEFAULT_IMAGE_CONFIG.outputFormat;
  return {
    enabled: merged.enabled === true,
    defaultModel: validModel(merged.defaultModel, DEFAULT_IMAGE_CONFIG.defaultModel),
    defaultSave,
    outputFormat,
    timeoutMs: validTimeout(merged.timeoutMs, DEFAULT_IMAGE_CONFIG.timeoutMs),
  };
}

export function resolveConfig(cwd: string, agentDir = getAgentDir()): ResolvedConfig {
  const paths = configPaths(cwd, agentDir);
  const global = readConfig(paths.global);
  const project = readConfig(paths.project);
  return {
    configPath: existsSync(paths.project) ? paths.project : paths.global,
    projectConfigPath: paths.project,
    globalConfigPath: paths.global,
    projectConfigExists: existsSync(paths.project),
    globalConfigExists: existsSync(paths.global),
    image: mergeImageConfig(global.image, project.image),
  };
}

export const _configTest = {
  mergeImageConfig,
};
