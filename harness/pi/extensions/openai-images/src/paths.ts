import { homedir } from "node:os";
import { resolve } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export function piAgentDir(): string {
  return getAgentDir();
}

export function expandTildePath(path: string, home = homedir()): string {
  if (path === "~") return home;
  if (path.startsWith("~/") || path.startsWith("~\\")) {
    return `${home}${path.slice(1)}`;
  }
  return path;
}

export function resolveUserPath(path: string, cwd: string, home = homedir()): string {
  return resolve(cwd, expandTildePath(path, home));
}
