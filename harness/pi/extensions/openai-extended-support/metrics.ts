import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

export type FooterTotals = {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  cost: number;
};

export type FooterContext = {
  tokens: number | undefined;
  contextWindow: number | undefined;
  percent: number | null | undefined;
};

export type OpenAIExtendedSupportMetrics = {
  totals: FooterTotals;
  context: FooterContext;
  thinkingLevel: string | undefined;
};

function emptyTotals(): FooterTotals {
  return { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 };
}

export function emptyFooterMetrics(): OpenAIExtendedSupportMetrics {
  return {
    totals: emptyTotals(),
    context: { tokens: undefined, contextWindow: undefined, percent: undefined },
    thinkingLevel: undefined,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function addNumber(current: number, value: unknown): number {
  const next = finiteNumber(value);
  return next === undefined ? current : current + next;
}

function contextFromContext(
  ctx: ExtensionContext,
  previous: FooterContext,
): FooterContext {
  try {
    const usage = ctx.getContextUsage();
    if (!usage || !isRecord(usage)) return previous;
    const percent = usage.percent === null ? null : finiteNumber(usage.percent);
    return {
      tokens: finiteNumber(usage.tokens),
      contextWindow: finiteNumber(usage.contextWindow),
      percent,
    };
  } catch {
    // A context can become stale during session replacement. Keep the last values.
    return previous;
  }
}

export function collectFooterMetrics(
  ctx: ExtensionContext,
  thinkingLevel: string | undefined,
): OpenAIExtendedSupportMetrics {
  const totals = emptyTotals();
  try {
    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type !== "message" || entry.message.role !== "assistant") continue;
      const usage = entry.message.usage;
      if (!usage) continue;
      totals.input = addNumber(totals.input, usage.input);
      totals.output = addNumber(totals.output, usage.output);
      totals.cacheRead = addNumber(totals.cacheRead, usage.cacheRead);
      totals.cacheWrite = addNumber(totals.cacheWrite, usage.cacheWrite);
      totals.cost = addNumber(totals.cost, usage.cost?.total);
    }
  } catch {
    // Metrics are advisory and must not break session startup or replacement.
  }

  return {
    totals,
    context: contextFromContext(ctx, {
      tokens: undefined,
      contextWindow: undefined,
      percent: undefined,
    }),
    thinkingLevel,
  };
}

export function updateFooterContext(
  metrics: OpenAIExtendedSupportMetrics,
  ctx: ExtensionContext,
  thinkingLevel = metrics.thinkingLevel,
): OpenAIExtendedSupportMetrics {
  return {
    totals: { ...metrics.totals },
    context: contextFromContext(ctx, metrics.context),
    thinkingLevel,
  };
}

export function addAssistantUsage(
  metrics: OpenAIExtendedSupportMetrics,
  message: unknown,
  ctx: ExtensionContext,
  thinkingLevel = metrics.thinkingLevel,
): OpenAIExtendedSupportMetrics {
  if (!isRecord(message) || message.role !== "assistant" || !isRecord(message.usage)) {
    return updateFooterContext(metrics, ctx, thinkingLevel);
  }

  const usage = message.usage;
  return {
    totals: {
      input: addNumber(metrics.totals.input, usage.input),
      output: addNumber(metrics.totals.output, usage.output),
      cacheRead: addNumber(metrics.totals.cacheRead, usage.cacheRead),
      cacheWrite: addNumber(metrics.totals.cacheWrite, usage.cacheWrite),
      cost: addNumber(
        metrics.totals.cost,
        isRecord(usage.cost) ? usage.cost.total : undefined,
      ),
    },
    context: contextFromContext(ctx, metrics.context),
    thinkingLevel,
  };
}
