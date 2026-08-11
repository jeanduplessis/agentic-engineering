import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir, ToolExecutionComponent } from "@earendil-works/pi-coding-agent";
import { visibleWidth } from "@earendil-works/pi-tui";
import { isSkillReadPath, replaceBackgroundAnsi } from "./skill-read.ts";
import { isTerminalImageLine, mapNonImageLines } from "./terminal-image-lines.ts";

type TuiLike = {
	mode?: string;
	openUrl?: (url: string) => void;
	requestRender?: () => void;
	[key: symbol]: unknown;
};

type ToolResult = {
	content: Array<{
		type: string;
		text?: string;
		data?: string;
		mimeType?: string;
	}>;
	details?: unknown;
	isError: boolean;
};

type ToolExecutionInternals = {
	toolName: string;
	toolCallId: string;
	args?: unknown;
	expanded: boolean;
	ui: TuiLike;
	setExpanded(expanded: boolean): void;
	isPartial: boolean;
	result?: ToolResult;
};

type ToolTarget = {
	url: string;
	component: ToolExecutionInternals;
	kind: "toggle" | "agent";
};

type AgentCall = {
	toolCallId: string;
	description?: string;
	subagentType?: string;
	sequence: number;
	agentId?: string;
};

type StartedAgent = {
	id: string;
	type: string;
	description: string;
	sequence: number;
};

type AgentSessionLike = {
	subscribe(listener: () => void): () => void;
};

type AgentRecordLike = {
	id: string;
	type: string;
	description: string;
	status: string;
	startedAt: number;
	completedAt?: number;
	session?: AgentSessionLike;
	[key: string]: unknown;
};

type SubagentsRegistry = {
	getRecord(id: string): unknown;
	listAgents?: () => unknown;
};

type ViewerComponent = {
	handleInput(data: string): void;
	render(width: number): string[];
	invalidate(): void;
	dispose?(): void;
};

type ConversationViewerModule = {
	ConversationViewer: new (
		tui: unknown,
		session: AgentSessionLike,
		record: AgentRecordLike,
		activity: unknown,
		theme: unknown,
		done: (result: undefined) => void,
		onStop?: () => void,
		keybindings?: unknown,
		onSteer?: (message: string) => void,
	) => ViewerComponent;
	VIEWPORT_HEIGHT_PCT: number;
};

type AgentViewerUI = ExtensionContext["ui"];

type PatchedPrototype = Record<PropertyKey, unknown>;

const ORIGINAL_RENDER = Symbol.for("pi.pi-ui-customization.original-render");
const CONTROLLER = Symbol.for("pi.pi-ui-customization.controller");
const ORIGINAL_OPEN_URL = Symbol.for("pi.pi-ui-customization.original-open-url");
const SUBAGENTS_MANAGER = Symbol.for("pi-subagents:manager");
const VIEWER_MODULE = "@tintinweb/pi-subagents/dist/ui/conversation-viewer.js";
const INTERNAL_URL_PREFIX = "pi://tool-output-expand/";
const EXPAND_HINT = "to expand";
const CLICK_HINT = "or click";
// Half the previous darkening distance, applied symmetrically around the base.
const BORDER_CONTRAST_STEP = 0.225;
const ANSI_SEQUENCE = /^(?:\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~])/;
const ANSI_SEQUENCE_GLOBAL = /(?:\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~])/g;

type RgbColor = {
	r: number;
	g: number;
	b: number;
};

type BackgroundColor = {
	mode: "truecolor" | "ansi256";
	color: RgbColor;
	ansi: string;
};

const ANSI_BASIC_COLORS: RgbColor[] = [
	{ r: 0, g: 0, b: 0 },
	{ r: 128, g: 0, b: 0 },
	{ r: 0, g: 128, b: 0 },
	{ r: 128, g: 128, b: 0 },
	{ r: 0, g: 0, b: 128 },
	{ r: 128, g: 0, b: 128 },
	{ r: 0, g: 128, b: 128 },
	{ r: 192, g: 192, b: 192 },
	{ r: 128, g: 128, b: 128 },
	{ r: 255, g: 0, b: 0 },
	{ r: 0, g: 255, b: 0 },
	{ r: 255, g: 255, b: 0 },
	{ r: 0, g: 0, b: 255 },
	{ r: 255, g: 0, b: 255 },
	{ r: 0, g: 255, b: 255 },
	{ r: 255, g: 255, b: 255 },
];

function ansi256ToRgb(index: number): RgbColor {
	if (index < 16) return ANSI_BASIC_COLORS[index]!;
	if (index < 232) {
		const cubeIndex = index - 16;
		const channel = (value: number) => (value === 0 ? 0 : 55 + value * 40);
		return {
			r: channel(Math.floor(cubeIndex / 36)),
			g: channel(Math.floor((cubeIndex % 36) / 6)),
			b: channel(cubeIndex % 6),
		};
	}

	const gray = 8 + (index - 232) * 10;
	return { r: gray, g: gray, b: gray };
}

function rgbToAnsi256(color: RgbColor): number {
	let closest = 0;
	let closestDistance = Number.POSITIVE_INFINITY;
	for (let index = 0; index < 256; index++) {
		const candidate = ansi256ToRgb(index);
		const distance =
			(color.r - candidate.r) ** 2 * 0.299 +
			(color.g - candidate.g) ** 2 * 0.587 +
			(color.b - candidate.b) ** 2 * 0.114;
		if (distance < closestDistance) {
			closest = index;
			closestDistance = distance;
		}
	}
	return closest;
}

function asObject(value: unknown): Record<string, unknown> | undefined {
	return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function asString(value: unknown): string | undefined {
	return typeof value === "string" && value.length > 0 ? value : undefined;
}

class PiUiCustomizationController {
	private targets = new Map<string, ToolTarget>();
	private targetsByComponent = new WeakMap<object, ToolTarget>();
	private agentCalls = new Map<string, AgentCall>();
	private startedAgents = new Map<string, StartedAgent>();
	private tui?: TuiLike;
	private uiContext?: AgentViewerUI;
	private fallbackOpenUrl?: (url: string) => void;
	private viewerModulePromise?: Promise<ConversationViewerModule | undefined>;
	private nextTargetId = 0;
	private eventSequence = 0;

	reset(ui?: AgentViewerUI): void {
		this.targets = new Map();
		this.targetsByComponent = new WeakMap();
		this.agentCalls = new Map();
		this.startedAgents = new Map();
		this.tui = undefined;
		this.uiContext = ui;
		this.fallbackOpenUrl = undefined;
		this.nextTargetId = 0;
		this.eventSequence = 0;
	}

	recordToolStart(toolCallId: string, args: unknown): void {
		const params = asObject(args);
		const call: AgentCall = {
			toolCallId,
			description: asString(params?.description),
			subagentType: asString(params?.subagent_type),
			sequence: ++this.eventSequence,
		};
		this.agentCalls.set(toolCallId, call);
		this.correlateStartedAgent(call);
	}

	recordStartedAgent(data: unknown): void {
		const event = asObject(data);
		const id = asString(event?.id);
		const type = asString(event?.type);
		const description = asString(event?.description);
		if (!id || !type || !description) return;

		const started: StartedAgent = {
			id,
			type,
			description,
			sequence: ++this.eventSequence,
		};
		this.startedAgents.set(id, started);
		for (const call of this.agentCalls.values()) this.correlateStartedAgent(call, started);
	}

	private correlateStartedAgent(call: AgentCall, started?: StartedAgent): void {
		if (call.agentId) return;
		const candidates = started ? [started] : [...this.startedAgents.values()];
		const claimedIds = new Set(
			[...this.agentCalls.values()]
				.filter((other) => other !== call && other.agentId)
				.map((other) => other.agentId),
		);
		const match = candidates
			.filter((candidate) =>
				!claimedIds.has(candidate.id) &&
				candidate.sequence >= call.sequence &&
				this.sameAgentType(call.subagentType, candidate.type) &&
				this.sameDescription(call.description, candidate.description),
			)
			.sort((left, right) => right.sequence - left.sequence)[0];
		if (match) call.agentId = match.id;
	}

	private sameAgentType(left: string | undefined, right: string | undefined): boolean {
		return !!left && !!right && left.toLowerCase() === right.toLowerCase();
	}

	private sameDescription(left: string | undefined, right: string | undefined): boolean {
		return !!left && !!right && left === right;
	}

	attach(ui: unknown): void {
		if (!ui || typeof ui !== "object") return;

		const tui = ui as TuiLike;
		this.tui = tui;
		if (tui.mode !== "fullscreen") return;

		const currentOpenUrl = tui.openUrl;
		if (currentOpenUrl !== this.handleOpenUrl) {
			const originalOpenUrl = tui[ORIGINAL_OPEN_URL];
			this.fallbackOpenUrl =
				typeof originalOpenUrl === "function"
					? (originalOpenUrl as (url: string) => void)
					: typeof currentOpenUrl === "function"
						? currentOpenUrl
						: undefined;
			tui[ORIGINAL_OPEN_URL] = this.fallbackOpenUrl;
			try {
				tui.openUrl = this.handleOpenUrl;
			} catch {
				// A future TUI implementation may expose a read-only URL handler.
			}
		}
	}

	decorate(component: ToolExecutionInternals, lines: string[], width: number): string[] {
		const skillLines = this.recolorSkillRead(component, lines);
		const hasExpandHint = skillLines.some(
			(line) => !isTerminalImageLine(line) && this.hasExpansionHint(this.plainText(line)),
		);
		const isAgent = component.toolName === "Agent";
		const isCompletedRead =
			component.toolName === "read" && !component.isPartial && component.result?.isError === false;
		const isClickable = isAgent || hasExpandHint || isCompletedRead;
		const displayLines =
			!component.expanded && hasExpandHint ? this.compactCollapsedLines(skillLines) : skillLines;
		if (this.tui?.mode !== "fullscreen" || (!component.expanded && !isClickable)) {
			return skillLines;
		}

		let target: ToolTarget | undefined;
		return mapNonImageLines(displayLines, (line) => {
			target ??= this.getTarget(component, isAgent ? "agent" : "toggle");
			const visibleLine = component.expanded ? line : this.stripExpansionHint(line);
			const paddedLine = this.padLineToWidth(visibleLine, width);
			const borderedLine = this.addLeftBorder(paddedLine, component.expanded, width);

			// Keep existing file/URL links usable while making every other part of
			// the block clickable to toggle its expanded state.
			return this.wrapOutsideHyperlinks(borderedLine, target.url);
		});
	}

	private recolorSkillRead(component: ToolExecutionInternals, lines: string[]): string[] {
		if (!this.isSuccessfulSkillRead(component)) return lines;

		const theme = this.uiContext?.theme;
		if (!theme) return lines;

		let fromAnsi: string;
		let toAnsi: string;
		try {
			fromAnsi = theme.getBgAnsi("toolSuccessBg");
			toAnsi = theme.getBgAnsi("customMessageBg");
		} catch {
			return lines;
		}
		if (!fromAnsi || fromAnsi === toAnsi) return lines;

		return mapNonImageLines(lines, (line) => replaceBackgroundAnsi(line, fromAnsi, toAnsi));
	}

	private isSuccessfulSkillRead(component: ToolExecutionInternals): boolean {
		if (component.toolName !== "read" || component.isPartial || component.result?.isError) {
			return false;
		}
		const args = asObject(component.args);
		const path = asString(args?.path) ?? asString(args?.file_path);
		return !!path && isSkillReadPath(path);
	}

	private compactCollapsedLines(lines: string[]): string[] {
		const firstContentIndex = lines.findIndex((line) => this.plainText(line).trim().length > 0);
		if (firstContentIndex === -1) return lines;

		const keep = new Set<number>();
		for (let index = 0; index < lines.length; index++) {
			if (isTerminalImageLine(lines[index]!)) keep.add(index);
		}
		for (let index = 0; index <= firstContentIndex; index++) {
			keep.add(index);
		}

		let lastOutputIndex: number | undefined;
		for (let index = firstContentIndex + 1; index < lines.length; index++) {
			const text = this.plainText(lines[index]!).trim();
			if (!text || this.hasExpansionHint(text) || this.isOutputMetadata(text)) continue;
			lastOutputIndex = index;
		}
		if (lastOutputIndex !== undefined) keep.add(lastOutputIndex);

		for (let index = firstContentIndex + 1; index < lines.length; index++) {
			const text = this.plainText(lines[index]!).trim();
			if (this.hasExpansionHint(text) || this.isOutputMetadata(text)) {
				keep.add(index);
			}
		}

		// ToolExecutionComponent's Box adds a styled bottom-padding row. Keep
		// trailing blank rows so the collapsed block retains its background below
		// the visible content.
		for (let index = lines.length - 1; index > firstContentIndex; index--) {
			if (this.plainText(lines[index]!).trim().length > 0) break;
			keep.add(index);
		}

		return lines.filter((_line, index) => keep.has(index));
	}

	private hasExpansionHint(text: string): boolean {
		return text.includes(EXPAND_HINT) || text.includes(CLICK_HINT);
	}

	private stripExpansionHint(line: string): string {
		const text = this.plainText(line);
		const hintCandidates = [EXPAND_HINT, CLICK_HINT]
			.map((hint) => ({ hint, index: text.indexOf(hint) }))
			.filter(({ index }) => index !== -1)
			.sort((left, right) => left.index - right.index);
		const match = hintCandidates[0];
		if (!match) return line;

		const hintEnd = match.index + match.hint.length;
		const openIndex = text.lastIndexOf("(", match.index);
		const closeIndex = text.indexOf(")", hintEnd);
		if (openIndex !== -1 && closeIndex !== -1) {
			const commaIndex = text.lastIndexOf(",", match.index);
			const hasEarlierContent = commaIndex > openIndex;
			const removeStart = hasEarlierContent ? commaIndex : openIndex;
			const removeEnd = hasEarlierContent ? closeIndex : closeIndex + 1;
			return this.removePlainTextRange(line, removeStart, removeEnd);
		}

		return this.removePlainTextRange(line, match.index, hintEnd);
	}

	private removePlainTextRange(line: string, start: number, end: number): string {
		let result = "";
		let rawIndex = 0;
		let textIndex = 0;

		while (rawIndex < line.length) {
			const ansi = this.ansiSequenceAt(line, rawIndex);
			if (ansi) {
				result += ansi;
				rawIndex += ansi.length;
				continue;
			}

			const codePoint = line.codePointAt(rawIndex);
			if (codePoint === undefined) break;
			const character = String.fromCodePoint(codePoint);
			const nextTextIndex = textIndex + character.length;
			if (nextTextIndex <= start || textIndex >= end) {
				result += character;
			}
			textIndex = nextTextIndex;
			rawIndex += character.length;
		}

		return result;
	}

	private addLeftBorder(line: string, expanded: boolean, width: number): string {
		const lineWithGap = this.insertSpaceAfterFirstVisibleCharacter(line);
		const boundedLine =
			visibleWidth(lineWithGap) > width ? this.removeLastVisibleCell(lineWithGap) : lineWithGap;
		const borderBackground = this.getBorderColor(boundedLine, expanded);
		const background = this.getBackgroundColor(boundedLine);
		const restoreBackground = background?.ansi ?? "\x1b[49m";
		return this.replaceFirstVisibleCharacter(`${borderBackground} ${restoreBackground}`, boundedLine);
	}

	private insertSpaceAfterFirstVisibleCharacter(line: string): string {
		let rawIndex = 0;
		while (rawIndex < line.length) {
			const ansi = this.ansiSequenceAt(line, rawIndex);
			if (ansi) {
				rawIndex += ansi.length;
				continue;
			}

			const codePoint = line.codePointAt(rawIndex);
			if (codePoint === undefined) break;
			const character = String.fromCodePoint(codePoint);
			if (visibleWidth(character) > 0) {
				const end = rawIndex + character.length;
				return `${line.slice(0, end)} ${line.slice(end)}`;
			}
			rawIndex += character.length;
		}

		return line;
	}

	private removeLastVisibleCell(line: string): string {
		let rawIndex = 0;
		let lastStart = -1;
		let lastEnd = -1;
		let lastWidth = 0;
		while (rawIndex < line.length) {
			const ansi = this.ansiSequenceAt(line, rawIndex);
			if (ansi) {
				rawIndex += ansi.length;
				continue;
			}

			const codePoint = line.codePointAt(rawIndex);
			if (codePoint === undefined) break;
			const character = String.fromCodePoint(codePoint);
			const characterWidth = visibleWidth(character);
			if (characterWidth > 0) {
				lastStart = rawIndex;
				lastEnd = rawIndex + character.length;
				lastWidth = characterWidth;
			}
			rawIndex += character.length;
		}

		if (lastStart === -1) return line;
		return `${line.slice(0, lastStart)}${" ".repeat(Math.max(0, lastWidth - 1))}${line.slice(lastEnd)}`;
	}

	private replaceFirstVisibleCharacter(replacement: string, line: string): string {
		let rawIndex = 0;
		while (rawIndex < line.length) {
			const ansi = this.ansiSequenceAt(line, rawIndex);
			if (ansi) {
				rawIndex += ansi.length;
				continue;
			}

			const codePoint = line.codePointAt(rawIndex);
			if (codePoint === undefined) break;
			const character = String.fromCodePoint(codePoint);
			const characterWidth = visibleWidth(character);
			if (characterWidth > 0) {
				return (
					line.slice(0, rawIndex) +
					replacement +
					" ".repeat(Math.max(0, characterWidth - 1)) +
					line.slice(rawIndex + character.length)
				);
			}
			rawIndex += character.length;
		}

		return line;
	}

	private getBorderColor(line: string, expanded: boolean): string {
		const background = this.getBackgroundColor(line);
		if (!background) {
			return `\x1b[48;5;${expanded ? 250 : 240}m`;
		}

		const factor = expanded ? 1 + BORDER_CONTRAST_STEP : 1 - BORDER_CONTRAST_STEP;
		const color = {
			r: Math.min(255, Math.round(background.color.r * factor)),
			g: Math.min(255, Math.round(background.color.g * factor)),
			b: Math.min(255, Math.round(background.color.b * factor)),
		};

		if (background.mode === "ansi256") {
			return `\x1b[48;5;${rgbToAnsi256(color)}m`;
		}
		return `\x1b[48;2;${color.r};${color.g};${color.b}m`;
	}

	private getBackgroundColor(line: string): BackgroundColor | undefined {
		const sgrPattern = /\x1b\[([0-9;]*)m/g;
		for (const match of line.matchAll(sgrPattern)) {
			const params = match[1] ? match[1].split(";").map(Number) : [0];
			for (let index = 0; index < params.length; index++) {
				const parameter = params[index];
				if (parameter === undefined) continue;

				if (parameter === 48 && params[index + 1] === 2) {
					const red = params[index + 2];
					const green = params[index + 3];
					const blue = params[index + 4];
					if (red !== undefined && green !== undefined && blue !== undefined) {
						return {
							mode: "truecolor",
							color: { r: red, g: green, b: blue },
							ansi: `\x1b[48;2;${red};${green};${blue}m`,
						};
					}
				}

				if (parameter === 48 && params[index + 1] === 5) {
					const colorIndex = params[index + 2];
					if (colorIndex !== undefined) {
						return {
							mode: "ansi256",
							color: ansi256ToRgb(colorIndex),
							ansi: `\x1b[48;5;${colorIndex}m`,
						};
					}
				}

				if (parameter >= 40 && parameter <= 47) {
					const colorIndex = parameter - 40;
					return {
						mode: "ansi256",
						color: ansi256ToRgb(colorIndex),
						ansi: `\x1b[48;5;${colorIndex}m`,
					};
				}
				if (parameter >= 100 && parameter <= 107) {
					const colorIndex = parameter - 100 + 8;
					return {
						mode: "ansi256",
						color: ansi256ToRgb(colorIndex),
						ansi: `\x1b[48;5;${colorIndex}m`,
					};
				}
			}
		}
		return undefined;
	}

	private ansiSequenceAt(line: string, index: number): string | undefined {
		return ANSI_SEQUENCE.exec(line.slice(index))?.[0];
	}

	private plainText(line: string): string {
		return line.replace(ANSI_SEQUENCE_GLOBAL, "");
	}

	private isOutputMetadata(text: string): boolean {
		return (
			text.startsWith("[Full output:") ||
			text.startsWith("[Truncated:") ||
			text.startsWith("[First line") ||
			text.startsWith("Took ") ||
			text.startsWith("Elapsed ")
		);
	}

	private padLineToWidth(line: string, width: number): string {
		const padding = Math.max(0, width - visibleWidth(line));
		if (padding === 0) return line;

		const ansiSuffix = /(?:\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~])+$/;
		const suffix = ansiSuffix.exec(line);
		const suffixStart = suffix ? suffix.index : line.length;
		return `${line.slice(0, suffixStart)}${" ".repeat(padding)}${line.slice(suffixStart)}`;
	}

	private wrapOutsideHyperlinks(line: string, url: string): string {
		const osc8Pattern = /\x1b\]8;[^\x07\x1b]*(?:\x07|\x1b\\)/g;
		let result = "";
		let cursor = 0;
		let externalLinkOpen = false;

		for (const match of line.matchAll(osc8Pattern)) {
			const index = match.index ?? cursor;
			const segment = line.slice(cursor, index);
			result += externalLinkOpen ? segment : this.wrapSegment(segment, url);

			const sequence = match[0];
			result += sequence;
			const body = sequence.slice(4, sequence.endsWith("\x07") ? -1 : -2);
			const separatorIndex = body.indexOf(";");
			externalLinkOpen = separatorIndex !== -1 && body.slice(separatorIndex + 1).length > 0;
			cursor = index + sequence.length;
		}

		const trailing = line.slice(cursor);
		return result + (externalLinkOpen ? trailing : this.wrapSegment(trailing, url));
	}

	private wrapSegment(segment: string, url: string): string {
		if (segment.length === 0) return segment;
		return `${this.openLink(url)}${segment}${this.closeLink()}`;
	}

	private getTarget(component: ToolExecutionInternals, kind: ToolTarget["kind"]): ToolTarget {
		const existing = this.targetsByComponent.get(component as object);
		if (existing) return existing;

		const target: ToolTarget = {
			url: `${INTERNAL_URL_PREFIX}${++this.nextTargetId}`,
			component,
			kind,
		};
		this.targetsByComponent.set(component as object, target);
		this.targets.set(target.url, target);
		return target;
	}

	private openLink(url: string): string {
		return `\x1b]8;;${url}\x07`;
	}

	private closeLink(): string {
		return "\x1b]8;;\x07";
	}

	private handleOpenUrl = (url: string): void => {
		const target = this.targets.get(url);
		if (target) {
			if (target.kind === "agent") {
				void this.openAgentViewer(target.component);
			} else {
				target.component.setExpanded(!target.component.expanded);
				this.tui?.requestRender?.();
			}
			return;
		}

		try {
			this.fallbackOpenUrl?.call(this.tui, url);
		} catch {
			// Opening external terminal links is best-effort.
		}
	};

	private async openAgentViewer(component: ToolExecutionInternals): Promise<void> {
		const ui = this.uiContext;
		if (!ui) return;

		let resolved: { record: AgentRecordLike; session: AgentSessionLike } | undefined;
		try {
			resolved = this.resolveAgent(component);
		} catch {
			resolved = undefined;
		}
		if (!resolved) {
			this.notify("This Agent result is not connected to a live subagent session.", "info");
			return;
		}
		const agent = resolved;
		const viewer = await this.loadViewer().catch(() => undefined);
		if (!viewer) {
			this.notify("The optional pi-subagents conversation viewer is unavailable.", "warning");
			return;
		}

		try {
			await ui.custom<undefined>(
				(tui, theme, keybindings, done) =>
					new viewer.ConversationViewer(
						tui,
						agent.session,
						agent.record,
						undefined,
						theme,
						done,
						undefined,
						keybindings,
					),
				{
					overlay: true,
					overlayOptions: {
						anchor: "center",
						width: "90%",
						maxHeight: `${viewer.VIEWPORT_HEIGHT_PCT}%`,
					},
				},
			);
		} catch {
			this.notify("Unable to open the subagent conversation viewer.", "warning");
		}
	}

	private resolveAgent(component: ToolExecutionInternals):
		| { record: AgentRecordLike; session: AgentSessionLike }
		| undefined {
		const details = asObject(component.result?.details);
		const detailsAgentId = asString(details?.agentId);
		const call = this.agentCalls.get(component.toolCallId);
		const directId = detailsAgentId ?? call?.agentId;
		if (directId) {
			const record = this.getRecord(directId);
			if (record?.session) return { record, session: record.session };
			return undefined;
		}

		const description = asString(details?.description) ?? call?.description;
		const type = asString(details?.subagentType) ?? call?.subagentType;
		const claimedIds = new Set(
			[...this.agentCalls.values()]
				.filter((other) => other !== call && other.agentId)
				.map((other) => other.agentId),
		);
		const startedMatches = [...this.startedAgents.values()]
			.filter(
				(started) =>
					!claimedIds.has(started.id) &&
					this.sameAgentType(type, started.type) &&
					this.sameDescription(description, started.description),
			)
			.sort((left, right) => right.sequence - left.sequence);
		for (const started of startedMatches) {
			const record = this.getRecord(started.id);
			if (record?.session) return { record, session: record.session };
		}

		// The registry intentionally exposes only getRecord today. If a compatible
		// version also exposes listAgents, use it as a bounded metadata match rather
		// than guessing an unrelated session.
		const registry = this.getRegistry();
		let records: unknown;
		try {
			records = registry?.listAgents?.();
		} catch {
			records = undefined;
		}
		if (Array.isArray(records)) {
			const matches = records
				.map((candidate) => this.asAgentRecord(candidate))
				.filter(
					(record): record is AgentRecordLike =>
						!!record &&
						!!record.session &&
						this.matchesAgent(record, description, type),
				)
				.sort((left, right) => right.startedAt - left.startedAt);
			const record = matches[0];
			if (record?.session) return { record, session: record.session };
		}
		return undefined;
	}

	private matchesAgent(record: AgentRecordLike, description?: string, type?: string): boolean {
		if (!description && !type) return false;
		if (description && record.description !== description) return false;
		if (type && !this.sameAgentType(type, record.type)) return false;
		return true;
	}

	private getRegistry(): SubagentsRegistry | undefined {
		const value = (globalThis as unknown as Record<PropertyKey, unknown>)[SUBAGENTS_MANAGER];
		const registry = asObject(value);
		return typeof registry?.getRecord === "function"
			? (registry as unknown as SubagentsRegistry)
			: undefined;
	}

	private getRecord(id: string): AgentRecordLike | undefined {
		try {
			return this.asAgentRecord(this.getRegistry()?.getRecord(id));
		} catch {
			return undefined;
		}
	}

	private asAgentRecord(value: unknown): AgentRecordLike | undefined {
		const record = asObject(value);
		if (
			!record ||
			typeof record.id !== "string" ||
			typeof record.type !== "string" ||
			typeof record.description !== "string" ||
			typeof record.status !== "string" ||
			typeof record.startedAt !== "number"
		)
			return undefined;
		return record as unknown as AgentRecordLike;
	}

	private async loadViewer(): Promise<ConversationViewerModule | undefined> {
		this.viewerModulePromise ??= (async () => {
			let viewerPath: string | undefined;
			const requireCandidates: Array<ReturnType<typeof createRequire> | undefined> = [];
			try {
				requireCandidates.push(createRequire(join(getAgentDir(), "npm", "package.json")));
			} catch {
				// Pi installations without the npm root use the fallback below.
			}
			try {
				requireCandidates.push(createRequire(join(getAgentDir(), "package.json")));
			} catch {
				// The agent directory may not contain a package manifest.
			}
			try {
				requireCandidates.push(createRequire(import.meta.url));
			} catch {
				// An unusual loader may not expose import.meta.url to createRequire.
			}
			for (const resolver of requireCandidates) {
				if (!resolver) continue;
				try {
					viewerPath = resolver.resolve(VIEWER_MODULE);
					break;
				} catch {
					// Try the next supported Pi/package resolution root.
				}
			}
			if (!viewerPath) return undefined;
			try {
				const module = (await import(pathToFileURL(viewerPath).href)) as unknown as ConversationViewerModule;
				return typeof module.ConversationViewer === "function" &&
					typeof module.VIEWPORT_HEIGHT_PCT === "number"
					? module
					: undefined;
			} catch {
				return undefined;
			}
		})();
		return this.viewerModulePromise;
	}

	private notify(message: string, type: "info" | "warning" | "error"): void {
		try {
			this.uiContext?.notify(message, type);
		} catch {
			// Notifications are best-effort and must not disrupt terminal links.
		}
	}
}

function installRenderPatch(controller: PiUiCustomizationController): void {
	const prototype = ToolExecutionComponent.prototype as unknown as PatchedPrototype;
	prototype[CONTROLLER] = controller;

	if (prototype[ORIGINAL_RENDER]) return;

	const originalRender = ToolExecutionComponent.prototype.render;
	prototype[ORIGINAL_RENDER] = originalRender;

	ToolExecutionComponent.prototype.render = function (width: number): string[] {
		const internals = this as unknown as ToolExecutionInternals;
		const activeController = (ToolExecutionComponent.prototype as unknown as PatchedPrototype)[
			CONTROLLER
		] as PiUiCustomizationController | undefined;

		activeController?.attach(internals.ui);
		const lines = originalRender.call(this, width);
		return activeController?.decorate(internals, lines, width) ?? lines;
	};
}

export default function piUiCustomization(pi: ExtensionAPI): void {
	const controller = new PiUiCustomizationController();
	installRenderPatch(controller);

	pi.on("tool_execution_start", (event) => {
		if (event.toolName === "Agent") controller.recordToolStart(event.toolCallId, event.args);
	});
	pi.events.on("subagents:started", (data) => controller.recordStartedAgent(data));
	pi.on("session_start", (_event, ctx) => controller.reset(ctx.ui));
	pi.on("session_shutdown", () => controller.reset());
}
