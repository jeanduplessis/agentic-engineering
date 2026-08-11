import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { OpenAIExtendedSupportConfig } from "./types";
import type { OpenAIExtendedSupportMetrics } from "./metrics";
import type { UsageSnapshot } from "./usage";
import { findMatchingTarget } from "./payload";
import type { ModelRef } from "./types";

/** Event emitted whenever OpenAI Extended Support state changes. */
export const EXTENDED_SUPPORT_STATE_EVENT = "openai-extended-support:state";

/** Global property containing the latest state for direct reads. */
export const EXTENDED_SUPPORT_GLOBAL_KEY = "piOpenAIExtendedSupport";

export type OpenAIExtendedSupportUsageState = Readonly<{
  enabled: boolean;
  snapshot: UsageSnapshot | undefined;
  updatedAt: number | undefined;
  error: string | undefined;
  loading: boolean;
}>;

export type OpenAIExtendedSupportState = Readonly<{
  /** The requested/persisted state, independent of model support. */
  desiredActive: boolean;
  /** Whether the selected model is in the configured target list. */
  supported: boolean;
  /** Whether the request will inject service_tier for the selected model. */
  active: boolean;
  /** The currently selected model, when available. */
  model: ModelRef | undefined;
  /** The service tier that will be sent for the current model, when active. */
  serviceTier: string | undefined;
  /** Latest subscription quota data, when usage polling is enabled. */
  usage: OpenAIExtendedSupportUsageState;
  /** Values for an optional external footer/widget consumer. */
  metrics: Readonly<OpenAIExtendedSupportMetrics>;
}>;

export type OpenAIExtendedSupportStateOptions = {
  usage?: Partial<OpenAIExtendedSupportUsageState>;
  metrics?: OpenAIExtendedSupportMetrics;
};

type PiGlobal = typeof globalThis & {
  [EXTENDED_SUPPORT_GLOBAL_KEY]?: OpenAIExtendedSupportState;
};

function getPiGlobal(): PiGlobal {
  return globalThis as PiGlobal;
}

function emptyMetrics(): OpenAIExtendedSupportMetrics {
  return {
    totals: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 },
    context: { tokens: undefined, contextWindow: undefined, percent: undefined },
    thinkingLevel: undefined,
  };
}

function freezeMetrics(
  metrics: OpenAIExtendedSupportMetrics | undefined,
): Readonly<OpenAIExtendedSupportMetrics> {
  const value = metrics ?? emptyMetrics();
  return Object.freeze({
    totals: Object.freeze({ ...value.totals }),
    context: Object.freeze({ ...value.context }),
    thinkingLevel: value.thinkingLevel,
  });
}

function freezeUsage(
  config: OpenAIExtendedSupportConfig,
  usage: Partial<OpenAIExtendedSupportUsageState> | undefined,
): OpenAIExtendedSupportUsageState {
  const snapshot = usage?.snapshot;
  return Object.freeze({
    enabled: usage?.enabled ?? config.usage?.enabled ?? false,
    snapshot: snapshot
      ? Object.freeze({ ...snapshot })
      : undefined,
    updatedAt: usage?.updatedAt,
    error: usage?.error,
    loading: usage?.loading ?? false,
  });
}

export function getOpenAIExtendedSupportState(
  config: OpenAIExtendedSupportConfig,
  model: ModelRef | undefined,
  options: OpenAIExtendedSupportStateOptions = {},
): OpenAIExtendedSupportState {
  const target = findMatchingTarget(model, config.targets);
  const desiredActive = config.enabled;
  const supported = target !== undefined;
  const active = desiredActive && supported;

  return Object.freeze({
    desiredActive,
    supported,
    active,
    model: model ? Object.freeze({ ...model }) : undefined,
    serviceTier: active ? target?.serviceTier : undefined,
    usage: freezeUsage(config, options.usage),
    metrics: freezeMetrics(options.metrics),
  });
}

/** Read the latest state without subscribing to the event bus. */
export function readOpenAIExtendedSupportState():
  | OpenAIExtendedSupportState
  | undefined {
  return getPiGlobal()[EXTENDED_SUPPORT_GLOBAL_KEY];
}

/** Clear state without emitting an event during runtime initialization. */
export function resetOpenAIExtendedSupportState(): void {
  getPiGlobal()[EXTENDED_SUPPORT_GLOBAL_KEY] = undefined;
}

export function publishOpenAIExtendedSupportState(
  pi: Pick<ExtensionAPI, "events">,
  config: OpenAIExtendedSupportConfig,
  model: ModelRef | undefined,
  options: OpenAIExtendedSupportStateOptions = {},
): OpenAIExtendedSupportState {
  const state = getOpenAIExtendedSupportState(config, model, options);
  getPiGlobal()[EXTENDED_SUPPORT_GLOBAL_KEY] = state;
  pi.events.emit(EXTENDED_SUPPORT_STATE_EVENT, state);
  return state;
}

export function clearOpenAIExtendedSupportState(
  pi: Pick<ExtensionAPI, "events">,
): void {
  resetOpenAIExtendedSupportState();
  pi.events.emit(EXTENDED_SUPPORT_STATE_EVENT, undefined);
}
