import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { OpenAIExtendedSupportConfig } from "./types";
import {
  formatResetCountdown,
  formatUsageSnapshot,
  getAuthFile,
  parseUsageSnapshot,
  requestCodexUsage,
  usageScopeForModel,
  type UsageSnapshot,
} from "./usage";
import { sanitizeDiagnosticError } from "./format";

export type UsageControllerState = {
  snapshot: UsageSnapshot | undefined;
  updatedAt: number | undefined;
  error: string | undefined;
  loading: boolean;
};

type UsageRefreshOptions = {
  notify?: boolean;
  force?: boolean;
};

type QueuedUsageRefresh = {
  ctx: ExtensionContext;
  generation: number;
  modelId?: string;
  notify?: boolean;
  force?: boolean;
};

const STALE_EXTENSION_CONTEXT_MESSAGE = "This extension ctx is stale";

function isStaleExtensionContextError(error: unknown): boolean {
  return error instanceof Error && error.message.includes(STALE_EXTENSION_CONTEXT_MESSAGE);
}

function isOpenAISubscriptionModel(
  ctx: ExtensionContext,
  cfg: OpenAIExtendedSupportConfig,
  isUsingOAuth?: boolean,
): boolean {
  const model = ctx.model;
  if (!model || (model.provider !== "openai" && model.provider !== "openai-codex")) {
    return false;
  }
  if (!cfg.usage.showOnlyOnSubscriptionModels) return true;

  try {
    return isUsingOAuth ?? ctx.modelRegistry.isUsingOAuth(model);
  } catch {
    return false;
  }
}

export class UsageController {
  private usageSnapshot: UsageSnapshot | undefined;
  private usageUpdatedAt: number | undefined;
  private usageError: string | undefined;
  private usageLastFetchAt: number | undefined;
  private usageTimer: ReturnType<typeof setInterval> | undefined;
  private usageRefreshInFlight = false;
  private queuedUsageRefresh: QueuedUsageRefresh | undefined;
  private shuttingDown = false;
  private usageAbortController: AbortController | undefined;
  private sessionAbortSignal: AbortSignal | undefined;
  private sessionAbortHandler: (() => void) | undefined;
  private sessionGeneration = 0;
  private loading = false;
  private currentContext: ExtensionContext | undefined;
  private readonly getConfig: (ctx: ExtensionContext) => OpenAIExtendedSupportConfig;
  private readonly onStateChange: (ctx?: ExtensionContext) => void;
  private readonly agentDir: string | undefined;

  constructor(
    getConfig: (ctx: ExtensionContext) => OpenAIExtendedSupportConfig,
    onStateChange: (ctx?: ExtensionContext) => void,
    agentDir?: string,
  ) {
    this.getConfig = getConfig;
    this.onStateChange = onStateChange;
    this.agentDir = agentDir;
  }

  get state(): UsageControllerState {
    return Object.freeze({
      snapshot: this.usageSnapshot,
      updatedAt: this.usageUpdatedAt,
      error: this.usageError,
      loading: this.loading,
    });
  }

  statusLine(ctx: ExtensionContext): string | undefined {
    const cfg = this.getConfig(ctx);
    if (!cfg.usage.enabled || !cfg.usage.showStatus) return undefined;
    if (!isOpenAISubscriptionModel(ctx, cfg)) return undefined;
    if (this.usageError || !this.usageSnapshot) return undefined;
    if (this.usageSnapshot.scope !== usageScopeForModel(ctx.model?.id)) return undefined;
    return formatUsageSnapshot(this.usageSnapshot, cfg.usage);
  }

  formatStatus(ctx: ExtensionContext): string {
    const cfg = this.getConfig(ctx);
    if (!cfg.usage.enabled) return "Usage display is disabled.";
    if (!isOpenAISubscriptionModel(ctx, cfg)) {
      return "Usage hidden: current model is not an OpenAI subscription model.";
    }
    if (this.loading) return "Usage: fetching…";
    if (this.usageError) return `Usage unavailable: ${this.usageError}`;
    if (!this.usageSnapshot || this.usageSnapshot.scope !== usageScopeForModel(ctx.model?.id)) {
      return "Usage unavailable.";
    }

    const stale =
      this.usageUpdatedAt && Date.now() - this.usageUpdatedAt > cfg.usage.refreshIntervalMs * 2
        ? ` | stale ${formatResetCountdown((Date.now() - this.usageUpdatedAt) / 1000)}`
        : "";
    return `${formatUsageSnapshot(this.usageSnapshot, cfg.usage)}${stale}`;
  }

  formatDebug(ctx: ExtensionContext): string {
    const cfg = this.getConfig(ctx);
    return [
      `Usage enabled: ${cfg.usage.enabled}`,
      `Current model: ${ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "none"}`,
      `Current model eligible: ${isOpenAISubscriptionModel(ctx, cfg)}`,
      `Requires subscription model: ${cfg.usage.showOnlyOnSubscriptionModels}`,
      `Last fetch: ${this.usageLastFetchAt ? new Date(this.usageLastFetchAt).toLocaleTimeString() : "never"}`,
      `Last successful update: ${this.usageUpdatedAt ? new Date(this.usageUpdatedAt).toLocaleTimeString() : "never"}`,
      `Last error: ${this.usageError ?? "none"}`,
      `Refresh interval: ${cfg.usage.refreshIntervalMs}ms`,
      `Endpoint: https://chatgpt.com/backend-api/wham/usage`,
    ].join("\n");
  }

  private isGenerationCurrent(generation: number): boolean {
    return !this.shuttingDown && generation === this.sessionGeneration;
  }

  private emitState(ctx?: ExtensionContext): void {
    if (ctx) this.currentContext = ctx;
    this.onStateChange(this.currentContext);
  }

  private clearSnapshot(error: string | undefined): void {
    this.usageSnapshot = undefined;
    this.usageUpdatedAt = undefined;
    this.usageError = error;
    this.loading = false;
    this.emitState();
  }

  private deactivateGeneration(generation: number): void {
    if (generation !== this.sessionGeneration) return;
    this.shuttingDown = true;
    this.sessionGeneration++;
    this.queuedUsageRefresh = undefined;
    this.usageAbortController?.abort();
    this.usageAbortController = undefined;
    this.loading = false;
    this.stopTimer();
  }

  private handleStaleContextError(error: unknown, generation: number): boolean {
    if (!isStaleExtensionContextError(error)) return false;
    this.deactivateGeneration(generation);
    return true;
  }

  private notify(ctx: ExtensionContext, message: string, level: "info" | "warning"): void {
    try {
      if (ctx.hasUI) ctx.ui.notify(message, level);
    } catch (error) {
      this.handleStaleContextError(error, this.sessionGeneration);
    }
  }

  async refresh(
    ctx: ExtensionContext,
    modelId?: string,
    options: UsageRefreshOptions = {},
    generation = this.sessionGeneration,
  ): Promise<void> {
    if (!this.isGenerationCurrent(generation)) return;

    let resolvedModelId = modelId;
    try {
      if (!ctx.hasUI) return;
      this.currentContext = ctx;
      resolvedModelId ??= ctx.model?.id;
    } catch (error) {
      this.handleStaleContextError(error, generation);
      return;
    }

    if (this.usageRefreshInFlight) {
      const queued =
        this.queuedUsageRefresh?.generation === generation ? this.queuedUsageRefresh : undefined;
      this.queuedUsageRefresh = {
        ctx,
        generation,
        modelId: resolvedModelId,
        notify: queued?.notify || options.notify,
        force: queued?.force || options.force,
      };
      return;
    }

    this.usageRefreshInFlight = true;
    this.loading = true;
    this.emitState();
    try {
      const cfg = this.getConfig(ctx);
      if (!this.isGenerationCurrent(generation)) return;

      if (!cfg.usage.enabled) {
        this.clearSnapshot("Usage display is disabled.");
        if (options.notify) this.notify(ctx, this.formatStatus(ctx), "warning");
        return;
      }
      if (!isOpenAISubscriptionModel(ctx, cfg)) {
        this.clearSnapshot(undefined);
        if (options.notify) this.notify(ctx, this.formatStatus(ctx), "warning");
        return;
      }

      const shouldThrottle =
        !options.force &&
        !options.notify &&
        this.usageLastFetchAt !== undefined &&
        Date.now() - this.usageLastFetchAt < cfg.usage.refreshIntervalMs;
      if (shouldThrottle) return;

      this.usageLastFetchAt = Date.now();
      this.usageAbortController = new AbortController();
      const timeoutSignal = AbortSignal.timeout(10_000);
      const sessionSignal = ctx.signal;
      const signal = sessionSignal
        ? AbortSignal.any([sessionSignal, timeoutSignal, this.usageAbortController.signal])
        : AbortSignal.any([timeoutSignal, this.usageAbortController.signal]);
      const data = await requestCodexUsage(ctx, signal, this.agentDir);
      if (!this.isGenerationCurrent(generation)) return;

      let currentModelId: string | undefined;
      try {
        currentModelId = ctx.model?.id;
      } catch (error) {
        this.handleStaleContextError(error, generation);
        return;
      }
      if (currentModelId !== resolvedModelId) return;

      this.usageSnapshot = data ? parseUsageSnapshot(data, resolvedModelId) : undefined;
      this.usageUpdatedAt = this.usageSnapshot ? Date.now() : undefined;
      this.usageError = data
        ? undefined
        : `Missing openai-codex OAuth credentials in ${getAuthFile(this.agentDir)}.`;
      this.loading = false;
      this.emitState();
      if (options.notify) {
        this.notify(
          ctx,
          this.formatStatus(ctx),
          this.usageSnapshot ? "info" : "warning",
        );
      }
    } catch (error) {
      if (this.handleStaleContextError(error, generation) || !this.isGenerationCurrent(generation)) {
        return;
      }
      this.usageError = sanitizeDiagnosticError(
        error instanceof Error ? error.message : String(error),
      );
      this.usageSnapshot = undefined;
      this.usageUpdatedAt = undefined;
      this.loading = false;
      this.emitState();
      if (options.notify) this.notify(ctx, this.formatStatus(ctx), "warning");
    } finally {
      if (generation !== this.sessionGeneration) return;
      this.usageAbortController = undefined;
      this.usageRefreshInFlight = false;
      const wasLoading = this.loading;
      this.loading = false;
      if (wasLoading) this.emitState();
      const next = this.queuedUsageRefresh;
      this.queuedUsageRefresh = undefined;
      if (next && !this.shuttingDown && next.generation === this.sessionGeneration) {
        void this.refresh(
          next.ctx,
          next.modelId,
          { notify: next.notify, force: next.force },
          next.generation,
        );
      }
    }
  }

  private stopTimer(): void {
    if (this.usageTimer) clearInterval(this.usageTimer);
    this.usageTimer = undefined;
    if (this.sessionAbortSignal && this.sessionAbortHandler) {
      this.sessionAbortSignal.removeEventListener("abort", this.sessionAbortHandler);
    }
    this.sessionAbortSignal = undefined;
    this.sessionAbortHandler = undefined;
  }

  start(ctx: ExtensionContext): void {
    this.usageAbortController?.abort();
    this.queuedUsageRefresh = undefined;
    this.usageRefreshInFlight = false;
    this.stopTimer();
    const generation = ++this.sessionGeneration;
    this.shuttingDown = false;

    let cfg: OpenAIExtendedSupportConfig;
    try {
      cfg = this.getConfig(ctx);
      if (!ctx.hasUI) return;
      this.currentContext = ctx;
    } catch (error) {
      this.handleStaleContextError(error, generation);
      return;
    }

    if (!cfg.usage.enabled) {
      this.clearSnapshot("Usage display is disabled.");
      return;
    }

    const sessionSignal = ctx.signal;
    if (sessionSignal?.aborted) {
      this.deactivateGeneration(generation);
      return;
    }
    this.sessionAbortSignal = sessionSignal;
    this.sessionAbortHandler = () => this.deactivateGeneration(generation);
    sessionSignal?.addEventListener("abort", this.sessionAbortHandler, { once: true });
    void this.refresh(ctx, undefined, { force: true }, generation);
    this.usageTimer = setInterval(() => {
      if (!this.isGenerationCurrent(generation)) return;
      if (sessionSignal?.aborted) {
        this.deactivateGeneration(generation);
        return;
      }
      void this.refresh(ctx, undefined, undefined, generation);
    }, cfg.usage.refreshIntervalMs);
    this.usageTimer.unref?.();
  }

  shutdown(): void {
    this.shuttingDown = true;
    this.sessionGeneration++;
    this.queuedUsageRefresh = undefined;
    this.usageAbortController?.abort();
    this.usageAbortController = undefined;
    this.usageRefreshInFlight = false;
    this.loading = false;
    this.stopTimer();
  }
}
