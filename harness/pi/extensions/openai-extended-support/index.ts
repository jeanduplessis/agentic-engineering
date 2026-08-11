import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
  ExtensionFactory,
} from "@earendil-works/pi-coding-agent";
import { getFastCommandCompletions, parseFastCommand } from "./commands";
import {
  cloneConfig,
  loadConfigForScope,
  saveConfigToPath,
} from "./config";
import {
  addAssistantUsage,
  collectFooterMetrics,
  emptyFooterMetrics,
  updateFooterContext,
  type OpenAIExtendedSupportMetrics,
} from "./metrics";
import { getPriorityPayload, toModelRef } from "./payload";
import {
  clearOpenAIExtendedSupportState,
  publishOpenAIExtendedSupportState,
  resetOpenAIExtendedSupportState,
} from "./state";
import { sanitizeDiagnosticError } from "./format";
import { UsageController } from "./usage-controller";
import type { ModelRef, OpenAIExtendedSupportConfig } from "./types";

export type OpenAIExtendedSupportOptions = {
  /** Directory containing the extension entry point; used to detect project-local installs. */
  extensionDir?: string;
  /** Test/advanced override for Pi's user-level agent directory. */
  agentDir?: string;
};

const DEFAULT_EXTENSION_DIR = dirname(fileURLToPath(import.meta.url));
const USAGE_STATUS_KEY = "openai-extended-support-usage";

function notifyError(
  ctx: Pick<ExtensionContext, "hasUI" | "ui">,
  error: unknown,
): void {
  try {
    if (!ctx.hasUI) return;
    const message = sanitizeDiagnosticError(
      error instanceof Error ? error.message : String(error),
    );
    ctx.ui.notify(message, "error");
  } catch {
    // The context may be stale during session replacement.
  }
}

export function createOpenAIExtendedSupportExtension(
  options: OpenAIExtendedSupportOptions = {},
): ExtensionFactory {
  const extensionDir = options.extensionDir ?? DEFAULT_EXTENSION_DIR;
  const agentDir = options.agentDir;

  return function openAIExtendedSupportExtension(pi: ExtensionAPI): void {
    resetOpenAIExtendedSupportState();

    let config: OpenAIExtendedSupportConfig = cloneConfig();
    let configPath: string | undefined;
    let loadedCwd: string | undefined;
    let currentModel: ModelRef | undefined;
    let metrics: OpenAIExtendedSupportMetrics = emptyFooterMetrics();

    function thinkingLevel(): string | undefined {
      try {
        return pi.getThinkingLevel();
      } catch {
        return undefined;
      }
    }

    function updateUsageStatus(ctx: ExtensionContext): void {
      try {
        if (!ctx.hasUI) return;
        ctx.ui.setStatus(USAGE_STATUS_KEY, usageController.statusLine(ctx));
      } catch {
        // Status updates are best-effort when a context is being replaced.
      }
    }

    function publishState(ctx?: ExtensionContext): void {
      publishOpenAIExtendedSupportState(pi, config, currentModel, {
        usage: {
          enabled: config.usage.enabled,
          ...usageController.state,
        },
        metrics,
      });
      if (ctx) updateUsageStatus(ctx);
    }

    const usageController = new UsageController(
      (ctx) => config,
      (ctx) => publishState(ctx),
      agentDir,
    );

    async function loadForContext(
      ctx: Pick<ExtensionContext, "cwd">,
    ): Promise<void> {
      const loaded = await loadConfigForScope({
        cwd: ctx.cwd,
        extensionDir,
        agentDir,
      });

      config = loaded.config;
      configPath = loaded.path;
      loadedCwd = ctx.cwd;
    }

    async function ensureLoaded(
      ctx: Pick<ExtensionContext, "cwd">,
    ): Promise<void> {
      if (!configPath || loadedCwd !== ctx.cwd) {
        await loadForContext(ctx);
      }
    }

    async function saveCurrent(
      ctx: Pick<ExtensionContext, "cwd">,
    ): Promise<void> {
      if (!configPath || loadedCwd !== ctx.cwd) {
        await loadForContext(ctx);
      }

      if (!configPath) {
        throw new Error("OpenAI Extended Support config path was not resolved");
      }
      if (!config.persistState) return;

      await saveConfigToPath(configPath, config);
    }

    function refreshCurrentModel(ctx: Pick<ExtensionContext, "model">): void {
      currentModel = toModelRef(ctx.model) ?? currentModel;
    }

    function refreshMetricsContext(ctx: ExtensionContext): void {
      metrics = updateFooterContext(metrics, ctx, thinkingLevel());
      publishState();
    }

    pi.registerFlag("fast", {
      description: "Start with OpenAI priority mode enabled",
      type: "boolean",
      default: false,
    });

    pi.registerCommand("fast", {
      description: "Toggle OpenAI priority mode. Usage: /fast [on|off|toggle]",
      getArgumentCompletions: getFastCommandCompletions,
      handler: async (
        args: string,
        ctx: ExtensionCommandContext,
      ): Promise<void> => {
        try {
          await ensureLoaded(ctx);
          refreshCurrentModel(ctx);
          config.enabled = parseFastCommand(args, config.enabled);
          await saveCurrent(ctx);
          publishState(ctx);
        } catch (error) {
          notifyError(ctx, error);
        }
      },
    });

    pi.registerCommand("openai-usage", {
      description: "Show OpenAI subscription usage",
      handler: async (_args, ctx): Promise<void> => {
        try {
          await ensureLoaded(ctx);
          await usageController.refresh(ctx, ctx.model?.id, {
            notify: true,
            force: true,
          });
        } catch (error) {
          notifyError(ctx, error);
        }
      },
    });

    pi.on("session_start", async (_event, ctx) => {
      try {
        currentModel = toModelRef(ctx.model);
        await loadForContext(ctx);

        if (pi.getFlag("fast") === true) {
          config.enabled = true;
          if (config.persistState) await saveCurrent(ctx);
        }

        metrics = collectFooterMetrics(ctx, thinkingLevel());
        publishState(ctx);
        usageController.start(ctx);
      } catch (error) {
        notifyError(ctx, error);
      }
    });

    pi.on("model_select", (event, ctx) => {
      currentModel = toModelRef(event.model) ?? toModelRef(ctx.model);
      metrics = updateFooterContext(metrics, ctx, thinkingLevel());
      publishState(ctx);
      void usageController.refresh(ctx, currentModel?.id, { force: true });
    });

    pi.on("thinking_level_select", (_event, ctx) => {
      refreshMetricsContext(ctx);
    });

    pi.on("agent_start", (_event, ctx) => {
      refreshMetricsContext(ctx);
    });

    pi.on("message_update", (_event, ctx) => {
      refreshMetricsContext(ctx);
    });

    pi.on("turn_end", (event, ctx) => {
      metrics = event.message?.role === "assistant"
        ? addAssistantUsage(metrics, event.message, ctx, thinkingLevel())
        : collectFooterMetrics(ctx, thinkingLevel());
      publishState(ctx);
      void usageController.refresh(ctx);
    });

    pi.on("session_compact", (_event, ctx) => {
      metrics = collectFooterMetrics(ctx, thinkingLevel());
      publishState(ctx);
    });

    pi.on("session_tree", (_event, ctx) => {
      metrics = collectFooterMetrics(ctx, thinkingLevel());
      publishState(ctx);
    });

    pi.on("before_provider_request", (event, ctx) => {
      const model = toModelRef(ctx.model) ?? currentModel;
      return getPriorityPayload(config, model, event.payload);
    });

    pi.on("session_shutdown", (_event, ctx) => {
      try {
        usageController.shutdown();
        if (ctx.hasUI) ctx.ui.setStatus(USAGE_STATUS_KEY, undefined);
      } catch (error) {
        notifyError(ctx, error);
      } finally {
        clearOpenAIExtendedSupportState(pi);
      }
    });
  };
}

const openAIExtendedSupportExtension = createOpenAIExtendedSupportExtension();

export default openAIExtendedSupportExtension;
