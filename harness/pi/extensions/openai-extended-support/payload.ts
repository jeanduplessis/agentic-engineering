import {
  DEFAULT_SERVICE_TIER,
  SUPPORTED_PROVIDERS,
  type ModelRef,
  type OpenAIExtendedSupportConfig,
  type PriorityTarget,
} from "./types";

const SUPPORTED_PROVIDER_SET = new Set<string>(SUPPORTED_PROVIDERS);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function toModelRef(model: unknown): ModelRef | undefined {
  if (!isRecord(model)) return undefined;

  const { provider, id } = model;
  if (typeof provider !== "string" || typeof id !== "string") return undefined;

  const normalizedProvider = provider.trim().toLowerCase();
  const normalizedId = id.trim();
  if (
    !normalizedProvider ||
    !normalizedId ||
    normalizedId.length > 200 ||
    /[\u0000-\u001f\u007f-\u009f]/.test(normalizedId)
  )
    return undefined;

  return { provider: normalizedProvider, id: normalizedId };
}

export function isSupportedProvider(provider: string): boolean {
  return SUPPORTED_PROVIDER_SET.has(provider.trim().toLowerCase());
}

export function findMatchingTarget(
  model: ModelRef | undefined,
  targets: PriorityTarget[],
): PriorityTarget | undefined {
  if (!model) return undefined;
  const provider = model.provider.trim().toLowerCase();
  const id = model.id.trim();
  if (
    !provider ||
    !id ||
    id.length > 200 ||
    /[\u0000-\u001f\u007f-\u009f]/.test(id) ||
    !isSupportedProvider(provider)
  )
    return undefined;

  return targets.find(
    (target) =>
      target.provider.trim().toLowerCase() === provider &&
      target.model === id &&
      isSupportedProvider(target.provider),
  );
}

export function applyPriorityPayload(
  payload: unknown,
  serviceTier: string,
): unknown | undefined {
  if (!isRecord(payload)) return undefined;

  return {
    ...payload,
    service_tier: serviceTier || DEFAULT_SERVICE_TIER,
  };
}

export function getPriorityPayload(
  config: OpenAIExtendedSupportConfig,
  model: ModelRef | undefined,
  payload: unknown,
): unknown | undefined {
  if (!config.enabled) return undefined;

  const target = findMatchingTarget(model, config.targets);
  if (!target) return undefined;

  return applyPriorityPayload(
    payload,
    target.serviceTier ?? DEFAULT_SERVICE_TIER,
  );
}
