export const PACKAGE_NAME = "openai-extended-support";
export const DEFAULT_SERVICE_TIER = "priority";

export const SUPPORTED_PROVIDERS = ["openai", "openai-codex"] as const;
export type SupportedProvider = (typeof SUPPORTED_PROVIDERS)[number];

export type PriorityTarget = {
  provider: string;
  model: string;
  serviceTier?: string;
};

export type UsageConfig = {
  enabled: boolean;
  refreshIntervalMs: number;
  showOnlyOnSubscriptionModels: boolean;
  showResetTimes: boolean;
  showStatus: boolean;
};

export type OpenAIExtendedSupportConfig = {
  enabled: boolean;
  persistState: boolean;
  targets: PriorityTarget[];
  usage: UsageConfig;
};

export type ModelRef = {
  provider: string;
  id: string;
};

export type ConfigScope = "user" | "project";

export type ResolvedConfigPath = {
  scope: ConfigScope;
  path: string;
};
