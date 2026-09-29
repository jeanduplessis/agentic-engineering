import { spawn } from "node:child_process";
import { realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { isAbsolute, parse, relative, resolve, sep } from "node:path";

const TIMEOUT_MS = 120_000;
const PROCESS_BYTES = 512 * 1024;
const FALLBACK = "Continue with rg, grep, and read for this task.";

/** jg cannot run in this session (missing binary or login). Callers stop offering code_search. */
export class UnavailableError extends Error {}

export interface RunResult { code: number | null; stdout: string; stderr: string }
export interface RunOptions { cwd: string; env?: NodeJS.ProcessEnv; signal?: AbortSignal; timeoutMs?: number }
export type Runner = (command: string, args: string[], options: RunOptions) => Promise<RunResult>;

// JSON escapes C0 controls already; also neutralize DEL/C1 controls before terminal rendering.
function json(value: unknown): string {
	return JSON.stringify(value).replace(/[\u007f-\u009f]/g,
		(character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

/** No shell, no stdin, bounded capture; cancellation and timeout stop the process group on POSIX. */
export const runProcess: Runner = (command, args, options) => {
	if (options.signal?.aborted) return Promise.reject(new Error("code_search cancelled."));
	return new Promise((accept, reject) => {
		const child = spawn(command, args, {
			cwd: options.cwd, env: options.env, shell: false, windowsHide: true,
			detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"],
		});
		const stdout: Buffer[] = [];
		const stderr: Buffer[] = [];
		let bytes = 0;
		let failure: Error | undefined;
		const stop = (error: Error) => {
			if (failure) return;
			failure = error;
			if (!child.pid) return;
			if (process.platform === "win32") child.kill("SIGKILL");
			else try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
		};
		const cancel = () => stop(new Error("code_search cancelled."));
		const timer = setTimeout(() => stop(new Error(`code_search timed out. ${FALLBACK}`)), options.timeoutMs ?? TIMEOUT_MS);
		options.signal?.addEventListener("abort", cancel, { once: true });
		if (options.signal?.aborted) cancel();
		const capture = (target: Buffer[], chunk: Buffer) => {
			if (failure) return;
			bytes += chunk.length;
			if (bytes > PROCESS_BYTES) stop(new Error("jg exceeded its output limit; narrow the query or paths."));
			else target.push(chunk);
		};
		child.stdout.on("data", (chunk: Buffer) => capture(stdout, chunk));
		child.stderr.on("data", (chunk: Buffer) => capture(stderr, chunk));
		const cleanup = () => { clearTimeout(timer); options.signal?.removeEventListener("abort", cancel); };
		child.on("error", (error: NodeJS.ErrnoException) => {
			cleanup();
			reject(error.code === "ENOENT"
				? new UnavailableError(`jg is not installed or not on PATH (npm install -g @remotehost/jg, or set PI_JG_BIN). ${FALLBACK}`)
				: new Error(`Cannot start ${command}: ${error.message}`));
		});
		child.on("close", (code) => {
			cleanup();
			if (failure) reject(failure);
			else accept({ code, stdout: Buffer.concat(stdout).toString("utf8"), stderr: Buffer.concat(stderr).toString("utf8") });
		});
	});
};

async function gitRoot(cwd: string, run: Runner): Promise<string | undefined> {
	try {
		const result = await run("git", ["rev-parse", "--show-toplevel"], { cwd, timeoutMs: 10_000 });
		return result.code === 0 && result.stdout.trim() ? result.stdout.trim() : undefined;
	} catch { return undefined; }
}

export interface Scope { root: string; paths: string[]; git: boolean }

/**
 * Confine search paths to the workspace. jg sends selected source to a hosted service and explicit
 * paths bypass ignore rules, so reject paths outside the root, hidden segments, and git-ignored paths.
 */
export async function resolveScope(cwd: string, requested: string[] | undefined, run: Runner = runProcess, home = homedir()): Promise<Scope> {
	const base = await realpath(cwd);
	const top = await gitRoot(base, run);
	const root = await realpath(top ?? base);
	if (root === parse(root).root || root === await realpath(home).catch(() => home)) {
		throw new Error(`code_search refuses to search the home or filesystem root; start Pi inside a project. ${FALLBACK}`);
	}
	const paths: string[] = [];
	for (const input of requested?.length ? requested : ["."]) {
		let real: string;
		try { real = await realpath(resolve(base, input)); } catch {
			throw new Error(`code_search path does not exist: ${json(input)}`);
		}
		const rel = relative(root, real);
		if (rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
			throw new Error(`code_search path is outside the workspace ${json(root)}: ${json(input)}`);
		}
		if (rel.split(sep).some((segment) => segment.startsWith("."))) {
			throw new Error(`code_search does not search hidden paths: ${json(input)}`);
		}
		if (top && rel) {
			const ignored = await run("git", ["check-ignore", "-q", "--", rel], { cwd: root, timeoutMs: 10_000 });
			if (ignored.code === 0) throw new Error(`code_search does not search git-ignored paths: ${json(input)}`);
		}
		paths.push(rel || ".");
	}
	return { root, paths: [...new Set(paths)], git: Boolean(top) };
}

export interface SearchInput { query: string; paths?: string[]; limit?: number; broad?: boolean }
export interface SearchDetails { root: string; paths: string[]; exitCode: number; matches: number; truncated: boolean }
export interface SearchOptions { env?: NodeJS.ProcessEnv; run?: Runner; home?: string }

type JsonObject = Record<string, unknown>;
const object = (value: unknown): value is JsonObject => value !== null && typeof value === "object" && !Array.isArray(value);

export async function searchCode(input: SearchInput, cwd: string, signal?: AbortSignal, options: SearchOptions = {}) {
	const run = options.run ?? runProcess;
	const env = { ...(options.env ?? process.env) };
	const binary = env.PI_JG_BIN;
	if (binary !== undefined && (!binary || !isAbsolute(binary))) {
		throw new UnavailableError(`PI_JG_BIN must be an absolute path to the jg executable. ${FALLBACK}`);
	}
	const scope = await resolveScope(cwd, input.paths, run, options.home);
	const args = ["--json"];
	if (input.limit !== undefined) args.push("--limit", String(input.limit));
	if (input.broad) args.push("--broad");
	// `--` keeps queries such as "login" or "status" from being read as jg subcommands.
	args.push("--", input.query, ...scope.paths);
	const result = await run(binary ?? "jg", args, { cwd: scope.root, env, signal });

	if (result.code === 130) throw new Error("code_search cancelled.");
	if (result.code !== 0 && result.code !== 1) {
		const diagnostic = result.stderr.trim().slice(0, 600);
		if (/jg login/i.test(diagnostic)) {
			throw new UnavailableError(`jg is not logged in (run \`jg login\` in a terminal). ${FALLBACK}`);
		}
		throw new Error(`jg exited with code ${result.code}: ${json(diagnostic)}. ${FALLBACK}`);
	}
	let data: unknown;
	try { data = JSON.parse(result.stdout); } catch {
		// Do not echo malformed stdout: it can contain source.
		throw new Error(`jg returned invalid JSON; check the installed jg version. ${FALLBACK}`);
	}
	if (!object(data) || data.schemaVersion !== 1 || !Array.isArray(data.matches)) {
		throw new Error(`jg returned an unsupported result schema; code_search expects schemaVersion 1. ${FALLBACK}`);
	}
	const details: SearchDetails = {
		root: scope.root, paths: scope.paths, exitCode: result.code,
		matches: data.matches.length, truncated: data.truncated === true,
	};
	const note = details.matches === 0
		? "No matches. This does not prove the code is absent: rephrase the behavior, set broad, or use rg for exact identifiers.\n"
		: `Paths are relative to ${json(scope.root)}. Confirm with read or rg before editing.\n`;
	return { content: [{ type: "text" as const, text: note + json(data) }], details };
}
