export type PiThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh";

export type KiloThinkingLevelMap = Partial<Record<PiThinkingLevel, string | null>>;

export type KiloThinkingVariant = {
  reasoning?: {
    enabled?: boolean;
    effort?: string;
  };
};

export type KiloThinkingModel = {
  id: string;
  opencode?: {
    variants?: Record<string, KiloThinkingVariant>;
  };
};

export function mapVariantEffort(
  variants: Record<string, KiloThinkingVariant> | undefined,
  key: string,
): string | undefined {
  const variant = variants?.[key];
  if (!variant) return undefined;
  const reasoning = variant.reasoning;
  if (!reasoning) return key;
  if (reasoning.enabled === false || reasoning.effort === "none") return "none";
  return reasoning.effort ?? key;
}

export function thinkingLevelMapFromVariants(
  variants: Record<string, KiloThinkingVariant> | undefined,
): KiloThinkingLevelMap | undefined {
  if (!variants || Object.keys(variants).length === 0) return undefined;

  const map: KiloThinkingLevelMap = {};
  const off = mapVariantEffort(variants, "none") ?? mapVariantEffort(variants, "instant");
  // Missing off/none must be null. An unset key makes Pi send "none", which
  // models such as kilo-internal/galaxy reject.
  map.off = off === undefined ? null : off;

  for (const level of ["minimal", "low", "medium", "high", "xhigh"] as const) {
    const effort = mapVariantEffort(variants, level);
    map[level] = effort === undefined ? null : effort;
  }

  // Pi has no separate "max" thinking level. Expose a Kilo/OpenCode max
  // variant as Pi's xhigh when xhigh is absent.
  if (map.xhigh === null) {
    const max = mapVariantEffort(variants, "max");
    if (max !== undefined) map.xhigh = max;
  }

  return map;
}

export function getKiloThinkingLevelMap(model: KiloThinkingModel): KiloThinkingLevelMap | undefined {
  const fromVariants = thinkingLevelMapFromVariants(model.opencode?.variants);
  if (fromVariants) return fromVariants;

  if (model.id === "deepseek/deepseek-v4-pro") {
    return {
      minimal: null,
      low: null,
      medium: null,
      high: "high",
      xhigh: "max",
    };
  }

  // Safety net for the current frontier OpenAI model while Kilo/OpenRouter
  // model metadata is catching up.
  if (model.id.includes("gpt-5.5")) {
    return {
      off: "none",
      minimal: null,
      low: "low",
      medium: "medium",
      high: "high",
      xhigh: "xhigh",
    };
  }

  return undefined;
}
