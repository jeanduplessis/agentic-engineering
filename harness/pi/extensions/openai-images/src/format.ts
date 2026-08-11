const ANSI_ESCAPE_REGEXP = new RegExp(
  String.raw`\\u001B\\[[0-?]*[ -/]*[@-~]`,
  "g",
);
const DEFAULT_MAX_LENGTH = 500;

function replaceControlCharacters(value: string): string {
  let result = "";
  for (const char of value) {
    const code = char.charCodeAt(0);
    result += code <= 31 || (code >= 127 && code <= 159) ? " " : char;
  }
  return result;
}

export function stripAnsi(value: string): string {
  return value.replace(ANSI_ESCAPE_REGEXP, "");
}

/** Remove terminal escapes and credential-like values from user-facing errors. */
export function sanitizeDiagnosticError(
  message: string,
  maxLength = DEFAULT_MAX_LENGTH,
): string {
  const redacted = stripAnsi(message)
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [REDACTED]")
    .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, "sk-[REDACTED]")
    .replace(/\bacct_[A-Za-z0-9_-]{6,}\b/g, "acct_[REDACTED]")
    .replace(
      /(["']?(?:access|access_token|token|api[_-]?key|authorization|accountId|account_id)["']?\s*[:=]\s*["']?)([^"',\s}\]]+)/gi,
      "$1[REDACTED]",
    );
  const clean = replaceControlCharacters(redacted)
    .replace(/ +/g, " ")
    .trim();
  const safe = clean || "Unknown error.";
  if (safe.length <= maxLength) return safe;
  return `${safe.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

export function maskIdentifier(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  if (trimmed.length <= 8) return "found";
  return `${trimmed.slice(0, 4)}...${trimmed.slice(-4)}`;
}
