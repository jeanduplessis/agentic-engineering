import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export type CodexCredentials = {
  accessToken: string;
  accountId: string;
};

export type CodexCredentialsWithSource = CodexCredentials & {
  source: "modelRegistry" | "authFile";
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function abortError(signal: AbortSignal): Error {
  const reason = signal.reason;
  if (reason instanceof Error) return reason;
  return new Error(typeof reason === "string" ? reason : "Operation was aborted.");
}

function waitForSignal<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return operation;
  if (signal.aborted) return Promise.reject(abortError(signal));

  return new Promise<T>((resolve, reject) => {
    const onAbort = () => {
      cleanup();
      reject(abortError(signal));
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
    if (!isRecord(parsed)) return undefined;
    const auth = parsed["https://api.openai.com/auth"];
    if (!isRecord(auth)) return undefined;
    const accountId = auth.chatgpt_account_id;
    return typeof accountId === "string" && accountId.trim()
      ? accountId.trim()
      : undefined;
  } catch {
    return undefined;
  }
}

function credentialValue(
  value: unknown,
  keys: string[],
): string | undefined {
  if (!isRecord(value)) return undefined;
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }
  return undefined;
}

export function parseCodexRegistryCredentials(
  raw: string | undefined,
): CodexCredentials | undefined {
  const value = raw?.trim();
  if (!value) return undefined;

  try {
    const parsed = JSON.parse(value) as unknown;
    if (isRecord(parsed)) {
      const accessToken = credentialValue(parsed, ["access", "accessToken", "access_token", "token"]);
      const accountId = credentialValue(parsed, ["accountId", "account_id"]);
      if (accessToken) {
        const resolvedAccountId = accountId ?? extractAccountIdFromJwt(accessToken);
        if (resolvedAccountId) return { accessToken, accountId: resolvedAccountId };
      }
    }
  } catch {
    // A plain bearer token is also accepted by Pi for openai-codex.
  }

  const accountId = extractAccountIdFromJwt(value);
  return accountId ? { accessToken: value, accountId } : undefined;
}

function expiryInMilliseconds(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return value < 1_000_000_000_000 ? value * 1000 : value;
}

export function authFilePath(agentDir = getAgentDir()): string {
  return join(agentDir, "auth.json");
}

export function readCodexAuth(agentDir = getAgentDir()): CodexCredentials | undefined {
  try {
    const parsed = JSON.parse(readFileSync(authFilePath(agentDir), "utf8")) as unknown;
    if (!isRecord(parsed)) return undefined;
    const entry = parsed["openai-codex"];
    if (!isRecord(entry) || entry.type !== "oauth") {
      return undefined;
    }

    const accessToken = credentialValue(entry, ["access", "accessToken", "access_token"]);
    if (!accessToken) return undefined;
    const expires = expiryInMilliseconds(entry.expires);
    if (expires !== undefined && Date.now() >= expires) return undefined;
    const accountId =
      credentialValue(entry, ["accountId", "account_id"]) ??
      extractAccountIdFromJwt(accessToken);
    return accountId ? { accessToken, accountId } : undefined;
  } catch {
    return undefined;
  }
}

export async function getCodexCredentials(
  ctx?: Pick<ExtensionContext, "modelRegistry">,
  signal?: AbortSignal,
): Promise<CodexCredentialsWithSource | undefined> {
  if (signal?.aborted) throw abortError(signal);

  let registryToken: string | undefined;
  try {
    const request = ctx?.modelRegistry.getApiKeyForProvider("openai-codex");
    if (request) registryToken = await waitForSignal(request, signal);
  } catch (error) {
    if (signal?.aborted) throw error;
  }

  const registryCredentials = parseCodexRegistryCredentials(registryToken);
  if (registryCredentials) return { ...registryCredentials, source: "modelRegistry" };

  const auth = readCodexAuth();
  return auth ? { ...auth, source: "authFile" } : undefined;
}

export const _authTest = {
  decodeBase64Url,
  expiryInMilliseconds,
};
