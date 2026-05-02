import { execFileSync } from "child_process";
import type { PRIdentifier, ReviewState } from "./types";

/** Check if a string looks like a CLI flag (--word or -X). */
function looksLikeFlag(arg: string): boolean {
  return /^--[a-zA-Z]/.test(arg) || /^-[a-zA-Z]$/.test(arg);
}

/**
 * Parse a GitHub PR URL into owner, repo, and PR number.
 * Accepts: https://github.com/owner/repo/pull/123
 */
export function parsePRUrl(url: string): PRIdentifier | null {
  const match = url.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
  if (!match) return null;
  return { owner: match[1], repo: match[2], number: parseInt(match[3], 10) };
}

/**
 * Minimal argument parser. Returns a map of flags and positional args.
 * Supports: --flag value, --flag=value, -f value, --boolean-flag (no value)
 */
export interface ParsedArgs {
  flags: Record<string, string>;
  positional: string[];
}

export function parseArgs(argv: string[]): ParsedArgs {
  const flags: Record<string, string> = {};
  const positional: string[] = [];

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];

    if (arg === "--") {
      // Everything after -- is positional
      positional.push(...argv.slice(i + 1));
      break;
    }

    if (arg.startsWith("--")) {
      const eqIndex = arg.indexOf("=");
      if (eqIndex !== -1) {
        // --flag=value
        flags[arg.slice(2, eqIndex)] = arg.slice(eqIndex + 1);
      } else if (i + 1 < argv.length && !looksLikeFlag(argv[i + 1])) {
        // --flag value
        flags[arg.slice(2)] = argv[i + 1];
        i++;
      } else {
        // --boolean-flag
        flags[arg.slice(2)] = "true";
      }
    } else if (arg.startsWith("-") && arg.length === 2) {
      // -f value
      if (i + 1 < argv.length && !looksLikeFlag(argv[i + 1])) {
        flags[arg.slice(1)] = argv[i + 1];
        i++;
      } else {
        flags[arg.slice(1)] = "true";
      }
    } else {
      positional.push(arg);
    }

    i++;
  }

  return { flags, positional };
}

/**
 * Parse and validate a PR number string, returning a positive integer.
 */
function parsePRNumber(value: string): number {
  const n = parseInt(value, 10);
  if (isNaN(n) || n <= 0) {
    throw new Error(`Invalid PR number: ${value}. Must be a positive integer`);
  }
  return n;
}

/**
 * Resolve a PRIdentifier from CLI arguments.
 * Priority: positional PR URL > -R + --pr flags
 */
export function resolvePR(args: ParsedArgs): PRIdentifier {
  // Check positional args for a PR URL
  for (const pos of args.positional) {
    const parsed = parsePRUrl(pos);
    if (parsed) return parsed;
  }

  // Check -R and --pr flags
  const repoFlag = args.flags["R"];
  const prFlag = args.flags["pr"];

  if (repoFlag && prFlag) {
    const parts = repoFlag.split("/");
    if (parts.length !== 2) {
      throw new Error(`Invalid repository format: ${repoFlag}. Expected owner/repo`);
    }
    return { owner: parts[0], repo: parts[1], number: parsePRNumber(prFlag) };
  }

  if (prFlag && !repoFlag) {
    const prNumber = parsePRNumber(prFlag);
    // Try to infer repo from git remote
    const repo = inferRepo();
    if (repo) {
      return { owner: repo.owner, repo: repo.repo, number: prNumber };
    }
    throw new Error("Cannot determine repository. Use -R owner/repo or provide a PR URL");
  }

  throw new Error("Pull request not specified. Use --pr <number> with -R owner/repo, or provide a PR URL");
}

/**
 * Try to infer owner/repo from the current git remote via `gh`.
 */
function inferRepo(): { owner: string; repo: string } | null {
  try {
    const output = execFileSync("gh", ["repo", "view", "--json", "owner,name", "-q", ".owner.login + \"/\" + .name"], {
      encoding: "utf-8",
      timeout: 5000,
    }).trim();
    const parts = output.split("/");
    if (parts.length === 2) {
      return { owner: parts[0], repo: parts[1] };
    }
  } catch {
    // Ignore — repo inference is best-effort
  }
  return null;
}

/**
 * Parse comma-separated review states and validate them.
 */
export function parseStates(input: string): ReviewState[] {
  const valid: ReviewState[] = ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"];
  const states = input.split(",").map((s) => s.trim().toUpperCase());

  for (const s of states) {
    if (!valid.includes(s as ReviewState)) {
      throw new Error(`Invalid review state: ${s}. Valid states: ${valid.join(", ")}`);
    }
  }

  return states as ReviewState[];
}

/**
 * Output JSON to stdout.
 */
export function outputJSON(data: unknown): void {
  process.stdout.write(JSON.stringify(data, null, 2) + "\n");
}

/**
 * Output an error as JSON to stderr and exit with code 1.
 */
export function exitWithError(message: string): never {
  process.stderr.write(JSON.stringify({ error: message }) + "\n");
  process.exit(1);
}
