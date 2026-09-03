import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rename, rm, utimes, writeFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { graphStatus, queryGraph, runProcess } from "../cli.ts";

// Explicit local experiment, never a startup hook. The production tool contract is unchanged.
const args = process.argv.slice(2);
assert.ok(args.length <= 2, "Usage: performance.mjs [phase] [timing-repetitions]");
const phase = args[0] ?? "all";
const runs = Number(args[1] ?? 3);
assert.ok(["all", "latency", "impact", "quality", "fixtures"].includes(phase), "Phase: all | latency | impact | quality | fixtures");
assert.ok(Number.isInteger(runs) && runs >= 1 && runs <= 10, "Repetitions must be 1–10");
assert.ok(isAbsolute(process.env.PI_ENTIRE_GRAPH_BIN ?? ""), "Set PI_ENTIRE_GRAPH_BIN to the reviewed standalone binary");
const repo = resolve(fileURLToPath(new URL("../../../../../", import.meta.url)));
const root = await mkdtemp(join(tmpdir(), "graph-performance-"));
const controller = new AbortController();
const cancel = () => controller.abort();
process.once("SIGINT", cancel);
process.once("SIGTERM", cancel);
const env = { ...process.env, ENTIRE_PLUGIN_DATA_DIR: join(root, "cache") };
// Reproducible baseline: never inherit an operator's budget or profiling overrides.
delete env.ENTIRE_GRAPH_SWEEP_DIR_BUDGET;
delete env.GRAPH_SPIKE_CPU_PROFILE;
delete env.GRAPH_SPIKE_TIMING;
const report = {
	date: new Date().toISOString(), platform: `${process.platform}/${process.arch}`, node: process.version,
	repository: repo, head: execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
	phase, timingRepetitions: runs, mode: "serial local CLI calls; no models; OS filesystem cache not flushed",
	variants: [], cases: [],
};
const tasks = [
	{ query: "link selected Pi extensions into the agent directory", file: "setup.sh", symbol: "install_pi_harness" },
	{ query: "calculate total token usage and cost across session entries", file: "harness/pi/extensions/custom-footer/index.ts", symbol: "collectSessionTotals" },
	{ query: "route compaction through a dedicated model with fallback to the active model", file: "harness/pi/extensions/compaction-model/index.ts", symbol: "registerCompactionModel" },
];
const variants = [
	{ name: "default-full", profile: "full" },
	{ name: "default-fast", profile: "fast" },
	{ name: "budget-1024-full", profile: "full", budget: 1024 },
	{ name: "budget-256-full", profile: "full", budget: 256 },
	{ name: "budget-64-full", profile: "full", budget: 64 },
	{ name: "budget-64-fast", profile: "fast", budget: 64 },
	{ name: "head-full", profile: "full", head: true },
];

function locations(data) {
	return (data.results ?? []).filter((hit) => hit.section !== "related")
		.map((hit) => ({ file: hit.file_path, symbol: hit.qualified_name, line: hit.focus_line ?? hit.start_line }));
}
function range(values) {
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return { min: sorted[0], median: sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2, max: sorted.at(-1) };
}
async function call(command, input, variant, cwd = repo) {
	const childEnv = { ...env, ENTIRE_PLUGIN_DATA_DIR: join(root, "cache", variant.name) };
	if (variant.budget !== undefined) childEnv.ENTIRE_GRAPH_SWEEP_DIR_BUDGET = String(variant.budget);
	const result = await queryGraph(command, { ...input, head: variant.head ?? false }, cwd, controller.signal, {
		env: childEnv,
		// Test-only substitution of a supported CLI flag, not a new runtime/tool parameter.
		run: (binary, argv, options) => {
			const adjusted = [...argv];
			adjusted[adjusted.indexOf("--profile") + 1] = variant.profile;
			return runProcess(binary, adjusted, options);
		},
	});
	let text = result.content[0].text;
	if (result.details.fullOutputPath) {
		try { text = await readFile(result.details.fullOutputPath, "utf8"); }
		finally { await rm(dirname(result.details.fullOutputPath), { recursive: true, force: true }); }
	}
	const { response: data } = JSON.parse(text);
	assert.equal(data.profile, variant.profile);
	if (!variant.head) assert.equal(result.details.cacheHit, false, "Working-tree results must remain fresh, not cached");
	return { data, elapsedMs: result.details.elapsedMs, cacheHit: result.details.cacheHit, outputBytes: Buffer.byteLength(result.content[0].text) };
}
function measurement(result) {
	return { elapsedMs: result.elapsedMs, cacheHit: result.cacheHit, outputBytes: result.outputBytes,
		stats: result.data.stats, completeness: result.data.completeness, partialFailures: result.data.partial_failures,
		warnings: result.data.warnings, hits: locations(result.data) };
}
function check(name, passed, facts = {}) {
	report.cases.push({ name, passed: Boolean(passed), ...facts });
}
async function file(base, path, contents) {
	await mkdir(dirname(join(base, path)), { recursive: true });
	await writeFile(join(base, path), contents);
}
async function fixture(name) {
	const cwd = join(root, name);
	await mkdir(cwd);
	execFileSync("git", ["-c", "core.hooksPath=/dev/null", "init", "-q", cwd], {
		env: { ...env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: process.platform === "win32" ? "NUL" : "/dev/null" },
	});
	return cwd;
}

try {
	report.graph = await graphStatus(repo, { env, timeoutMs: 5000 });
	if (phase === "all" || phase === "latency") {
		// Round-robin, serial runs avoid benchmarking concurrent analyzers against one another.
		for (const variant of variants) report.variants.push({ ...variant, command: "search", samples: [] });
		for (let round = 0; round < runs; round++) {
			for (const variant of report.variants) {
				console.error(`latency ${round + 1}/${runs}: ${variant.name}`);
				variant.samples.push(measurement(await call("search", { query: tasks[1].query }, variant)));
			}
		}
		const baseline = report.variants[0].samples[0];
		for (const variant of report.variants) {
			variant.elapsedMs = range(variant.samples.map((sample) => sample.elapsedMs));
			variant.allCallsUnderFiveSeconds = variant.samples.every((sample) => sample.elapsedMs < 5000);
			variant.stableLocations = variant.samples.every((sample) => JSON.stringify(sample.hits) === JSON.stringify(variant.samples[0].hits));
			variant.sameLocationsAsFullBaseline = JSON.stringify(variant.samples[0].hits) === JSON.stringify(baseline.hits);
			check(`${variant.name}: repeated location stability`, variant.stableLocations);
			if (variant.budget && variant.profile === "full") {
				check(`${variant.name}: indexed counts and ranked locations match the full baseline`, variant.samples.every((sample) =>
					sample.stats.files_scanned === baseline.stats.files_scanned &&
					sample.stats.files_indexed === baseline.stats.files_indexed &&
					JSON.stringify(sample.hits) === JSON.stringify(baseline.hits)));
			}
		}
	}
	if (phase === "all" || phase === "impact") {
		const impactVariants = variants.filter((item) => item.name === "default-full" || item.budget === 64)
			.map((item) => ({ ...item, command: "impact", samples: [] }));
		report.variants.push(...impactVariants);
		for (let round = 0; round < runs; round++) {
			for (const variant of impactVariants) {
				console.error(`impact ${round + 1}/${runs}: ${variant.name}`);
				const result = await call("impact", { symbol: "usageCost", file: tasks[1].file }, variant);
				const callers = (result.data.callers?.entries ?? []).map((entry) => ({
					file: entry.endpoint.file_path, symbol: entry.endpoint.qualified_name,
				}));
				variant.samples.push({ ...measurement(result), callers });
			}
		}
		for (const variant of impactVariants) {
			variant.elapsedMs = range(variant.samples.map((sample) => sample.elapsedMs));
			variant.allCallsUnderFiveSeconds = variant.samples.every((sample) => sample.elapsedMs < 5000);
			check(`${variant.name}: impact callers remain stable`, variant.samples.every((sample) =>
				JSON.stringify(sample.callers) === JSON.stringify(variant.samples[0].callers) &&
				sample.callers.some((caller) => caller.symbol === "collectSessionTotals")));
		}
	}
	if (phase === "all" || phase === "quality") {
		for (const variant of variants.filter((item) => item.budget === 64)) {
			for (const task of tasks) {
				console.error(`quality: ${variant.name}, ${task.symbol}`);
				const result = await call("search", { query: task.query }, variant);
				const rank = locations(result.data).findIndex((hit) => hit.file === task.file && hit.symbol === task.symbol) + 1;
				check(`${variant.name}: ${task.symbol}`, rank > 0, { rank: rank || null, ...measurement(result) });
			}
			const result = await call("impact", { symbol: "usageCost", file: tasks[1].file }, variant);
			const callers = (result.data.callers?.entries ?? []).map((entry) => entry.endpoint.qualified_name);
			check(`${variant.name}: repository caller`, callers.includes("collectSessionTotals"), { callers, ...measurement(result) });
		}
	}
	if (phase === "all" || phase === "fixtures") {
		for (const variant of variants.filter((item) => item.budget === 64)) {
			console.error(`freshness and security fixtures: ${variant.name}`);
			const cwd = await fixture(`fresh-${variant.name}`);
			await file(cwd, "price.ts", 'export function invoiceTotal() { return "BEFORE"; }\n');
			await file(cwd, "caller.ts", 'import { invoiceTotal } from "./price";\nexport function checkoutInvoice() { return invoiceTotal(); }\n');
			// An exact integer-second timestamp avoids Date's sub-millisecond rounding.
			const fixedTime = 1_700_000_000;
			await utimes(join(cwd, "price.ts"), fixedTime, fixedTime);
			const before = await call("search", { query: "invoiceTotal" }, variant, cwd);
			const stamp = await stat(join(cwd, "price.ts"), { bigint: true });
			await file(cwd, "price.ts", 'export function invoiceTotal() { return "AFTER!"; }\n');
			await utimes(join(cwd, "price.ts"), fixedTime, fixedTime);
			const restored = await stat(join(cwd, "price.ts"), { bigint: true });
			const after = await call("search", { query: "invoiceTotal" }, variant, cwd);
			check(`${variant.name}: same-size/restored-mtime edit is fresh`,
				stamp.size === restored.size && stamp.mtimeNs === restored.mtimeNs &&
				JSON.stringify(before.data.results).includes("BEFORE") && JSON.stringify(after.data.results).includes("AFTER!") &&
				!JSON.stringify(after.data.results).includes("BEFORE"));
			const impact = await call("impact", { symbol: "invoiceTotal", file: "price.ts" }, variant, cwd);
			check(`${variant.name}: cross-file caller`, impact.data.callers?.entries.some((entry) => entry.endpoint.qualified_name === "checkoutInvoice"));
			await file(cwd, "new.ts", "export function applyUntrackedSurcharge() { return 7; }\n");
			const added = await call("search", { query: "applyUntrackedSurcharge" }, variant, cwd);
			check(`${variant.name}: untracked add`, locations(added.data).some((hit) => hit.file === "new.ts"));
			await rename(join(cwd, "new.ts"), join(cwd, "moved.ts"));
			const moved = await call("search", { query: "applyUntrackedSurcharge" }, variant, cwd);
			check(`${variant.name}: rename`, locations(moved.data).some((hit) => hit.file === "moved.ts") && !locations(moved.data).some((hit) => hit.file === "new.ts"));
			await file(cwd, ".gitignore", "moved.ts\n");
			const ignored = await call("search", { query: "applyUntrackedSurcharge" }, variant, cwd);
			check(`${variant.name}: ignore-policy change`, !(ignored.data.results ?? []).some((hit) => hit.file_path === "moved.ts"));
			await rm(join(cwd, "moved.ts"));
			await file(cwd, ".gitignore", "");
			const deleted = await call("search", { query: "applyUntrackedSurcharge" }, variant, cwd);
			check(`${variant.name}: deletion`, !(deleted.data.results ?? []).some((hit) => hit.file_path === "moved.ts"));

			const safety = await fixture(`safety-${variant.name}`);
			await file(safety, ".gitignore", "node_modules/\n");
			await file(safety, "app.ts", "export function loadOriginCredential() { return 'safe placeholder'; }\n");
			for (let i = 0; i < 200; i++) await mkdir(join(safety, "node_modules", `d${String(i).padStart(4, "0")}`), { recursive: true });
			await mkdir(join(safety, ".dep-git", "objects"), { recursive: true });
			await mkdir(join(safety, ".dep-git", "refs"), { recursive: true });
			await file(safety, ".dep-git/config", "[remote \"origin\"]\nurl = https://example.invalid/GRAPH_PERF_CANARY_NOT_A_SECRET\n");
			await file(safety, ".dep-git/credential.ts", "export function loadHiddenCredential() { return 'GRAPH_PERF_CANARY_NOT_A_SECRET'; }\n");
			await file(safety, "node_modules/d0199/dep/.git", "gitdir: ../../../.dep-git\n");
			const guarded = await call("search", { query: "origin credential" }, variant, safety);
			check(`${variant.name}: hidden gitdir exclusion and warning`,
				!JSON.stringify(guarded.data).includes("GRAPH_PERF_CANARY_NOT_A_SECRET") &&
				!(guarded.data.results ?? []).some((hit) => hit.file_path.startsWith(".dep-git/")) &&
				locations(guarded.data).some((hit) => hit.file === "app.ts") &&
				guarded.data.warnings?.some((warning) => warning.code === "W_GITDIR_SWEEP_BUDGET"),
				{ warningCodes: guarded.data.warnings?.map((warning) => warning.code) });

			// Make the completeness trade-off observable: headless Git-shaped source with no pointer.
			await rm(join(safety, "node_modules/d0199/dep/.git"));
			const exhaustive = await call("search", { query: "loadHiddenCredential" }, variants[0], safety);
			const conservative = await call("search", { query: "loadHiddenCredential" }, variant, safety);
			check(`${variant.name}: conservative exclusion can omit legitimate Git-shaped source`,
				locations(exhaustive.data).some((hit) => hit.file === ".dep-git/credential.ts") &&
				!(conservative.data.results ?? []).some((hit) => hit.file_path.startsWith(".dep-git/")));
		}
	}
	report.passed = report.cases.filter((item) => item.passed).length;
	report.total = report.cases.length;
	console.log(JSON.stringify(report, null, 2));
	if (report.passed !== report.total) process.exitCode = 1;
} catch (error) {
	report.error = error instanceof Error ? error.message : String(error);
	console.log(JSON.stringify(report, null, 2));
	process.exitCode = 1;
} finally {
	process.removeListener("SIGINT", cancel);
	process.removeListener("SIGTERM", cancel);
	await rm(root, { recursive: true, force: true });
}
