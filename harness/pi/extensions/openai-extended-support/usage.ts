import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export type UsageWindow = {
  used_percent?: number | null;
  reset_after_seconds?: number | null;
  reset_at?: number | null;
};

export type RateLimitBucket = {
  allowed?: boolean;
  limit_reached?: boolean;
  primary_window?: UsageWindow | null;
  secondary_window?: UsageWindow | null;
};

export type CodexUsageResponse = {
  rate_limit?: RateLimitBucket | null;
  additional_rate_limits?: Record<string, unknown> | unknown[] | null;
};

export type UsageScope = "default" | "spark";

export type UsageSnapshot = {
  capturedAt: number;
  scope: UsageScope;
  fiveHourLeftPercent: number | null;
  sevenDayLeftPercent: number | null;
  fiveHourResetInSeconds: number | null;
  sevenDayResetInSeconds: number | null;
  isLimited: boolean;
};

export type CodexCredentials = {
  accessToken: string;
  accountId: string;
};

export type CodexCredentialsWithSource = CodexCredentials & {
  source: "modelRegistry" | "authFile";
};

export const USAGE_URL = "https://chatgpt.com/backend-api/wham/usage";
export const SPARK_MODEL_ID = "gpt-5.3-codex-spark";
const SPARK_LIMIT_NAME = "GPT-5.3-Codex-Spark";

export function getAuthFile(agentDir = getAgentDir()): string {
  return join(agentDir, "auth.json");
}

/** Kept for consumers that need to display the conventional auth location. */
export const AUTH_FILE = getAuthFile();

type ResetClockFormatters = {
  time: Intl.DateTimeFormat;
  weekday: Intl.DateTimeFormat;
  date: Intl.DateTimeFormat;
};
const RESET_CLOCK_FORMATTER_CACHE_LIMIT = 4;
const resetClockFormatters = new Map<string, ResetClockFormatters>();

function currentTimeZoneKey(date: Date): string {
  const zoneLabel = /\(([^)]+)\)$/.exec(date.toString())?.[1] ?? "";
  return `${process.env.TZ ?? ""}:${date.getTimezoneOffset()}:${zoneLabel}`;
}

function getResetClockFormatters(now: Date, reset: Date): ResetClockFormatters {
  const timeZoneKey = `${currentTimeZoneKey(now)}:${reset.getTimezoneOffset()}`;
  let formatters = resetClockFormatters.get(timeZoneKey);
  if (!formatters) {
    formatters = {
      time: new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }),
      weekday: new Intl.DateTimeFormat(undefined, { weekday: "short" }),
      date: new Intl.DateTimeFormat(undefined, { month: "numeric", day: "numeric" }),
    };
    resetClockFormatters.set(timeZoneKey, formatters);
    while (resetClockFormatters.size > RESET_CLOCK_FORMATTER_CACHE_LIMIT) {
      const oldestKey = resetClockFormatters.keys().next().value;
      if (oldestKey === undefined) break;
      resetClockFormatters.delete(oldestKey);
    }
  }
  return formatters;
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

function usedToLeftPercent(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return clampPercent(100 - value);
}

export function formatResetCountdown(seconds: number | null): string | null {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return null;
  const total = Math.max(0, Math.round(seconds));
  const days = Math.floor(total / 86_400);
  const hours = Math.floor((total % 86_400) / 3_600);
  const minutes = Math.floor((total % 3_600) / 60);
  const secs = total % 60;
  if (days > 0) return `${days}d${hours}h`;
  if (hours > 0) return `${hours}h${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${secs}s`;
}

function formatResetClock(
  seconds: number | null,
  options?: { includeDate?: boolean },
  now = Date.now(),
): string | null {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return null;
  const resetDate = new Date(now + seconds * 1000);
  const currentDate = new Date(now);
  const formatters = getResetClockFormatters(currentDate, resetDate);
  const time = formatters.time.format(resetDate);
  if (!options?.includeDate && resetDate.toDateString() === currentDate.toDateString()) return time;
  const weekday = formatters.weekday.format(resetDate);
  if (!options?.includeDate) return `${weekday} ${time}`;
  const date = formatters.date.format(resetDate);
  return `${weekday} ${date} ${time}`;
}

function formatCompactReset(
  label: string,
  seconds: number | null,
  options?: { includeDate?: boolean },
  now = Date.now(),
): string | null {
  const countdown = formatResetCountdown(seconds);
  const clock = formatResetClock(seconds, options, now);
  return countdown && clock ? `${label} ↺ ${countdown} - ${clock}` : null;
}

function isAbortSignal(value: unknown): value is AbortSignal {
  return typeof value === "object" && value !== null && "aborted" in value;
}

function waitForSignal<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return operation;
  if (signal.aborted) return Promise.reject(signal.reason ?? new Error("Operation was aborted."));

  return new Promise<T>((resolve, reject) => {
    const onAbort = () => {
      cleanup();
      reject(signal.reason ?? new Error("Operation was aborted."));
    };
    const cleanup = () => signal.removeEventListener("abort", onAbort);
    signal.addEventListener("abort", onAbort, { once: true });
    void operation.then(
      (value) => {
        cleanup();
        resolve(value);
      },
      (error: unknown) => {
        cleanup();
        reject(error);
      },
    );
  });
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  return Buffer.from(padded, "base64").toString("utf8");
}

export function extractAccountIdFromJwt(token: string): string | undefined {
  try {
    const [, payload] = token.split(".");
    if (!payload) return undefined;
    const parsed = JSON.parse(decodeBase64Url(payload)) as unknown;
    const auth = asObject(parsed)?.["https://api.openai.com/auth"];
    const accountId = asObject(auth)?.chatgpt_account_id;
    return typeof accountId === "string" && accountId.trim() ? accountId.trim() : undefined;
  } catch {
    return undefined;
  }
}

export function parseCodexRegistryCredentials(
  raw: string | undefined,
): CodexCredentials | undefined {
  const value = raw?.trim();
  if (!value) return undefined;

  try {
    const parsed = JSON.parse(value) as unknown;
    const record = asObject(parsed);
    if (record) {
      const accessToken =
        typeof record.access === "string"
          ? record.access
          : typeof record.token === "string"
            ? record.token
            : undefined;
      const explicitAccountId =
        typeof record.accountId === "string"
          ? record.accountId
          : typeof record.account_id === "string"
            ? record.account_id
            : undefined;
      const accountId = explicitAccountId ?? (accessToken ? extractAccountIdFromJwt(accessToken) : undefined);
      if (accessToken?.trim() && accountId?.trim()) {
        return { accessToken: accessToken.trim(), accountId: accountId.trim() };
      }
    }
  } catch {
    // A plain bearer token is valid for openai-codex in pi.
  }

  const accountId = extractAccountIdFromJwt(value);
  return accountId ? { accessToken: value, accountId } : undefined;
}

type AuthEntry = {
  type?: string;
  access?: string | null;
  accountId?: string | null;
  account_id?: string | null;
  expires?: number | null;
};

export async function readCodexAuth(
  agentDir = getAgentDir(),
): Promise<CodexCredentials | undefined> {
  try {
    const raw = await readFile(getAuthFile(agentDir), "utf8");
    const parsed = JSON.parse(raw) as Record<string, AuthEntry | undefined>;
    const entry = parsed["openai-codex"];
    if (entry?.type !== "oauth") return undefined;
    if (typeof entry.expires === "number") {
      const expiresMs = entry.expires < 1_000_000_000_000 ? entry.expires * 1000 : entry.expires;
      if (Date.now() >= expiresMs) return undefined;
    }
    const accessToken = entry.access?.trim();
    const accountId = (entry.accountId ?? entry.account_id)?.trim();
    return accessToken && accountId ? { accessToken, accountId } : undefined;
  } catch {
    return undefined;
  }
}

export async function getCodexCredentials(
  ctx?: Pick<ExtensionContext, "modelRegistry">,
  signal?: AbortSignal,
  agentDir?: string,
): Promise<CodexCredentialsWithSource | undefined> {
  if (signal?.aborted) throw signal.reason ?? new Error("Operation was aborted.");

  let registryToken: string | undefined;
  try {
    const registryRequest = ctx?.modelRegistry?.getApiKeyForProvider("openai-codex");
    registryToken = registryRequest
      ? await waitForSignal(registryRequest.catch(() => undefined), signal)
      : undefined;
  } catch (error) {
    if (signal?.aborted) throw error;
  }
  const registryCredentials = parseCodexRegistryCredentials(registryToken);
  if (registryCredentials) return { ...registryCredentials, source: "modelRegistry" };

  const auth = await readCodexAuth(agentDir);
  return auth ? { ...auth, source: "authFile" } : undefined;
}

export async function requestCodexUsage(
  ctxOrSignal?: ExtensionContext | AbortSignal,
  signal?: AbortSignal,
  agentDir?: string,
): Promise<CodexUsageResponse | undefined> {
  const ctx = isAbortSignal(ctxOrSignal) ? undefined : ctxOrSignal;
  const requestSignal = isAbortSignal(ctxOrSignal) ? ctxOrSignal : signal;
  const credentials = await getCodexCredentials(ctx, requestSignal, agentDir);
  if (!credentials) return undefined;

  const response = await fetch(USAGE_URL, {
    headers: {
      accept: "*/*",
      authorization: `Bearer ${credentials.accessToken}`,
      "chatgpt-account-id": credentials.accountId,
    },
    signal: requestSignal,
  });
  if (!response.ok) throw new Error(`Codex usage request failed (${response.status})`);
  return (await response.json()) as CodexUsageResponse;
}

function normalizeRateLimitBucket(value: unknown): RateLimitBucket | null {
  const record = asObject(value);
  if (!record) return null;
  if (
    !("primary_window" in record || "secondary_window" in record || "limit_reached" in record || "allowed" in record)
  )
    return null;
  return record as RateLimitBucket;
}

function extractSparkRateLimitFromEntry(value: unknown): RateLimitBucket | null {
  const record = asObject(value);
  if (!record || record.limit_name !== SPARK_LIMIT_NAME) return null;
  return normalizeRateLimitBucket(record.rate_limit);
}

function findSparkRateLimitBucket(data: CodexUsageResponse): RateLimitBucket | null {
  const additional = data.additional_rate_limits;
  if (Array.isArray(additional)) {
    for (const entry of additional) {
      const bucket = extractSparkRateLimitFromEntry(entry);
      if (bucket) return bucket;
    }
  } else {
    const map = asObject(additional);
    if (map) {
      for (const value of Object.values(map)) {
        const bucket = extractSparkRateLimitFromEntry(value);
        if (bucket) return bucket;
      }
    }
  }
  return null;
}

function getResetSeconds(window: UsageWindow | null | undefined, now: number): number | null {
  if (typeof window?.reset_after_seconds === "number" && Number.isFinite(window.reset_after_seconds))
    return Math.max(0, window.reset_after_seconds);
  if (typeof window?.reset_at !== "number" || !Number.isFinite(window.reset_at)) return null;
  const resetAtSeconds = window.reset_at > 100_000_000_000 ? window.reset_at / 1000 : window.reset_at;
  return Math.max(0, resetAtSeconds - now / 1000);
}

export function usageScopeForModel(modelId: string | undefined): UsageScope {
  return modelId === SPARK_MODEL_ID ? "spark" : "default";
}

export function parseUsageSnapshot(
  data: CodexUsageResponse,
  modelId: string | undefined,
  now = Date.now(),
): UsageSnapshot {
  const scope = usageScopeForModel(modelId);
  const bucket =
    scope === "spark"
      ? findSparkRateLimitBucket(data) ?? normalizeRateLimitBucket(data.rate_limit)
      : normalizeRateLimitBucket(data.rate_limit);
  return {
    capturedAt: now,
    scope,
    fiveHourLeftPercent: usedToLeftPercent(bucket?.primary_window?.used_percent),
    sevenDayLeftPercent: usedToLeftPercent(bucket?.secondary_window?.used_percent),
    fiveHourResetInSeconds: getResetSeconds(bucket?.primary_window, now),
    sevenDayResetInSeconds: getResetSeconds(bucket?.secondary_window, now),
    isLimited: bucket?.limit_reached === true || bucket?.allowed === false,
  };
}

export function formatPercent(value: number | null): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(clampPercent(value))}%`
    : "--";
}

function remainingResetSeconds(
  seconds: number | null,
  capturedAt: number,
  now: number,
): number | null {
  return seconds === null ? null : seconds - (now - capturedAt) / 1000;
}

export function formatUsageSnapshot(
  snapshot: UsageSnapshot,
  options: { showResetTimes: boolean },
  now = Date.now(),
): string {
  const fiveHour = formatPercent(snapshot.fiveHourLeftPercent);
  const sevenDay = formatPercent(snapshot.sevenDayLeftPercent);
  const resets = options.showResetTimes
    ? [
        formatCompactReset(
          "5h",
          remainingResetSeconds(snapshot.fiveHourResetInSeconds, snapshot.capturedAt, now),
        ),
        formatCompactReset(
          "7d",
          remainingResetSeconds(snapshot.sevenDayResetInSeconds, snapshot.capturedAt, now),
          { includeDate: true },
        ),
      ].filter((value): value is string => value !== null)
    : [];
  return `Usage: 5h: ${fiveHour} | 7d: ${sevenDay}${resets.length ? ` | ${resets.join(" | ")}` : ""}`;
}
