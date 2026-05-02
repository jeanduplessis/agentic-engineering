import { execFileSync } from "child_process";
import type { GraphQLResponse } from "./types";

export function graphql<T>(query: string, variables: Record<string, string | number | boolean> = {}): T {
  const args = ["api", "graphql", "-f", `query=${query}`];

  for (const [key, value] of Object.entries(variables)) {
    // Use -F for non-string types (numbers, booleans), -f for strings
    if (typeof value === "string") {
      args.push("-f", `${key}=${value}`);
    } else {
      args.push("-F", `${key}=${value}`);
    }
  }

  let stdout: string;
  try {
    stdout = execFileSync("gh", args, {
      encoding: "utf-8",
      maxBuffer: 10 * 1024 * 1024, // 10MB
      timeout: 30000,
    });
  } catch (err: unknown) {
    const error = err as { stderr?: string; message?: string };
    const message = error.stderr?.trim() || error.message || "Failed to execute gh command";
    throw new Error(message);
  }

  let parsed: GraphQLResponse<T>;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new Error("Failed to parse GitHub API response as JSON");
  }

  if (parsed.errors && parsed.errors.length > 0) {
    throw new Error(parsed.errors.map((e) => e.message).join("; "));
  }

  if (!parsed.data) {
    throw new Error("GitHub API returned no data");
  }

  return parsed.data;
}
