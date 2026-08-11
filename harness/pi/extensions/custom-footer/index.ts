import { homedir } from "node:os";
import { isAbsolute, relative, resolve, sep } from "node:path";
import type { AssistantMessage, Usage } from "@earendil-works/pi-ai";
import type {
	ExtensionAPI,
	ExtensionContext,
	SessionEntry,
	Theme,
} from "@earendil-works/pi-coding-agent";
import {
	sliceByColumn,
	truncateToWidth,
	visibleWidth,
	wrapTextWithAnsi,
} from "@earendil-works/pi-tui";
import {
	EXTENDED_SUPPORT_STATE_EVENT,
	readOpenAIExtendedSupportState,
	type OpenAIExtendedSupportState,
} from "../openai-extended-support/state";

const UNAVAILABLE = "﹍";
const KILO_STATUS_KEY = "kilo-credits";
const PRIORITY_MODE_MARKER = "⚡︎";
const RATE_ENTRY_TYPE = "custom-footer-rate";
const SUCCESSFUL_STOP_REASONS = new Set(["stop", "length", "toolUse"]);
const CWD_MAX_WIDTH = 30;
const LOCATION_SEPARATOR = " • ";
const DEFAULT_SESSION_TITLE = "New session";

type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
type ModelRow = { id: string; steps: number; cost: number };

type SessionTotals = {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	reasoning: number | undefined;
	cost: number;
	models: ModelRow[];
};

function usageFromEntry(entry: SessionEntry): Usage | undefined {
	if (entry.type === "message") {
		if (entry.message.role === "assistant") return entry.message.usage;
		if (entry.message.role === "toolResult") return entry.message.usage;
	}
	if (entry.type === "compaction" || entry.type === "branch_summary") return entry.usage;
	return undefined;
}

function usageCost(usage: Usage | undefined): number {
	const cost = usage?.cost?.total;
	return typeof cost === "number" && Number.isFinite(cost) ? cost : 0;
}

function displayModel(provider: string | undefined, model: string | undefined): string {
	if (!model) return UNAVAILABLE;
	if (model.includes("/") || !provider) return model;
	return `${provider}/${model}`;
}

function collectSessionTotals(entries: SessionEntry[]): SessionTotals {
	let input = 0;
	let output = 0;
	let cacheRead = 0;
	let cacheWrite = 0;
	let cost = 0;
	let reasoning = 0;
	let sawUsage = false;
	let allReasoningReported = true;
	let otherCost = 0;
	const models = new Map<string, ModelRow>();

	for (const entry of entries) {
		const usage = usageFromEntry(entry);
		if (usage) {
			sawUsage = true;
			input += usage.input ?? 0;
			output += usage.output ?? 0;
			cacheRead += usage.cacheRead ?? 0;
			cacheWrite += usage.cacheWrite ?? 0;
			cost += usageCost(usage);
			if (typeof usage.reasoning === "number" && Number.isFinite(usage.reasoning)) {
				reasoning += usage.reasoning;
			} else {
				allReasoningReported = false;
			}
		}

		if (entry.type === "message" && entry.message.role === "assistant") {
			const message = entry.message as AssistantMessage;
			const identity = `${message.provider}\0${message.model}`;
			let row = models.get(identity);
			if (!row) {
				row = { id: displayModel(message.provider, message.model), steps: 0, cost: 0 };
				models.set(identity, row);
			}
			if (SUCCESSFUL_STOP_REASONS.has(message.stopReason)) row.steps += 1;
			row.cost += usageCost(message.usage);
		} else if (usage) {
			otherCost += usageCost(usage);
		}
	}

	const modelRows = [...models.values()];
	if (otherCost !== 0) modelRows.push({ id: "other", steps: 0, cost: otherCost });

	return {
		input,
		output,
		cacheRead,
		cacheWrite,
		reasoning: sawUsage && allReasoningReported ? reasoning : undefined,
		cost,
		models: modelRows,
	};
}

function formatTokens(value: number | undefined | null): string {
	if (value === undefined || value === null || !Number.isFinite(value)) return UNAVAILABLE;
	if (value <= 0) return "0k";

	const units = [
		{ divisor: 1_000, suffix: "k" },
		{ divisor: 1_000_000, suffix: "m" },
		{ divisor: 1_000_000_000, suffix: "b" },
		{ divisor: 1_000_000_000_000, suffix: "t" },
	] as const;
	let unitIndex = 0;
	while (unitIndex < units.length - 1 && value >= units[unitIndex + 1].divisor) {
		unitIndex += 1;
	}

	while (true) {
		const unit = units[unitIndex];
		const scaled = value / unit.divisor;
		const precision = unitIndex > 0 && scaled < 10 ? 10 : 1;
		const rounded = Math.ceil(scaled * precision) / precision;
		if (rounded < 1000 || unitIndex === units.length - 1) {
			return `${rounded}${unit.suffix}`;
		}
		unitIndex += 1;
	}
}

function formatPercent(value: number | undefined | null): string {
	if (value === undefined || value === null || !Number.isFinite(value)) return UNAVAILABLE;
	return `${Math.ceil(value)}`;
}

function readKiloBalance(
	ctx: ExtensionContext,
	statuses: ReadonlyMap<string, string>,
): string | undefined {
	if (ctx.model?.provider !== "kilo") return undefined;
	// The custom Kilo provider publishes its already-formatted balance here.
	return statuses.get(KILO_STATUS_KEY);
}

function middleTruncate(text: string, width: number): string {
	if (width <= 0) return "";
	if (visibleWidth(text) <= width) return text;
	if (width === 1) return "…";
	const contentWidth = width - 1;
	const leftWidth = Math.ceil(contentWidth / 2);
	const rightWidth = Math.floor(contentWidth / 2);
	const totalWidth = visibleWidth(text);
	const left = sliceByColumn(text, 0, leftWidth, true);
	const right = sliceByColumn(text, Math.max(0, totalWidth - rightWidth), rightWidth, true);
	return `${left}…${right}`;
}

function tailTruncate(text: string, width: number): string {
	if (width <= 0) return "";
	if (visibleWidth(text) <= width) return text;
	if (width === 1) return "…";
	return `…${sliceByColumn(text, visibleWidth(text) - width + 1, width - 1, true)}`;
}

function formatCwd(cwd: string): string {
	const home = homedir();
	const resolvedCwd = resolve(cwd);
	const resolvedHome = resolve(home);
	const relativeToHome = relative(resolvedHome, resolvedCwd);
	const isInsideHome =
		relativeToHome === "" ||
		(relativeToHome !== ".." &&
			!relativeToHome.startsWith(`..${sep}`) &&
			!isAbsolute(relativeToHome));

	if (!isInsideHome) return cwd;
	return relativeToHome === "" ? "~" : `~${sep}${relativeToHome}`;
}

function formatLocation(cwd: string, branch: string | null, width: number): string {
	if (width <= 0) return "";

	const displayCwd = tailTruncate(formatCwd(cwd), Math.min(CWD_MAX_WIDTH, width));
	if (!branch) return tailTruncate(displayCwd, width);

	const branchWidth = visibleWidth(branch);
	const cwdWidth = visibleWidth(displayCwd);
	const separatorWidth = visibleWidth(LOCATION_SEPARATOR);
	const availablePartsWidth = width - separatorWidth;
	const fullLocation = `${displayCwd}${LOCATION_SEPARATOR}${branch}`;

	if (visibleWidth(fullLocation) <= width) return fullLocation;
	if (availablePartsWidth < 2) return tailTruncate(fullLocation, width);

	let fittedCwdWidth = cwdWidth;
	let fittedBranchWidth = branchWidth;
	if (fittedCwdWidth + fittedBranchWidth > availablePartsWidth) {
		if (fittedBranchWidth < availablePartsWidth) {
			fittedCwdWidth = Math.max(1, availablePartsWidth - fittedBranchWidth);
		} else {
			fittedCwdWidth = Math.max(1, Math.floor(availablePartsWidth / 2));
			fittedBranchWidth = Math.max(1, availablePartsWidth - fittedCwdWidth);
		}
	}

	return `${tailTruncate(displayCwd, fittedCwdWidth)}${LOCATION_SEPARATOR}${tailTruncate(
		branch,
		fittedBranchWidth,
	)}`;
}

function renderSessionLine(
	sessionTitle: string | undefined,
	location: string,
	theme: Theme,
	width: number,
): string {
	const renderedLocation = theme.fg("text", location);
	if (!sessionTitle) return alignRight(renderedLocation, width);

	const titleWidth = width - visibleWidth(renderedLocation) - 1;
	if (titleWidth <= 0) return alignRight(renderedLocation, width);

	const title = theme.italic(theme.fg("text", middleTruncate(sessionTitle, titleWidth)));
	return `${title}${" ".repeat(
		Math.max(0, width - visibleWidth(title) - visibleWidth(renderedLocation)),
	)}${renderedLocation}`;
}

function padRight(text: string, width: number): string {
	return text + " ".repeat(Math.max(0, width - visibleWidth(text)));
}

function alignRight(text: string, width: number): string {
	return " ".repeat(Math.max(0, width - visibleWidth(text))) + text;
}

function fit(line: string, width: number): string {
	return visibleWidth(line) <= width ? line : truncateToWidth(line, width, "");
}

function wrapPreservingAnsi(text: string, width: number): string[] {
	if (width <= 0) return [];
	if (visibleWidth(text) <= width) return [text];
	return wrapTextWithAnsi(text, width).flatMap((line) =>
		visibleWidth(line) <= width ? [line] : [truncateToWidth(line, width, "")],
	);
}

function symbolColor(theme: Theme, text: string): string {
	return theme.fg("thinkingLow", text);
}

function thinkingColor(theme: Theme, level: ThinkingLevel, text: string): string {
	const colors = {
		off: "thinkingOff",
		minimal: "thinkingMinimal",
		low: "thinkingLow",
		medium: "thinkingMedium",
		high: "thinkingHigh",
		xhigh: "thinkingXhigh",
		max: "thinkingMax",
	} as const;
	return theme.fg(colors[level], text);
}

function contextPercentColor(theme: Theme, percent: number | null | undefined, text: string): string {
	if (percent !== null && percent !== undefined && percent > 85) {
		return theme.fg("thinkingXhigh", text);
	}
	if (percent !== null && percent !== undefined && percent > 70) {
		return theme.fg("thinkingHigh", text);
	}
	return theme.fg("text", text);
}

function renderContextAndModel(
	ctx: ExtensionContext,
	theme: Theme,
	width: number,
	priorityModeActive: boolean,
	level: ThinkingLevel,
): string[] {
	const context = ctx.getContextUsage();
	const tokenText = formatTokens(context?.tokens);
	const percentText = formatPercent(context?.percent);
	const contextLeft =
		symbolColor(theme, "𐘱") +
		theme.fg("text", `${tokenText} `) +
		contextPercentColor(theme, context?.percent, `${percentText}%`);

	const modelName = displayModel(ctx.model?.provider, ctx.model?.id);
	const modelPrefix = priorityModeActive ? `${PRIORITY_MODE_MARKER} ` : "";
	const separator = theme.fg("text", " • ");
	const levelText = thinkingColor(theme, level, level);
	const modelRight =
		(priorityModeActive ? symbolColor(theme, modelPrefix) : "") +
		theme.fg("text", modelName) +
		separator +
		levelText;

	if (visibleWidth(contextLeft) + 1 + visibleWidth(modelRight) <= width) {
		return [
			contextLeft +
				" ".repeat(width - visibleWidth(contextLeft) - visibleWidth(modelRight)) +
				modelRight,
		];
	}

	const lines = wrapPreservingAnsi(contextLeft, width);
	if (visibleWidth(modelRight) <= width) {
		lines.push(alignRight(modelRight, width));
		return lines;
	}

	// Reflow model and thinking onto separate lines before truncating the identifier.
	const truncatedModelName = middleTruncate(
		modelName,
		Math.max(0, width - visibleWidth(modelPrefix)),
	);
	const renderedModel =
		(priorityModeActive ? symbolColor(theme, modelPrefix) : "") +
		theme.fg("text", truncatedModelName);
	lines.push(alignRight(renderedModel, width));
	const thinking = theme.fg("text", "• ") + levelText;
	lines.push(alignRight(fit(thinking, width), width));
	return lines;
}

function packMetrics(metrics: string[], width: number, gap: string): string[] {
	const lines: string[] = [];
	let current = "";
	for (const metric of metrics) {
		if (visibleWidth(metric) > width) {
			if (current) lines.push(current);
			lines.push(...wrapPreservingAnsi(metric, width));
			current = "";
			continue;
		}
		const candidate = current ? `${current}${gap}${metric}` : metric;
		if (visibleWidth(candidate) <= width) {
			current = candidate;
		} else {
			if (current) lines.push(current);
			current = metric;
		}
	}
	if (current) lines.push(current);
	return lines;
}

function renderUsageAndBalance(
	totals: SessionTotals,
	latestRate: number | undefined,
	kiloBalance: string | undefined,
	level: ThinkingLevel,
	theme: Theme,
	width: number,
): string[] {
	const denominator = totals.input + totals.cacheRead + totals.cacheWrite;
	const cachePercent = denominator > 0 ? (totals.cacheRead / denominator) * 100 : undefined;
	const metric = (symbol: string, value: string) =>
		symbolColor(theme, symbol) + theme.fg("text", value);
	const metrics = [
		metric("↑", formatTokens(totals.input)),
		metric("↓", formatTokens(totals.output)),
		metric("⚛︎", formatTokens(totals.reasoning)),
		metric("▦", `${formatTokens(totals.cacheRead)}/${formatPercent(cachePercent)}%`),
		metric("⇢", `${latestRate === undefined ? UNAVAILABLE : Math.floor(latestRate)}t/s`),
		metric("$", totals.cost.toFixed(2)),
	];

	const usage = metrics.join(" ");
	const needed = visibleWidth(usage) + (kiloBalance ? 1 + visibleWidth(kiloBalance) : 0);
	if (needed <= width) {
		if (!kiloBalance) return [usage];
		return [usage + " ".repeat(width - visibleWidth(usage) - visibleWidth(kiloBalance)) + kiloBalance];
	}

	const lines = visibleWidth(usage) <= width ? [usage] : packMetrics(metrics, width, " ");
	if (kiloBalance) {
		for (const balanceLine of wrapPreservingAnsi(kiloBalance, width)) {
			lines.push(alignRight(balanceLine, width));
		}
	}
	return lines;
}

function formatQuotaClock(seconds: number | null, capturedAt: number, now: number): string {
	if (typeof seconds !== "number" || !Number.isFinite(seconds)) return UNAVAILABLE;
	const reset = new Date(now + (seconds - (now - capturedAt) / 1000) * 1000);
	return new Intl.DateTimeFormat(undefined, {
		weekday: "short",
		hour: "numeric",
		minute: "2-digit",
	}).format(reset);
}

function renderSubscriptionQuota(
	state: OpenAIExtendedSupportState | undefined,
	theme: Theme,
	width: number,
): string[] {
	const snapshot = state?.usage.snapshot;
	if (state?.supported !== true || !snapshot) return [];

	const now = Date.now();
	// The endpoint currently returns the weekly quota in primary_window, which
	// the parser exposes as the five-hour fields. Display those values as 7d.
	const line =
		symbolColor(theme, "⧖") +
		theme.fg("text", ` 7d ${formatPercent(snapshot.fiveHourLeftPercent)}%/`) +
		symbolColor(theme, "↺") +
		theme.fg(
			"text",
			` ${formatQuotaClock(snapshot.fiveHourResetInSeconds, snapshot.capturedAt, now)}`,
		);
	return wrapPreservingAnsi(line, width);
}

function renderModelTable(rows: ModelRow[], theme: Theme, width: number): string[] {
	if (width <= 0) return [];
	const lines = [theme.fg("dim", "─".repeat(width))];
	const stepWidth = Math.max("Steps".length, ...rows.map((row) => String(row.steps).length));
	const costs = rows.map((row) => `$${row.cost.toFixed(2)}`);
	const costWidth = Math.max("Cost".length, ...costs.map((cost) => cost.length));
	const markerWidth = 2;

	for (const gapWidth of [4, 2, 1]) {
		const modelWidth = width - markerWidth - stepWidth - costWidth - gapWidth * 2;
		if (modelWidth < "Model".length) continue;
		const gap = " ".repeat(gapWidth);
		lines.push(
			theme.fg(
				"dim",
				`  ${padRight("Model", modelWidth)}${gap}${"Steps".padStart(stepWidth)}${gap}${"Cost".padStart(costWidth)}`,
			),
		);
		rows.forEach((row, index) => {
			const model = middleTruncate(row.id, modelWidth);
			lines.push(
				theme.fg("text", `➤ ${padRight(model, modelWidth)}`) +
					gap +
					theme.fg("text", String(row.steps).padStart(stepWidth)) +
					gap +
					theme.fg("text", costs[index].padStart(costWidth)),
			);
		});
		return lines;
	}

	// At narrow widths, keep the model and numeric columns on separate rows.
	lines.push(theme.fg("dim", fit("  Model", width)));
	const numericHeader = `${"Steps".padStart(stepWidth)} ${"Cost".padStart(costWidth)}`;
	if (visibleWidth(numericHeader) <= width) {
		lines.push(theme.fg("dim", alignRight(numericHeader, width)));
		rows.forEach((row, index) => {
			lines.push(theme.fg("text", `➤ ${middleTruncate(row.id, Math.max(0, width - markerWidth))}`));
			const values = `${String(row.steps).padStart(stepWidth)} ${costs[index].padStart(costWidth)}`;
			lines.push(theme.fg("text", alignRight(values, width)));
		});
		return lines;
	}

	lines.push(theme.fg("dim", fit("  Steps", width)));
	lines.push(theme.fg("dim", fit("  Cost", width)));
	rows.forEach((row, index) => {
		lines.push(theme.fg("text", `➤ ${middleTruncate(row.id, Math.max(0, width - markerWidth))}`));
		lines.push(...wrapPreservingAnsi(theme.fg("text", `  Steps ${row.steps}`), width));
		lines.push(...wrapPreservingAnsi(theme.fg("text", `  Cost ${costs[index]}`), width));
	});
	return lines;
}

export default function customFooterExtension(pi: ExtensionAPI) {
	let requestRender: (() => void) | undefined;
	let activeAssistantStream:
		| { message: object; timestamp: number; startedAt: number }
		| undefined;
	let latestRate: number | undefined;
	let sessionName: string | undefined;
	let priorityModeActive = readOpenAIExtendedSupportState()?.active === true;

	function restoreLatestRate(ctx: ExtensionContext): void {
		latestRate = undefined;
		for (const entry of ctx.sessionManager.getBranch()) {
			if (entry.type !== "custom" || entry.customType !== RATE_ENTRY_TYPE) continue;
			const rate = (entry.data as { rate?: unknown } | undefined)?.rate;
			if (typeof rate === "number" && Number.isFinite(rate) && rate >= 0) latestRate = rate;
		}
	}

	function install(ctx: ExtensionContext): void {
		if (ctx.mode !== "tui") return;
		ctx.ui.setFooter((tui, theme, footerData) => {
			const rerender = () => tui.requestRender();
			requestRender = rerender;
			const unsubscribeBranch = footerData.onBranchChange(rerender);

			return {
				dispose() {
					unsubscribeBranch();
					if (requestRender === rerender) requestRender = undefined;
				},
				invalidate() {},
				render(rawWidth: number): string[] {
					const width = Math.max(0, Math.floor(rawWidth));
					if (width === 0) return [];
					if (width <= 2) return [" ".repeat(width)];
					const contentWidth = width - 2;
					const level = (ctx.thinkingLevel ?? "off") as ThinkingLevel;
					const totals = collectSessionTotals(ctx.sessionManager.getEntries());
					const kiloBalance = readKiloBalance(
						ctx,
						footerData.getExtensionStatuses(),
					);
					const sessionTitle =
						sessionName ||
						pi.getSessionName() ||
						ctx.sessionManager.getSessionName() ||
						DEFAULT_SESSION_TITLE;
					const location = formatLocation(ctx.cwd, footerData.getGitBranch(), contentWidth);
					const titleLine = renderSessionLine(sessionTitle, location, theme, contentWidth);
					const extendedSupportState = readOpenAIExtendedSupportState();
					const lines = [
						titleLine,
						...renderContextAndModel(
							ctx,
							theme,
							contentWidth,
							priorityModeActive,
							level,
						),
						...renderUsageAndBalance(
							totals,
							latestRate,
							kiloBalance,
							level,
							theme,
							contentWidth,
						),
						...renderSubscriptionQuota(extendedSupportState, theme, contentWidth),
					];
					const completedModels = totals.models.filter((row) => row.id !== "other" && row.steps > 0);
					if (completedModels.length > 1) {
						lines.push(...renderModelTable(totals.models, theme, Math.min(contentWidth, 120)));
					}
					return lines.map((line) => ` ${padRight(fit(line, contentWidth), contentWidth)} `);
				},
			};
		});
	}

	// resources_discover follows every extension's session_start handler, so this
	// installs after Kilo's own footer regardless of extension load order.
	pi.events.on(EXTENDED_SUPPORT_STATE_EVENT, (state) => {
		priorityModeActive =
			typeof state === "object" && state !== null && "active" in state && state.active === true;
		requestRender?.();
	});

	pi.on("session_info_changed", (event) => {
		sessionName = event.name;
		requestRender?.();
	});

	pi.on("session_start", (_event, ctx) => {
		activeAssistantStream = undefined;
		sessionName = ctx.sessionManager.getSessionName();
		restoreLatestRate(ctx);
		requestRender?.();
	});

	pi.on("resources_discover", (_event, ctx) => {
		install(ctx);
	});

	pi.on("message_start", (event) => {
		if (event.message.role !== "assistant") return;
		// Start before Pi consumes response content. Tool-call start events may
		// arrive with buffered arguments, so timing from the first content event
		// can pair a tiny duration with the provider's full output-token count.
		activeAssistantStream = {
			message: event.message,
			timestamp: event.message.timestamp,
			startedAt: performance.now(),
		};
	});

	pi.on("message_update", (event) => {
		if (event.message.role !== "assistant" || !activeAssistantStream) return;
		// Follow the provider's latest partial object while preserving the start.
		activeAssistantStream.message = event.message;
		activeAssistantStream.timestamp = event.message.timestamp;
	});

	pi.on("message_end", (event) => {
		if (event.message.role !== "assistant") return;
		const stream = activeAssistantStream;
		const start =
			stream &&
			(stream.message === event.message || stream.timestamp === event.message.timestamp)
				? stream.startedAt
				: undefined;
		activeAssistantStream = undefined;
		if (start !== undefined && SUCCESSFUL_STOP_REASONS.has(event.message.stopReason)) {
			const elapsedSeconds = (performance.now() - start) / 1000;
			if (elapsedSeconds > 0) {
				latestRate = event.message.usage.output / elapsedSeconds;
				pi.appendEntry(RATE_ENTRY_TYPE, {
					rate: latestRate,
					responseTimestamp: event.message.timestamp,
				});
			}
		}
		requestRender?.();
	});

	// message_end handlers run before Pi persists the finalized message. Repaint
	// again at turn_end, when session totals include that message.
	pi.on("turn_end", () => requestRender?.());
	pi.on("model_select", () => requestRender?.());
	pi.on("thinking_level_select", () => requestRender?.());
	pi.on("session_tree", (_event, ctx) => {
		restoreLatestRate(ctx);
		requestRender?.();
	});

	pi.registerCommand("custom-footer", {
		description: "Reinstall the compact session footer",
		handler: async (_args, ctx) => {
			install(ctx);
			ctx.ui.notify("Custom footer installed", "info");
		},
	});
}
