import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  truncateSync,
  writeFileSync,
} from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join, relative } from "node:path";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import sharp from "sharp";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  DEFAULT_IMAGE_CONFIG,
  type ResolvedConfig,
} from "../src/config.ts";
import {
  parseCodexRegistryCredentials,
  extractAccountIdFromJwt,
} from "../src/codex-auth.ts";
import { registerOpenAIImage, _imageTest } from "../src/image.ts";

vi.mock("../src/codex-auth.ts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/codex-auth.ts")>();
  return {
    ...actual,
    readCodexAuth: vi.fn(() => undefined),
    getCodexCredentials: vi.fn(async (ctx?: Pick<ExtensionContext, "modelRegistry">) => {
      const raw = await ctx?.modelRegistry.getApiKeyForProvider("openai-codex");
      const credentials = actual.parseCodexRegistryCredentials(raw);
      return credentials ? { ...credentials, source: "modelRegistry" as const } : undefined;
    }),
  };
});

type ToolExecute = (
  toolCallId: string,
  params: Record<string, unknown>,
  signal: AbortSignal | undefined,
  onUpdate: ((update: unknown) => void) | undefined,
  ctx: ExtensionContext,
) => Promise<{ content: unknown[]; details?: unknown }>;

type RegisteredTool = {
  name: string;
  execute: ToolExecute;
};

type ImageHarness = {
  ctx: ExtensionContext;
  tool: RegisteredTool;
  getDebug: (ctx: ExtensionContext) => Promise<Record<string, unknown>>;
};

const tempDirs: string[] = [];
const originalImageSaveDir = process.env.PI_IMAGE_SAVE_DIR;

function createTempProject(): string {
  const cwd = mkdtempSync(join(tmpdir(), "pi-openai-images-"));
  tempDirs.push(cwd);
  return cwd;
}

function makeConfig(
  cwd: string,
  image: Partial<ResolvedConfig["image"]> = {},
): ResolvedConfig {
  return {
    configPath: join(cwd, ".pi", "extensions", "openai-images.json"),
    projectConfigPath: join(cwd, ".pi", "extensions", "openai-images.json"),
    globalConfigPath: join(cwd, "global", "openai-images.json"),
    projectConfigExists: false,
    globalConfigExists: false,
    image: { ...DEFAULT_IMAGE_CONFIG, ...image },
  };
}

function sseResponse(events: unknown[], lineEnding = "\n"): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const event of events) {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(event)}${lineEnding}${lineEnding}`),
          );
        }
        controller.close();
      },
    }),
    { headers: { "content-type": "text/event-stream" } },
  );
}

function finalImageEvent(id = "ig_test", data = "Zm9v") {
  return {
    type: "response.output_item.done",
    item: { type: "image_generation_call", id, status: "completed", result: data },
  };
}

async function writeTinyPng(path: string): Promise<void> {
  await sharp({
    create: {
      width: 1,
      height: 1,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 1 },
    },
  })
    .png()
    .toFile(path);
}

async function writeTinyJpeg(path: string): Promise<void> {
  const data = await sharp({
    create: {
      width: 1,
      height: 1,
      channels: 3,
      background: { r: 0, g: 0, b: 0 },
    },
  })
    .jpeg()
    .toBuffer();
  writeFileSync(path, data);
}

function createImageHarness(options: {
  cwd?: string;
  registryCredentials?: string;
  imageConfig?: Partial<ResolvedConfig["image"]>;
} = {}): ImageHarness {
  const cwd = options.cwd ?? createTempProject();
  let registeredTool: RegisteredTool | undefined;
  const pi = {
    registerTool: vi.fn((tool: unknown) => {
      registeredTool = tool as RegisteredTool;
    }),
    registerCommand: vi.fn(),
    registerMessageRenderer: vi.fn(),
  } as unknown as ExtensionAPI;
  const ctx = {
    cwd,
    mode: "tui",
    hasUI: true,
    signal: undefined,
    model: { provider: "openai-codex", id: "gpt-5.5" },
    ui: { notify: vi.fn() },
    modelRegistry: {
      getApiKeyForProvider: vi.fn(() => Promise.resolve(options.registryCredentials)),
    },
  } as unknown as ExtensionContext;
  const cfg = makeConfig(cwd, {
    defaultSave: "none",
    ...options.imageConfig,
  });
  const debug = registerOpenAIImage(pi, () => cfg);
  if (!registeredTool) throw new Error("openai_image tool was not registered.");
  return {
    ctx,
    tool: registeredTool,
    getDebug: debug.getDebug as unknown as ImageHarness["getDebug"],
  };
}

function stubFetch(response: Response): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function executeImageTool(
  harness: ImageHarness,
  params: Record<string, unknown>,
  signal?: AbortSignal,
) {
  return harness.tool.execute("tool-call-1", params, signal, vi.fn(), harness.ctx);
}

beforeEach(() => {
  delete process.env.PI_IMAGE_SAVE_DIR;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  if (originalImageSaveDir === undefined) delete process.env.PI_IMAGE_SAVE_DIR;
  else process.env.PI_IMAGE_SAVE_DIR = originalImageSaveDir;
  for (const tempDir of tempDirs.splice(0)) {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

describe("authentication helpers", () => {
  test("parses registry JSON credentials", () => {
    expect(
      parseCodexRegistryCredentials(
        JSON.stringify({ access: "access-token", accountId: "acct_test" }),
      ),
    ).toEqual({ accessToken: "access-token", accountId: "acct_test" });
  });

  test("extracts an account id from a JWT", () => {
    const payload = Buffer.from(
      JSON.stringify({
        "https://api.openai.com/auth": { chatgpt_account_id: "acct_jwt" },
      }),
    )
      .toString("base64url")
      .replace(/=+$/g, "");
    const token = `header.${payload}.signature`;
    expect(extractAccountIdFromJwt(token)).toBe("acct_jwt");
  });
});

describe("image helpers", () => {
  test("exposes image tool defaults", () => {
    expect(_imageTest.OPENAI_IMAGE_TOOL).toBe("openai_image");
  });

  test("detects image mime types and display paths", () => {
    expect(_imageTest.imageMimeType("x.jpg")).toBe("image/jpeg");
    expect(_imageTest.displayPath(join(homedir(), "dev", "image.png"))).toBe(
      "~/dev/image.png",
    );
  });

  test("extracts data URLs and completed image events", () => {
    expect(_imageTest.dataUrlParts("data:image/png;base64,Zm9v", "image/png")).toEqual({
      data: "Zm9v",
      mimeType: "image/png",
    });
    expect(
      _imageTest.extractImageFromEvent(finalImageEvent("ig_1", "Zm9v"), "image/png"),
    ).toMatchObject({ id: "ig_1", status: "completed", data: "Zm9v" });
    expect(_imageTest.extractImageFromEvent({ partial_image_b64: "cGFydGlhbA==" }, "image/png"))
      .toMatchObject({ status: "partial", data: "cGFydGlhbA==" });
  });

  test("builds image generation requests", () => {
    const cwd = createTempProject();
    const request = _imageTest.buildRequest(
      { prompt: "draw an otter", action: "generate", outputFormat: "webp" },
      "gpt-5.5",
      makeConfig(cwd),
      [],
    );
    expect(request).toMatchObject({
      model: "gpt-5.5",
      tool_choice: { type: "image_generation" },
      tools: [{ type: "image_generation", action: "generate", output_format: "webp" }],
    });
  });
});

describe("openai_image tool execution", () => {
  test("sends a Codex image request and returns native image content", async () => {
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    const result = await executeImageTool(harness, { prompt: "draw an otter", save: "none" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(_imageTest.CODEX_RESPONSES_URL);
    expect(init.headers).toMatchObject({
      authorization: "Bearer test-access",
      "chatgpt-account-id": "acct_test",
    });
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body).toMatchObject({
      model: "gpt-5.5",
      tool_choice: { type: "image_generation" },
    });
    expect(result.content).toEqual([
      { type: "text", text: expect.stringContaining("Generated image") },
      { type: "image", data: "Zm9v", mimeType: "image/png" },
    ]);
    expect(result.details).toMatchObject({ id: "ig_test", mimeType: "image/png" });
    expect(result.details).not.toHaveProperty("data");
  });

  test("waits for the completed image event after partial events", async () => {
    stubFetch(
      sseResponse([
        { partial_image_b64: "cGFydGlhbA==" },
        finalImageEvent("ig_final", "ZmluYWw="),
      ]),
    );
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    const result = await executeImageTool(harness, { prompt: "draw", save: "none" });

    expect(result.content).toContainEqual({
      type: "image",
      data: "ZmluYWw=",
      mimeType: "image/png",
    });
    expect(result.details).toMatchObject({ id: "ig_final" });
  });

  test("parses CRLF-delimited SSE events", async () => {
    stubFetch(sseResponse([finalImageEvent("ig_crlf", "Y3JsZg==")], "\r\n"));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    const result = await executeImageTool(harness, { prompt: "draw", save: "none" });

    expect(result.details).toMatchObject({ id: "ig_crlf" });
  });

  test("saves project-local reference edits", async () => {
    const cwd = createTempProject();
    const inputPath = join(cwd, "input.png");
    await writeTinyPng(inputPath);
    const inputData = readFileSync(inputPath).toString("base64");
    const fetchMock = stubFetch(sseResponse([finalImageEvent("ig_saved", "Zm9v")]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
      imageConfig: { defaultSave: "project" },
    });

    const result = await executeImageTool(harness, {
      prompt: "edit it",
      action: "edit",
      images: ["input.png", inputPath],
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body)) as {
      input: Array<{ content: unknown[] }>;
    };
    expect(body.input[0]?.content).toContainEqual({
      type: "input_image",
      detail: "auto",
      image_url: `data:image/png;base64,${inputData}`,
    });
    const outputDir = join(cwd, ".pi", "generated-images");
    const files = readdirSync(outputDir);
    expect(files).toHaveLength(1);
    expect(files[0]).toMatch(/^openai-image-.*-ig_saved\.png$/);
    expect(readFileSync(join(outputDir, files[0]!)).toString("base64")).toBe("Zm9v");
    expect(result.details).toMatchObject({ savedPath: join(outputDir, files[0]!) });
  });

  test("uses detected image content type instead of the filename extension", async () => {
    const cwd = createTempProject();
    const renamedJpeg = join(cwd, "actually-jpeg.png");
    await writeTinyJpeg(renamedJpeg);
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await executeImageTool(harness, {
      prompt: "edit it",
      images: ["actually-jpeg.png"],
      save: "none",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(init.body)).toContain("data:image/jpeg;base64,");
  });

  test("resolves a relative custom save directory", async () => {
    const cwd = createTempProject();
    stubFetch(sseResponse([finalImageEvent("ig_custom", "Zm9v")]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    const result = await executeImageTool(harness, {
      prompt: "draw",
      save: "custom",
      saveDir: "artifacts",
    });

    expect(result.details).toMatchObject({
      savedPath: expect.stringContaining(join(cwd, "artifacts")),
    });
    expect(readdirSync(join(cwd, "artifacts"))).toHaveLength(1);
  });

  test("rejects missing custom save directories before fetch", async () => {
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await expect(executeImageTool(harness, { prompt: "draw", save: "custom" })).rejects.toThrow(
      "save=custom requires saveDir or PI_IMAGE_SAVE_DIR",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("rejects image inputs outside the workspace", async () => {
    const cwd = createTempProject();
    const outsideDir = createTempProject();
    const outsideImage = join(outsideDir, "outside.png");
    await writeTinyPng(outsideImage);
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await expect(
      executeImageTool(harness, { prompt: "draw", images: [outsideImage] }),
    ).rejects.toThrow("Image input must be a file inside the current workspace");
    await expect(
      executeImageTool(harness, { prompt: "draw", images: [relative(cwd, outsideImage)] }),
    ).rejects.toThrow("Image input must be a file inside the current workspace");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("rejects non-image files before fetch", async () => {
    const cwd = createTempProject();
    writeFileSync(join(cwd, "notes.txt"), "not an image", "utf8");
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await expect(
      executeImageTool(harness, { prompt: "draw", images: ["notes.txt"] }),
    ).rejects.toThrow("Image input is not a readable image");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("rejects oversized image inputs before fetch", async () => {
    const cwd = createTempProject();
    const largeImage = join(cwd, "large.png");
    writeFileSync(largeImage, "");
    truncateSync(largeImage, _imageTest.MAX_IMAGE_INPUT_BYTES + 1);
    const fetchMock = stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      cwd,
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await expect(
      executeImageTool(harness, { prompt: "draw", images: ["large.png"] }),
    ).rejects.toThrow("Image input is too large");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("rejects disabled image generation and missing auth", async () => {
    const disabledFetch = stubFetch(sseResponse([finalImageEvent()]));
    const disabled = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
      imageConfig: { enabled: false },
    });
    await expect(executeImageTool(disabled, { prompt: "draw" })).rejects.toThrow(
      "OpenAI image generation is disabled in config",
    );
    expect(disabledFetch).not.toHaveBeenCalled();

    const missingFetch = stubFetch(sseResponse([finalImageEvent()]));
    const missing = createImageHarness({ registryCredentials: undefined });
    await expect(executeImageTool(missing, { prompt: "draw" })).rejects.toThrow(
      "Missing openai-codex OAuth credentials",
    );
    expect(missingFetch).not.toHaveBeenCalled();
  });

  test("redacts and bounds streamed error messages", async () => {
    const secret = `bad\u001b[31m Bearer sk-secretsecret accountId=acct_1234567890abcdef ${"x".repeat(700)}`;
    stubFetch(sseResponse([{ type: "error", message: secret }]));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });

    await expect(executeImageTool(harness, { prompt: "draw" })).rejects.toThrow(
      "Codex image error: bad",
    );
    const debug = await harness.getDebug(harness.ctx);
    expect(debug.lastError).not.toContain("sk-secretsecret");
    expect(debug.lastError).not.toContain("acct_1234567890abcdef");
    expect(String(debug.lastError).length).toBeLessThanOrEqual(500);
  });

  test("works without interactive UI in headless mode", async () => {
    stubFetch(sseResponse([finalImageEvent("ig_headless", "aGVhZGxlc3M=")]));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });
    harness.ctx.hasUI = false;
    harness.ctx.mode = "json";

    const result = await executeImageTool(harness, { prompt: "draw", save: "none" });

    expect(result.content).toContainEqual({
      type: "image",
      data: "aGVhZGxlc3M=",
      mimeType: "image/png",
    });
  });

  test("forwards cancellation to the image request", async () => {
    stubFetch(sseResponse([finalImageEvent()]));
    const harness = createImageHarness({
      registryCredentials: JSON.stringify({ access: "test-access", accountId: "acct_test" }),
    });
    const controller = new AbortController();
    controller.abort(new Error("cancelled"));

    await expect(
      executeImageTool(harness, { prompt: "draw", save: "none" }, controller.signal),
    ).rejects.toThrow("cancelled");
  });
});
