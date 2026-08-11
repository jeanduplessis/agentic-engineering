import { randomUUID } from "node:crypto";
import {
  mkdir,
  readFile,
  realpath,
  rename,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { homedir } from "node:os";
import { extname, isAbsolute, join, resolve, sep } from "node:path";
import {
  CONFIG_DIR_NAME,
  type AgentToolResult,
  type ExtensionAPI,
  type ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Box, Container, Image, Text } from "@earendil-works/pi-tui";
import { Type, type Static } from "typebox";
import sharp from "sharp";
import {
  IMAGE_OUTPUT_FORMATS,
  IMAGE_SAVE_MODES,
  type ImageOutputFormat,
  type ImageSaveMode,
  type ResolvedConfig,
} from "./config.ts";
import {
  getCodexCredentials,
  extractAccountIdFromJwt,
  type CodexCredentialsWithSource,
} from "./codex-auth.ts";
import { maskIdentifier, sanitizeDiagnosticError } from "./format.ts";
import { piAgentDir, resolveUserPath } from "./paths.ts";

export const OPENAI_IMAGE_TOOL = "openai_image";
export const OPENAI_IMAGE_COMMAND = "openai-image";
export const OPENAI_IMAGE_STATUS_COMMAND = "openai-image-status";
export const CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses";
export const DEFAULT_TIMEOUT_MS = 180_000;
export const MAX_IMAGE_INPUT_BYTES = 20 * 1024 * 1024;
export const MAX_IMAGE_INPUTS = 5;
export const MAX_TOTAL_IMAGE_INPUT_BYTES = 50 * 1024 * 1024;
export const MAX_PROMPT_LENGTH = 20_000;

export const IMAGE_ACTIONS = ["auto", "generate", "edit"] as const;
export type ImageAction = (typeof IMAGE_ACTIONS)[number];

const SUPPORTED_INPUT_IMAGE_FORMATS = new Set(["png", "jpeg", "jpg", "webp", "gif"]);
const SSE_EVENT_BOUNDARY = /\r?\n\r?\n/;

type ImageToolSchema = {
  prompt: string;
  action?: ImageAction;
  images?: string[];
  model?: string;
  outputFormat?: ImageOutputFormat;
  save?: ImageSaveMode;
  saveDir?: string;
};

export const IMAGE_TOOL_SCHEMA = Type.Object(
  {
    prompt: Type.String({
      maxLength: MAX_PROMPT_LENGTH,
      description:
        "Image generation/editing prompt. Pass the user's wording verbatim unless they explicitly ask you to refine or expand it.",
    }),
    action: Type.Optional(
      StringEnum(IMAGE_ACTIONS, {
        description: "Generate a new image, edit/reference images, or let the model decide.",
      }),
    ),
    images: Type.Optional(
      Type.Array(Type.String(), {
        maxItems: MAX_IMAGE_INPUTS,
        description: "Local image paths to use as edit targets or references.",
      }),
    ),
    model: Type.Optional(
      Type.String({
        maxLength: 200,
        description: "Codex model to drive the hosted image_generation tool.",
      }),
    ),
    outputFormat: Type.Optional(
      StringEnum(IMAGE_OUTPUT_FORMATS, { description: "Generated image format." }),
    ),
    save: Type.Optional(
      StringEnum(IMAGE_SAVE_MODES, { description: "Where to save the generated image." }),
    ),
    saveDir: Type.Optional(
      Type.String({ description: "Directory to use when save is custom." }),
    ),
  },
  { additionalProperties: false },
);

export type ImageToolParams = Static<typeof IMAGE_TOOL_SCHEMA>;

export type ImageResultDetails = {
  id: string;
  status: string;
  prompt: string;
  revisedPrompt?: string;
  savedPath?: string;
  model: string;
  action: ImageAction;
  outputFormat: ImageOutputFormat;
  mimeType: string;
};

type ImageResult = ImageResultDetails & {
  data: string;
};

type ImageInput = {
  path: string;
  data: string;
  mimeType: string;
  size: number;
};

type ExtractedImageResult = {
  id: string;
  status: string;
  revisedPrompt?: string;
  data: string;
  mimeType: string;
};

export type ImageGenerationDebug = {
  authFound: boolean;
  authSource?: CodexCredentialsWithSource["source"];
  accountId?: string;
  endpoint: string;
  defaultModel: string;
  defaultSave: ImageSaveMode;
  enabled: boolean;
  lastStatus?: string;
  lastError?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function abortError(signal: AbortSignal): Error {
  const reason = signal.reason;
  if (reason instanceof Error) return reason;
  return new Error(typeof reason === "string" ? reason : "Image request was aborted.");
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw abortError(signal);
}

function stripModelProvider(model: string): string {
  const trimmed = model.trim();
  const slash = trimmed.lastIndexOf("/");
  return slash >= 0 ? trimmed.slice(slash + 1) : trimmed;
}

function resolveModel(
  params: Pick<ImageToolParams, "model">,
  ctx: ExtensionContext,
  cfg: ResolvedConfig,
): string {
  const explicit = params.model?.trim();
  if (explicit) return stripModelProvider(explicit);
  if (ctx.model?.provider === "openai-codex") return stripModelProvider(ctx.model.id);
  return stripModelProvider(cfg.image.defaultModel);
}

function resolveImageConfig(
  cfg: ResolvedConfig,
  params: Pick<ImageToolParams, "action" | "outputFormat" | "save">,
): {
  action: ImageAction;
  outputFormat: ImageOutputFormat;
  save: ImageSaveMode;
} {
  const action = params.action ?? "auto";
  const outputFormat = params.outputFormat ?? cfg.image.outputFormat;
  const save = params.save ?? cfg.image.defaultSave;
  if (!IMAGE_ACTIONS.includes(action)) throw new Error(`Unsupported image action: ${action}`);
  if (!IMAGE_OUTPUT_FORMATS.includes(outputFormat)) {
    throw new Error(`Unsupported image output format: ${outputFormat}`);
  }
  if (!IMAGE_SAVE_MODES.includes(save)) throw new Error(`Unsupported image save mode: ${save}`);
  return { action, outputFormat, save };
}

export function imageMimeType(path: string, format?: string): string {
  if (format === "jpeg" || format === "jpg") return "image/jpeg";
  if (format === "webp") return "image/webp";
  if (format === "gif") return "image/gif";
  if (format === "png") return "image/png";

  const extension = extname(path).toLowerCase();
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  if (extension === ".webp") return "image/webp";
  if (extension === ".gif") return "image/gif";
  return "image/png";
}

function extensionForFormat(format: ImageOutputFormat): string {
  return format === "jpeg" ? "jpg" : format;
}

function isInsideDirectory(root: string, child: string): boolean {
  const normalizedRoot = resolve(root);
  const normalizedChild = resolve(child);
  return (
    normalizedChild !== normalizedRoot &&
    normalizedChild.startsWith(`${normalizedRoot}${sep}`)
  );
}

async function validateImageInput(
  path: string,
  realWorkspaceRoot: string,
): Promise<{ mimeType: string; path: string; size: number }> {
  const realInputPath = await realpath(path).catch(() => undefined);
  if (!realInputPath || !isInsideDirectory(realWorkspaceRoot, realInputPath)) {
    throw new Error(
      `Image input must be a file inside the current workspace: ${displayPath(path)}`,
    );
  }

  const pathStats = await stat(realInputPath).catch(() => undefined);
  if (!pathStats?.isFile()) {
    throw new Error(
      `Image input must be a file inside the current workspace: ${displayPath(path)}`,
    );
  }
  if (pathStats.size > MAX_IMAGE_INPUT_BYTES) {
    throw new Error(`Image input is too large (max 20 MB): ${displayPath(path)}`);
  }

  const metadata = await sharp(realInputPath, { animated: false })
    .metadata()
    .catch(() => undefined);
  if (!metadata?.format || !SUPPORTED_INPUT_IMAGE_FORMATS.has(metadata.format)) {
    throw new Error(`Image input is not a readable image: ${displayPath(path)}`);
  }

  return {
    mimeType: imageMimeType(path, metadata.format),
    path: realInputPath,
    size: pathStats.size,
  };
}

async function readImageInputs(
  paths: string[] | undefined,
  cwd: string,
  signal?: AbortSignal,
): Promise<ImageInput[]> {
  const workspaceRoot = resolve(cwd);
  const realWorkspaceRoot = await realpath(workspaceRoot).catch(() => workspaceRoot);
  const validatedInputs: Array<{ path: string; mimeType: string; size: number }> = [];
  const seenPaths = new Set<string>();
  let totalBytes = 0;

  for (const rawPath of paths ?? []) {
    throwIfAborted(signal);
    let trimmed = rawPath.trim();
    if (trimmed.startsWith("@")) trimmed = trimmed.slice(1);
    if (!trimmed) continue;

    const candidatePath = isAbsolute(trimmed)
      ? resolve(trimmed)
      : resolve(workspaceRoot, trimmed);
    if (!isInsideDirectory(workspaceRoot, candidatePath)) {
      throw new Error(
        `Image input must be a file inside the current workspace: ${displayPath(candidatePath)}`,
      );
    }

    const input = await validateImageInput(candidatePath, realWorkspaceRoot);
    if (seenPaths.has(input.path)) continue;
    if (validatedInputs.length >= MAX_IMAGE_INPUTS) {
      throw new Error(`Too many image inputs (max ${MAX_IMAGE_INPUTS}).`);
    }

    totalBytes += input.size;
    if (totalBytes > MAX_TOTAL_IMAGE_INPUT_BYTES) {
      throw new Error("Image inputs are too large in total (max 50 MB).");
    }
    seenPaths.add(input.path);
    validatedInputs.push(input);
  }

  const inputs: ImageInput[] = [];
  let actualTotalBytes = 0;
  for (const input of validatedInputs) {
    throwIfAborted(signal);
    const buffer = await readFile(input.path);
    if (buffer.byteLength > MAX_IMAGE_INPUT_BYTES) {
      throw new Error(`Image input is too large (max 20 MB): ${displayPath(input.path)}`);
    }
    const metadata = await sharp(buffer, { animated: false })
      .metadata()
      .catch(() => undefined);
    if (!metadata?.format || !SUPPORTED_INPUT_IMAGE_FORMATS.has(metadata.format)) {
      throw new Error(`Image input is not a readable image: ${displayPath(input.path)}`);
    }
    actualTotalBytes += buffer.byteLength;
    if (actualTotalBytes > MAX_TOTAL_IMAGE_INPUT_BYTES) {
      throw new Error("Image inputs are too large in total (max 50 MB).");
    }
    inputs.push({
      path: input.path,
      mimeType: imageMimeType(input.path, metadata.format),
      data: buffer.toString("base64"),
      size: buffer.byteLength,
    });
  }
  return inputs;
}

function resolveSaveDir(
  mode: ImageSaveMode,
  params: Pick<ImageToolParams, "saveDir">,
  cwd: string,
): string | undefined {
  if (mode === "none") return undefined;
  if (mode === "project") return join(cwd, CONFIG_DIR_NAME, "generated-images");
  if (mode === "global") return join(piAgentDir(), "generated-images");

  const dir = params.saveDir?.trim() || process.env.PI_IMAGE_SAVE_DIR?.trim();
  if (!dir) throw new Error("save=custom requires saveDir or PI_IMAGE_SAVE_DIR.");
  return resolveUserPath(dir, cwd);
}

async function saveImage(
  data: string,
  format: ImageOutputFormat,
  outputDir: string,
  id: string,
): Promise<string> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const safeId = id.replace(/[^a-zA-Z0-9_-]/g, "_") || randomUUID().slice(0, 8);
  const filename = `openai-image-${timestamp}-${safeId}.${extensionForFormat(format)}`;
  const outputPath = join(outputDir, filename);
  const temporaryPath = join(outputDir, `.${filename}.${randomUUID()}.tmp`);

  await mkdir(outputDir, { recursive: true });
  try {
    await writeFile(temporaryPath, Buffer.from(data, "base64"), {
      flag: "wx",
      mode: 0o600,
    });
    await rename(temporaryPath, outputPath);
    return outputPath;
  } catch (error) {
    await unlink(temporaryPath).catch(() => undefined);
    throw error;
  }
}

export function buildRequest(
  params: Pick<ImageToolParams, "prompt" | "action" | "outputFormat" | "save">,
  model: string,
  cfg: ResolvedConfig,
  images: ImageInput[] = [],
): Record<string, unknown> {
  const { action, outputFormat } = resolveImageConfig(cfg, params);
  const content: Array<Record<string, string>> = [
    { type: "input_text", text: params.prompt },
  ];
  for (const image of images) {
    content.push({
      type: "input_image",
      detail: "auto",
      image_url: `data:${image.mimeType};base64,${image.data}`,
    });
  }

  const imageTool: Record<string, unknown> = {
    type: "image_generation",
    output_format: outputFormat,
  };
  if (action !== "auto") imageTool.action = action;

  return {
    model,
    instructions: "",
    input: [{ role: "user", content }],
    tools: [imageTool],
    tool_choice: { type: "image_generation" },
    parallel_tool_calls: false,
    store: false,
    stream: true,
    include: [],
    client_metadata: { "x-codex-installation-id": "openai-images" },
  };
}

export function dataUrlParts(
  value: string,
  fallbackMimeType: string,
): { data: string; mimeType: string } {
  const match = value.match(/^data:([^;,]+);base64,(.*)$/s);
  if (match) {
    return {
      data: (match[2] ?? "").trim(),
      mimeType: match[1] ?? fallbackMimeType,
    };
  }
  return { data: value.trim(), mimeType: fallbackMimeType };
}

function imageGenerationItem(
  value: unknown,
): {
  id?: string;
  status?: string;
  revised_prompt?: string;
  result?: string;
  b64_json?: string;
} | undefined {
  if (!isRecord(value) || value.type !== "image_generation_call") return undefined;
  return value as {
    id?: string;
    status?: string;
    revised_prompt?: string;
    result?: string;
    b64_json?: string;
  };
}

function isCompletedStatus(status: string): boolean {
  return ["completed", "complete", "succeeded"].includes(status.toLowerCase());
}

export function extractImageFromEvent(
  event: unknown,
  fallbackMimeType: string,
): ExtractedImageResult | undefined {
  if (!isRecord(event)) return undefined;
  const item = imageGenerationItem(event.item) ?? imageGenerationItem(event);
  if (item) {
    const raw =
      typeof item.result === "string" && item.result.trim()
        ? item.result
        : typeof item.b64_json === "string"
          ? item.b64_json
          : undefined;
    if (!raw) return undefined;
    const { data, mimeType } = dataUrlParts(raw, fallbackMimeType);
    return {
      id: typeof item.id === "string" ? item.id : `ig_${randomUUID().slice(0, 8)}`,
      status: typeof item.status === "string" ? item.status : "completed",
      revisedPrompt:
        typeof item.revised_prompt === "string" ? item.revised_prompt : undefined,
      data,
      mimeType,
    };
  }

  const partial =
    typeof event.partial_image_b64 === "string"
      ? event.partial_image_b64
      : typeof event.b64_json === "string"
        ? event.b64_json
        : undefined;
  if (partial?.trim()) {
    const { data, mimeType } = dataUrlParts(partial, fallbackMimeType);
    return {
      id: `ig_${randomUUID().slice(0, 8)}`,
      status: "partial",
      data,
      mimeType,
    };
  }
  return undefined;
}

function eventErrorMessage(event: Record<string, unknown>): string | undefined {
  if (typeof event.message === "string") return event.message;
  if (isRecord(event.error) && typeof event.error.message === "string") {
    return event.error.message;
  }
  if (isRecord(event.response) && isRecord(event.response.error)) {
    const message = event.response.error.message;
    if (typeof message === "string") return message;
  }
  return undefined;
}

export async function parseSseForImage(
  response: Response,
  fallbackMimeType: string,
  signal?: AbortSignal,
): Promise<ExtractedImageResult> {
  if (!response.body) throw new Error("No response body from Codex image request.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processBlock = (block: string): ExtractedImageResult | undefined => {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n")
      .trim();
    if (!data || data === "[DONE]") return undefined;

    let event: unknown;
    try {
      event = JSON.parse(data) as unknown;
    } catch {
      return undefined;
    }

    if (isRecord(event) && event.type === "response.failed") {
      const message = sanitizeDiagnosticError(
        eventErrorMessage(event) ?? "Codex image request failed.",
      );
      throw new Error(message);
    }
    if (isRecord(event) && event.type === "error") {
      const message = sanitizeDiagnosticError(
        eventErrorMessage(event) ?? JSON.stringify(event),
      );
      throw new Error(`Codex image error: ${message}`);
    }

    const image = extractImageFromEvent(event, fallbackMimeType);
    return image && isCompletedStatus(image.status) && image.data ? image : undefined;
  };

  try {
    while (true) {
      throwIfAborted(signal);
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = SSE_EVENT_BOUNDARY.exec(buffer);
      while (boundary) {
        const block = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const image = processBlock(block);
        if (image) {
          await reader.cancel().catch(() => undefined);
          return image;
        }
        boundary = SSE_EVENT_BOUNDARY.exec(buffer);
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const image = processBlock(buffer);
      if (image) return image;
    }
  } finally {
    reader.releaseLock();
  }

  throw new Error("No completed image_generation_call result returned by Codex.");
}

async function getCredentials(
  ctx: ExtensionContext,
  signal?: AbortSignal,
): Promise<CodexCredentialsWithSource> {
  const credentials = await getCodexCredentials(ctx, signal);
  if (credentials) return credentials;
  throw new Error("Missing openai-codex OAuth credentials. Run /login openai-codex.");
}

async function requestCodexImage(
  params: ImageToolParams,
  ctx: ExtensionContext,
  cfg: ResolvedConfig,
  requestSignal?: AbortSignal,
): Promise<ImageResult> {
  if (!cfg.image.enabled) {
    throw new Error("OpenAI image generation is disabled in config.");
  }
  if (!params.prompt.trim()) throw new Error("Image prompt must not be empty.");

  const cwd = ctx.cwd || process.cwd();
  const model = resolveModel(params, ctx, cfg);
  const { action, outputFormat, save } = resolveImageConfig(cfg, params);
  const saveDir = resolveSaveDir(save, params, cwd);
  const timeoutSignal = AbortSignal.timeout(cfg.image.timeoutMs || DEFAULT_TIMEOUT_MS);
  const baseSignal = requestSignal ?? ctx.signal;
  const signal = baseSignal
    ? AbortSignal.any([baseSignal, timeoutSignal])
    : timeoutSignal;

  const credentials = await getCredentials(ctx, signal);
  const images = await readImageInputs(params.images, cwd, signal);
  const request = buildRequest(params, model, cfg, images);
  const response = await fetch(CODEX_RESPONSES_URL, {
    method: "POST",
    headers: {
      authorization: `Bearer ${credentials.accessToken}`,
      "chatgpt-account-id": credentials.accountId,
      "OpenAI-Beta": "responses=experimental",
      accept: "text/event-stream",
      "content-type": "application/json",
      originator: "codex_cli_rs",
      "User-Agent": "codex_cli_rs/0.0.0 (openai-images)",
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    const statusText = response.statusText
      ? ` ${sanitizeDiagnosticError(response.statusText, 120)}`
      : "";
    throw new Error(`Codex image request failed (${response.status}${statusText}).`);
  }

  const parsed = await parseSseForImage(
    response,
    imageMimeType(`image.${outputFormat}`, outputFormat),
    signal,
  );
  const savedPath = saveDir
    ? await saveImage(parsed.data, outputFormat, saveDir, parsed.id)
    : undefined;

  return {
    id: parsed.id,
    status: parsed.status,
    prompt: params.prompt,
    revisedPrompt: parsed.revisedPrompt,
    data: parsed.data,
    mimeType: parsed.mimeType,
    savedPath,
    model,
    action,
    outputFormat,
  };
}

function displayPath(path: string): string {
  const home = homedir();
  if (!home) return path;
  if (path === home) return "~";
  const homePrefix = home.endsWith(sep) ? home : `${home}${sep}`;
  return path.startsWith(homePrefix) ? `~/${path.slice(homePrefix.length)}` : path;
}

function clipText(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function resultText(result: ImageResultDetails): string {
  const lines = [
    `Generated image using OpenAI image_generation via openai-codex/${result.model}.`,
    `Action: ${result.action}.`,
    `Prompt: ${clipText(result.prompt, 4_000)}`,
  ];
  if (result.revisedPrompt) {
    lines.push(`Revised prompt: ${clipText(result.revisedPrompt, 4_000)}`);
  }
  if (result.savedPath) lines.push(`Saved: ${displayPath(result.savedPath)}`);
  return lines.join("\n");
}

function detailsFromResult(result: ImageResult): ImageResultDetails {
  const { data: _data, ...details } = result;
  return details;
}

function isImageContent(
  value: unknown,
): value is { type: "image"; data: string; mimeType: string } {
  return (
    isRecord(value) &&
    value.type === "image" &&
    typeof value.data === "string" &&
    typeof value.mimeType === "string"
  );
}

function imageFromContent(content: unknown):
  | { data: string; mimeType: string }
  | undefined {
  if (!Array.isArray(content)) return undefined;
  const image = content.find(isImageContent);
  return image ? { data: image.data, mimeType: image.mimeType } : undefined;
}

function textFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((part): part is { type: "text"; text: string } =>
      isRecord(part) && part.type === "text" && typeof part.text === "string",
    )
    .map((part) => part.text)
    .join("\n");
}

function imageComponent(
  data: string,
  mimeType: string,
  theme: { fg(color: "dim", text: string): string },
  filename?: string,
): Image {
  return new Image(
    data,
    mimeType,
    { fallbackColor: (line) => theme.fg("dim", line) },
    {
      maxWidthCells: 80,
      maxHeightCells: 24,
      ...(filename ? { filename } : {}),
    },
  );
}

function isImageResultDetails(value: unknown): value is ImageResultDetails {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.status === "string" &&
    typeof value.prompt === "string" &&
    typeof value.model === "string" &&
    typeof value.action === "string" &&
    typeof value.outputFormat === "string" &&
    typeof value.mimeType === "string"
  );
}

export function registerOpenAIImage(
  pi: ExtensionAPI,
  getConfig: (ctx: ExtensionContext) => ResolvedConfig,
): { getDebug: (ctx: ExtensionContext) => Promise<ImageGenerationDebug> } {
  let lastStatus: string | undefined;
  let lastError: string | undefined;

  async function generate(
    params: ImageToolParams,
    ctx: ExtensionContext,
    requestSignal?: AbortSignal,
  ): Promise<ImageResult> {
    try {
      lastStatus = "requesting";
      lastError = undefined;
      const result = await requestCodexImage(params, ctx, getConfig(ctx), requestSignal);
      lastStatus = `completed (${result.id})`;
      return result;
    } catch (error) {
      const message = sanitizeDiagnosticError(
        error instanceof Error ? error.message : String(error),
      );
      lastStatus = "error";
      lastError = message;
      throw new Error(message);
    }
  }

  async function getDebug(ctx: ExtensionContext): Promise<ImageGenerationDebug> {
    const cfg = getConfig(ctx);
    let credentials: CodexCredentialsWithSource | undefined;
    try {
      credentials = await getCredentials(ctx);
    } catch {
      credentials = undefined;
    }
    return {
      authFound: credentials !== undefined,
      authSource: credentials?.source,
      accountId: maskIdentifier(credentials?.accountId),
      endpoint: CODEX_RESPONSES_URL,
      defaultModel:
        ctx.model?.provider === "openai-codex"
          ? stripModelProvider(ctx.model.id)
          : stripModelProvider(cfg.image.defaultModel),
      defaultSave: cfg.image.defaultSave,
      enabled: cfg.image.enabled,
      lastStatus,
      lastError,
    };
  }

  pi.registerMessageRenderer("openai-image", (message, _options, theme) => {
    const details = isImageResultDetails(message.details) ? message.details : undefined;
    const text = details ? resultText(details) : textFromContent(message.content);
    const image = imageFromContent(message.content);
    const container = new Container();
    const box = new Box(1, 1, (line) => theme.bg("customMessageBg", line));
    box.addChild(
      new Text(`${theme.fg("accent", theme.bold("[openai-image]"))}\n\n${text}`, 0, 0),
    );
    if (image) {
      box.addChild(
        imageComponent(image.data, image.mimeType, theme, details?.savedPath),
      );
    }
    container.addChild(box);
    return container;
  });

  pi.registerCommand(OPENAI_IMAGE_COMMAND, {
    description: "Generate an image with OpenAI Codex image generation",
    handler: async (args, ctx) => {
      const prompt = args.trim();
      if (!prompt) {
        ctx.ui.notify("Usage: /openai-image <prompt>", "error");
        return;
      }
      try {
        ctx.ui.notify("Requesting OpenAI image...", "info");
        const result = await generate({ prompt }, ctx, ctx.signal);
        pi.sendMessage({
          customType: "openai-image",
          content: [
            { type: "text", text: resultText(result) },
            { type: "image", data: result.data, mimeType: result.mimeType },
          ],
          display: true,
          details: detailsFromResult(result),
        });
      } catch (error) {
        ctx.ui.notify(
          sanitizeDiagnosticError(error instanceof Error ? error.message : String(error)),
          "error",
        );
      }
    },
  });

  pi.registerCommand(OPENAI_IMAGE_STATUS_COMMAND, {
    description: "Show OpenAI image extension status",
    handler: async (_args, ctx) => {
      const debug = await getDebug(ctx);
      const lines = [
        `Enabled: ${debug.enabled}`,
        `Auth: ${debug.authFound ? `found (${debug.authSource})` : "missing"}`,
        `Account: ${debug.accountId ?? "none"}`,
        `Model: ${debug.defaultModel}`,
        `Save: ${debug.defaultSave}`,
        `Last request: ${debug.lastStatus ?? "none"}`,
      ];
      if (debug.lastError) lines.push(`Last error: ${debug.lastError}`);
      ctx.ui.notify(lines.join("\n"), debug.authFound ? "info" : "warning");
    },
  });

  pi.registerTool<typeof IMAGE_TOOL_SCHEMA, ImageResultDetails | undefined>({
    name: OPENAI_IMAGE_TOOL,
    label: "OpenAI image",
    description:
      "Generate or edit images through OpenAI Codex subscription auth using the hosted image_generation tool. Supports local reference/edit images and saving generated assets.",
    promptSnippet: "Generate or edit raster images via OpenAI Codex subscription auth.",
    promptGuidelines: [
      "Use openai_image when the user asks to generate or edit a raster image, photo, illustration, mockup, texture, sprite, or bitmap asset.",
      "Pass the user's image prompt verbatim. Do not embellish, rewrite, add camera/style details, or add negative prompt terms unless the user explicitly asks you to refine the prompt.",
      "Use openai_image with images for local reference images or edit targets; save project assets into the workspace when requested.",
    ],
    parameters: IMAGE_TOOL_SCHEMA,
    async execute(_toolCallId, params, signal, onUpdate, ctx) {
      const cfg = getConfig(ctx);
      const model = resolveModel(params, ctx, cfg);
      onUpdate?.({
        content: [
          {
            type: "text",
            text: `Requesting OpenAI image_generation via openai-codex/${model}...`,
          },
        ],
        details: undefined,
      });
      const result = await generate(params, ctx, signal);
      return {
        content: [
          { type: "text", text: resultText(result) },
          { type: "image", data: result.data, mimeType: result.mimeType },
        ],
        details: detailsFromResult(result),
      };
    },
    renderCall(args, theme) {
      const parts = [theme.fg("toolTitle", "openai_image")];
      if (args.action) parts.push(theme.fg("muted", args.action));
      if (args.images?.length) parts.push(theme.fg("dim", `${args.images.length} reference image(s)`));
      return new Text(parts.join(" "), 0, 0);
    },
    renderResult(
      result: AgentToolResult<ImageResultDetails | undefined>,
      options,
      theme,
      context,
    ) {
      if (options.isPartial) {
        return new Text(theme.fg("warning", "Requesting image..."), 0, 0);
      }

      const details = isImageResultDetails(result.details) ? result.details : undefined;
      const text = details ? resultText(details) : textFromContent(result.content);
      const image = imageFromContent(result.content);
      if (!image || !context.showImages) {
        return new Text(
          context.isError ? theme.fg("error", text) : theme.fg("success", text),
          0,
          0,
        );
      }

      const container = new Container();
      container.addChild(new Text(theme.fg(context.isError ? "error" : "success", text), 0, 0));
      container.addChild(imageComponent(image.data, image.mimeType, theme, details?.savedPath));
      return container;
    },
  });

  return { getDebug };
}

export const _imageTest = {
  CODEX_RESPONSES_URL,
  DEFAULT_TIMEOUT_MS,
  OPENAI_IMAGE_TOOL,
  OPENAI_IMAGE_COMMAND,
  MAX_IMAGE_INPUT_BYTES,
  MAX_IMAGE_INPUTS,
  MAX_TOTAL_IMAGE_INPUT_BYTES,
  MAX_PROMPT_LENGTH,
  extractAccountIdFromJwt,
  imageMimeType,
  dataUrlParts,
  extractImageFromEvent,
  parseSseForImage,
  displayPath,
  buildRequest,
  resolveSaveDir,
};
