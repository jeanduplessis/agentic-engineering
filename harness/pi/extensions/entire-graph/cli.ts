import { spawn } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import { StringDecoder } from "node:string_decoder";

export const OUTPUT_BYTES = 32 * 1024;
const PROCESS_BYTES = 2 * 1024 * 1024;
const TIMEOUT_MS = 60_000;

// JSON escapes C0 controls already; also neutralize DEL/C1 controls before terminal rendering.
function json(value: unknown, indent?: number): string {
	return JSON.stringify(value, null, indent).replace(/[\u007f-\u009f]/g,
		(character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

interface ProcessOptions {
	cwd: string;
	env?: NodeJS.ProcessEnv;
	signal?: AbortSignal;
	timeoutMs?: number;
	maxBytes?: number;
}

/** No shell; bounded capture; cancellation also stops descendants on POSIX. */
export function runProcess(command: string, args: string[], options: ProcessOptions): Promise<string> {
	if (options.signal?.aborted) return Promise.reject(new Error("Entire Graph cancelled."));
	return new Promise((accept, reject) => {
		const child = spawn(command, args, {
			cwd: options.cwd,
			env: options.env,
			shell: false,
			windowsHide: true,
			detached: process.platform !== "win32",
			stdio: ["ignore", "pipe", "pipe"],
		});
		const stdout: Buffer[] = [];
		const stderr: Buffer[] = [];
		let bytes = 0;
		let failure: Error | undefined;
		const stop = (error: Error) => {
			if (failure) return;
			failure = error;
			if (!child.pid) return;
			if (process.platform === "win32") {
				const killer = spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
					stdio: "ignore", windowsHide: true, timeout: 1000,
				});
				killer.on("error", () => child.kill("SIGKILL"));
				killer.on("close", (code) => { if (code !== 0) child.kill("SIGKILL"); });
			} else {
				try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
			}
		};
		const cancel = () => stop(new Error("Entire Graph cancelled."));
		const timer = setTimeout(() => stop(new Error("Entire Graph timed out.")), options.timeoutMs ?? TIMEOUT_MS);
		options.signal?.addEventListener("abort", cancel, { once: true });
		// Cover an abort between the pre-spawn check and listener registration.
		if (options.signal?.aborted) cancel();
		const capture = (target: Buffer[], chunk: Buffer) => {
			if (failure) return;
			bytes += chunk.length;
			if (bytes > (options.maxBytes ?? PROCESS_BYTES)) {
				stop(new Error("Entire Graph exceeded its process output limit; narrow the query."));
			} else target.push(chunk);
		};
		child.stdout.on("data", (chunk: Buffer) => capture(stdout, chunk));
		child.stderr.on("data", (chunk: Buffer) => capture(stderr, chunk));
		const cleanup = () => {
			clearTimeout(timer);
			options.signal?.removeEventListener("abort", cancel);
		};
		child.on("error", () => {
			cleanup();
			reject(new Error("Cannot start Entire Graph. Install the graph plugin or set PI_ENTIRE_GRAPH_BIN to an absolute standalone binary path."));
		});
		child.on("close", (code) => {
			cleanup();
			if (failure) reject(failure);
			else if (code !== 0) {
				// JSON quoting prevents terminal control characters in repository-derived errors.
				const diagnostic = Buffer.concat(stderr).toString("utf8").slice(0, 1200);
				reject(new Error(`Entire Graph exited with code ${code}: ${json(diagnostic)}`));
			} else accept(Buffer.concat(stdout).toString("utf8"));
		});
	});
}

interface ClientOptions {
	env?: NodeJS.ProcessEnv;
	timeoutMs?: number;
	run?: typeof runProcess;
}

type JsonObject = Record<string, unknown>;
function object(value: unknown): value is JsonObject {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function invoke(args: string[], cwd: string, signal: AbortSignal | undefined, options: ClientOptions): Promise<JsonObject> {
	const env = { ...(options.env ?? process.env) };
	const binary = env.PI_ENTIRE_GRAPH_BIN;
	if (binary !== undefined && (!binary || !isAbsolute(binary))) {
		throw new Error("PI_ENTIRE_GRAPH_BIN must be an absolute standalone binary path, not a shell command.");
	}
	// These optional upstream experiment knobs can replay an earlier answer instead of querying.
	// Never bind them to a Pi session or inherit a precomputed payload into a live tool call.
	for (const key of ["ENTIRE_GRAPH_PRESEARCH", "EG_PRESEARCH", "EG_SEARCH_SESSION", "EG_MAX_SEARCHES",
		"ENTIRE_GRAPH_REFERENCE_BLOCKS", "ENTIRE_REPO_ROOT"]) delete env[key];
	const output = await (options.run ?? runProcess)(binary ?? "entire", binary ? args : ["graph", ...args], {
		cwd: resolve(cwd), env, signal, timeoutMs: options.timeoutMs,
	});
	let data: unknown;
	try { data = JSON.parse(output); } catch {
		// Do not echo malformed stdout: it can contain source or other sensitive content.
		throw new Error("Entire Graph returned invalid JSON; check the installed graph version with /graph status.");
	}
	if (!object(data)) throw new Error("Entire Graph returned an unexpected response shape.");
	return data;
}

export interface SearchInput { query: string; topK?: number; head?: boolean }
export interface ImpactInput { symbol: string; file?: string; depth?: number; limit?: number; head?: boolean }

export interface GraphDetails {
	command: "search" | "impact";
	requestedView: "head" | "worktree";
	elapsedMs: number;
	cacheHit: boolean | undefined;
	truncated: boolean;
	fullOutputPath?: string;
}

function diagnostics(data: JsonObject) {
	const warnings = Array.isArray(data.warnings) ? data.warnings : [];
	const codes = [...new Set(warnings.filter(object).map((warning) => String(warning.code ?? "unknown").slice(0, 80)))];
	return {
		completeness_level: object(data.stats) ? String(data.stats.completeness_level ?? "not-reported").slice(0, 80) : "not-reported",
		warnings: warnings.length,
		warning_codes: codes.slice(0, 10),
		omitted_warning_codes: Math.max(0, codes.length - 10),
		partial_failures: Array.isArray(data.partial_failures) ? data.partial_failures.length : 0,
	};
}

export async function queryGraph(
	command: "search" | "impact", input: SearchInput | ImpactInput, cwd: string,
	signal?: AbortSignal, options: ClientOptions = {},
) {
	const args = [command, "--repo", resolve(cwd), "--format", "json", "--profile", "full"];
	if (input.head) args.push("--head");
	if (command === "search") {
		const search = input as SearchInput;
		args.push("--query", search.query, "--top-k", String(search.topK ?? 5), "--max-context-bytes", "12000");
	} else {
		const impact = input as ImpactInput;
		args.push("--symbol", impact.symbol, "--depth", String(impact.depth ?? 2), "--limit", String(impact.limit ?? 8));
		if (impact.file) args.push("--file", impact.file);
	}
	const started = performance.now();
	const data = await invoke(args, cwd, signal, options);
	if (command === "search" ? !(Array.isArray(data.results) || data.results === null) :
		!(typeof data.focus_matches_total === "number" && typeof data.disambiguation_required === "boolean")) {
		throw new Error(`Entire Graph returned an unexpected ${command} response shape.`);
	}
	if (input.head && (typeof data.commit !== "string" || !data.commit || typeof data.tree !== "string" || !data.tree ||
		(Array.isArray(data.warnings) && data.warnings.some((warning) => object(warning) && warning.code === "W_WORKTREE_SNAPSHOT")))) {
		throw new Error("Entire Graph did not provide a committed HEAD view. Use working-tree mode explicitly if that is intended.");
	}
	const cacheHit = command === "search" && object(data.stats) ? data.stats.index_cache_hit : data.index_cache_hit;
	const details: GraphDetails = {
		command, requestedView: input.head ? "head" : "worktree", elapsedMs: Math.round(performance.now() - started),
		cacheHit: typeof cacheHit === "boolean" ? cacheHit : undefined, truncated: false,
	};
	const summary = { requested_view: details.requestedView, diagnostics: diagnostics(data) };
	let text = json({ ...summary, response: data }, 2);
	if (Buffer.byteLength(text) > OUTPUT_BYTES || text.split("\n").length > 1000) {
		const directory = await mkdtemp(join(tmpdir(), "pi-entire-graph-"));
		details.fullOutputPath = join(directory, "result.json");
		await writeFile(details.fullOutputPath, text, { mode: 0o600 });
		details.truncated = true;
		const header = `${json(summary)}\nOutput truncated; inspect the full result before drawing conclusions.\n`;
		const suffix = `\nFull output saved to: ${json(details.fullOutputPath)}`;
		const budget = Math.max(0, OUTPUT_BYTES - Buffer.byteLength(header + suffix));
		const lines = text.split("\n").slice(0, 990).join("\n");
		const preview = new StringDecoder("utf8").write(Buffer.from(lines).subarray(0, budget));
		text = header + preview + suffix;
	}
	return { content: [{ type: "text" as const, text }], details };
}

export async function graphStatus(cwd: string, options: ClientOptions = {}) {
	const version = await invoke(["version", "--json"], cwd, undefined, options);
	const capabilities = await invoke(["capabilities", "--json"], cwd, undefined, options);
	if (typeof version.version !== "string" || !Array.isArray(capabilities.semantic_languages)) {
		throw new Error("Entire Graph returned unexpected version/capability data.");
	}
	return { version: version.version, semanticLanguages: capabilities.semantic_languages.length };
}
