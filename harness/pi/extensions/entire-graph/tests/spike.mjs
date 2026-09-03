import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { graphStatus, OUTPUT_BYTES } from "../cli.ts";
import { loadGraphExtension } from "./sdk.mjs";

// No model sessions, installs, commits, or changes to the repository under test.
const repo = resolve(fileURLToPath(new URL("../../../../../", import.meta.url)));
const root = await mkdtemp(join(tmpdir(), "entire-graph-spike-"));
const previousCache = process.env.ENTIRE_PLUGIN_DATA_DIR;
process.env.ENTIRE_PLUGIN_DATA_DIR = join(root, "cache");
const report = { date: new Date().toISOString(), repository: repo, mode: "deterministic; no model calls", cases: [] };

try {
	report.graph = await graphStatus(repo);
	const loaded = await loadGraphExtension(repo);
	assert.deepEqual(loaded.errors, []);
	const tools = loaded.extensions[0].tools;

	async function call(tool, args, cwd) {
		const result = await tools.get(tool).definition.execute("spike", args, new AbortController().signal, undefined, { cwd });
		assert.ok(Buffer.byteLength(result.content[0].text) <= OUTPUT_BYTES);
		let text = result.content[0].text;
		if (result.details.fullOutputPath) {
			text = await readFile(result.details.fullOutputPath, "utf8");
			await rm(dirname(result.details.fullOutputPath), { recursive: true, force: true });
		}
		return { ...JSON.parse(text), details: result.details, outputBytes: Buffer.byteLength(result.content[0].text) };
	}
	function hits(result) {
		return (result.response.results ?? []).filter((hit) => hit.section !== "related").map((hit) => ({
			file: hit.file_path, symbol: hit.qualified_name, line: hit.focus_line ?? hit.start_line,
		}));
	}
	function record(name, result, facts) {
		report.cases.push({ name, elapsedMs: result.details.elapsedMs, cacheHit: result.details.cacheHit,
			outputBytes: result.outputBytes, truncated: result.details.truncated, diagnostics: result.diagnostics, ...facts });
	}

	const fixture = join(root, "fixture");
	await mkdir(fixture);
	execFileSync("git", ["init", "-q", fixture], { env: { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: process.platform === "win32" ? "NUL" : "/dev/null" } });
	const pricing = `export function calculateInvoiceTotal(prices: number[], taxRate: number): number {
  const subtotal = prices.reduce((sum, price) => sum + price, 0);
  return subtotal * (1 + taxRate);
}

export function createInvoice(prices: number[]): number {
  return calculateInvoiceTotal(prices, 0.15);
}
`;
	await writeFile(join(fixture, "pricing.ts"), pricing);
	await writeFile(join(fixture, "checkout.ts"), `import { calculateInvoiceTotal } from "./pricing";
export function checkoutInvoice(prices: number[]): number {
  return calculateInvoiceTotal(prices, 0.2);
}
`);
	await writeFile(join(fixture, "first.ts"), "export function normalizeInvoice(value: string) { return value.trim(); }\n");
	await writeFile(join(fixture, "second.ts"), "export function normalizeInvoice(value: string) { return value.toLowerCase(); }\n");

	const found = await call("graph_search", { query: "calculate invoice total including tax" }, fixture);
	const foundHits = hits(found);
	record("fixture conceptual search", found, { hits: foundHits, passed: foundHits.some((hit) => hit.symbol === "calculateInvoiceTotal") });

	const impact = await call("graph_impact", { symbol: "calculateInvoiceTotal", file: "pricing.ts" }, fixture);
	const callerNames = (impact.response.callers?.entries ?? []).map((entry) => entry.endpoint.qualified_name);
	record("fixture known callers", impact, { callers: callerNames,
		passed: ["createInvoice", "checkoutInvoice"].every((name) => callerNames.includes(name)) });

	const ambiguous = await call("graph_impact", { symbol: "normalizeInvoice" }, fixture);
	record("fixture ambiguous symbol", ambiguous, { matches: ambiguous.response.focus_matches_total,
		passed: ambiguous.response.disambiguation_required && ambiguous.response.focus_matches_total === 2 });

	await writeFile(join(fixture, "pricing.ts"), pricing + "\nexport function applyUncommittedSurcharge(total: number): number { return total + 7; }\n");
	const changed = await call("graph_search", { query: "applyUncommittedSurcharge" }, fixture);
	record("fixture sees an uncommitted edit", changed, { hits: hits(changed),
		passed: hits(changed).some((hit) => hit.symbol === "applyUncommittedSurcharge") });

	const tasks = [
		{ query: "link selected Pi extensions into the agent directory", file: "setup.sh", symbol: "install_pi_harness" },
		{ query: "calculate total token usage and cost across session entries", file: "harness/pi/extensions/custom-footer/index.ts", symbol: "collectSessionTotals" },
		{ query: "route compaction through a dedicated model with fallback to the active model", file: "harness/pi/extensions/compaction-model/index.ts", symbol: "registerCompactionModel" },
	];
	for (const task of tasks) {
		const result = await call("graph_search", { query: task.query }, repo);
		const ranked = hits(result);
		const rank = ranked.findIndex((hit) => hit.file === task.file && hit.symbol === task.symbol) + 1;
		record(task.query, result, { expected: task, rank: rank || null, hits: ranked, passed: rank > 0 });
	}

	const repoImpact = await call("graph_impact", { symbol: "usageCost", file: "harness/pi/extensions/custom-footer/index.ts" }, repo);
	const repoCallers = (repoImpact.response.callers?.entries ?? []).map((entry) => entry.endpoint.qualified_name);
	record("repository known caller", repoImpact, { callers: repoCallers, passed: repoCallers.includes("collectSessionTotals") });

	const query = tasks[1].query;
	const cold = await call("graph_search", { query, head: true }, repo);
	const warm = await call("graph_search", { query, head: true }, repo);
	record("repeated HEAD query", warm, { firstElapsedMs: cold.details.elapsedMs, firstCacheHit: cold.details.cacheHit,
		passed: warm.details.cacheHit === true && JSON.stringify(hits(cold)) === JSON.stringify(hits(warm)) });
	const fresh = await call("graph_search", { query }, repo);
	record("working-tree query does not reuse the HEAD cache", fresh, { passed: fresh.details.cacheHit === false });
	report.passed = report.cases.filter((item) => item.passed).length;
	report.total = report.cases.length;
	console.log(JSON.stringify(report, null, 2));
	if (report.passed !== report.total) process.exitCode = 1;
} finally {
	if (previousCache === undefined) delete process.env.ENTIRE_PLUGIN_DATA_DIR;
	else process.env.ENTIRE_PLUGIN_DATA_DIR = previousCache;
	await rm(root, { recursive: true, force: true });
}
