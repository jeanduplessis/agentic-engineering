import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
	CompactionSummaryMessageComponent,
	createEditToolDefinition,
	ToolExecutionComponent,
	UserMessageComponent,
} from "@earendil-works/pi-coding-agent";
import { stripTerminalSequences, visibleWidth } from "@earendil-works/pi-tui";
import { installLinkHover } from "./link-hover.ts";
import { isSkillReadPath, replaceBackgroundAnsi } from "./skill-read.ts";
import { isTerminalImageLine, mapNonImageLines } from "./terminal-image-lines.ts";
import { decideToolCollapse } from "./tool-collapse.ts";

type TuiLike = {
	mode?: string;
	openUrl?: (url: string) => void;
	requestRender?: () => void;
	[key: symbol]: unknown;
};

type ExpandableComponent = {
	expanded: boolean;
	setExpanded(expanded: boolean): void;
};

type ToolExecutionInternals = ExpandableComponent & {
	toolName: string;
	toolCallId: string;
	toolDefinition?: {
		renderShell?: "default" | "self";
		renderCall?: unknown;
		renderResult?: unknown;
	};
	args?: unknown;
	ui: TuiLike;
	isPartial: boolean;
	result?: { isError: boolean };
};

type ToolTarget = {
	url: string;
	component: ExpandableComponent;
};

type ToolUi = ExtensionContext["ui"];

type PatchedPrototype = Record<PropertyKey, unknown>;

type UrlHandlerState = {
	originalOpenUrl?: (url: string) => void;
	controller?: PiUiCustomizationController;
};

const ORIGINAL_RENDER = Symbol.for("pi.pi-ui-customization.original-render");
const CONTROLLER = Symbol.for("pi.pi-ui-customization.controller");
const URL_HANDLER_STATE = Symbol.for("pi.pi-ui-customization.url-handler-state");
// Renderer functions are shared across builtin definitions; do not classify custom
// edit overrides by name alone or strip their renderer-owned safety/detail rows.
const BUILTIN_EDIT_RENDERERS = createEditToolDefinition(process.cwd());
const INTERNAL_URL_PREFIX = "pi://tool-output-expand/";
const EXPAND_HINT = "to expand";
const CLICK_HINT = "or click";
// Category colors do not encode execution state; native status text still does.
const TOOL_BACKGROUND = "\x1b[48;2;40;49;38m"; // #283126
const TOOL_GUTTER = "\x1b[48;2;34;39;31m"; // #22271f
const SKILL_BACKGROUND = "\x1b[48;2;45;40;56m"; // #2d2838
const SKILL_GUTTER = "\x1b[48;2;36;32;46m"; // #24202e
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

function asObject(value: unknown): Record<string, unknown> | undefined {
	return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function asString(value: unknown): string | undefined {
	return typeof value === "string" && value.length > 0 ? value : undefined;
}

class PiUiCustomizationController {
	private targets = new Map<string, ToolTarget>();
	private targetsByComponent = new WeakMap<object, ToolTarget>();
	private tui?: TuiLike;
	private uiContext?: ToolUi;
	private urlHandlerState?: UrlHandlerState;
	private nextTargetId = 0;

	reset(ui?: ToolUi): void {
		if (this.urlHandlerState?.controller === this) {
			this.urlHandlerState.controller = undefined;
		}
		this.urlHandlerState = undefined;
		this.targets = new Map();
		this.targetsByComponent = new WeakMap();
		this.tui = undefined;
		this.uiContext = ui;
		this.nextTargetId = 0;
	}

	attach(ui: unknown): void {
		if (!ui || typeof ui !== "object") return;

		const tui = ui as TuiLike;
		this.tui = tui;
		if (tui.mode !== "fullscreen") return;

		// Pi's stable TUI proxy wraps function properties on every read. Keep the
		// native callback inside an object so redraws and reloads cannot nest it.
		let state = tui[URL_HANDLER_STATE] as UrlHandlerState | undefined;
		if (!state) {
			const originalOpenUrl = tui.openUrl;
			const binding: UrlHandlerState = {
				originalOpenUrl: typeof originalOpenUrl === "function" ? originalOpenUrl : undefined,
			};
			try {
				tui.openUrl = (url: string): void => {
					if (binding.controller?.handleInternalUrl(url)) return;
					try {
						binding.originalOpenUrl?.call(tui, url);
					} catch {
						// Opening external terminal links is best-effort.
					}
				};
				tui[URL_HANDLER_STATE] = binding;
			} catch {
				// A future TUI implementation may expose a read-only URL handler.
				return;
			}
			state = binding;
		}
		if (this.urlHandlerState !== state && this.urlHandlerState?.controller === this) {
			this.urlHandlerState.controller = undefined;
		}
		state.controller = this;
		this.urlHandlerState = state;
	}

	decorateExpandable(component: ExpandableComponent, lines: string[]): string[] {
		if (this.tui?.mode !== "fullscreen") return lines;

		const target = this.getTarget(component);
		return mapNonImageLines(lines, (line) => this.wrapOutsideHyperlinks(line, target.url));
	}

	decorate(component: ToolExecutionInternals, lines: string[], width: number): string[] {
		// Builtin edit owns a Box but renders the full diff even when collapsed.
		// All other self-owned shells retain their safety/detail rows and framing.
		const definition = component.toolDefinition;
		const builtinEdit = component.toolName === "edit" &&
			definition?.renderCall === BUILTIN_EDIT_RENDERERS.renderCall &&
			definition?.renderResult === BUILTIN_EDIT_RENDERERS.renderResult;
		if (definition?.renderShell === "self" && !builtinEdit) {
			return this.decorateExpandable(component, lines);
		}
		const skillRead = this.isSkillRead(component);
		const categoryLines = this.recolorToolBackground(lines, skillRead ? SKILL_BACKGROUND : TOOL_BACKGROUND);
		const decision = decideToolCollapse({
			expanded: component.expanded,
		});
		const titleOnly = builtinEdit && !component.isPartial && component.result?.isError === false;
		const displayLines = decision.compact ? this.compactCollapsedLines(categoryLines, titleOnly) : categoryLines;
		if (this.tui?.mode !== "fullscreen" || (!component.expanded && !decision.clickable)) {
			return categoryLines;
		}

		let target: ToolTarget | undefined;
		return mapNonImageLines(displayLines, (line) => {
			target ??= this.getTarget(component);
			const visibleLine = component.expanded ? line : this.stripExpansionHint(line);
			const paddedLine = this.padLineToWidth(visibleLine, width);
			const borderedLine = this.addLeftBorder(paddedLine, skillRead ? SKILL_GUTTER : TOOL_GUTTER, width);

			// Keep existing file/URL links usable while making every other part of
			// the block clickable to toggle its expanded state.
			return this.wrapOutsideHyperlinks(borderedLine, target.url);
		});
	}

	private recolorToolBackground(lines: string[], toAnsi: string): string[] {
		const theme = this.uiContext?.theme;
		if (!theme) return lines;

		let backgrounds: string[];
		try {
			backgrounds = (["toolPendingBg", "toolSuccessBg", "toolErrorBg"] as const).map(
				(color) => theme.getBgAnsi(color),
			);
		} catch {
			return lines;
		}
		return mapNonImageLines(lines, (line) =>
			backgrounds.reduce((text, fromAnsi) => replaceBackgroundAnsi(text, fromAnsi, toAnsi), line),
		);
	}

	private isSkillRead(component: ToolExecutionInternals): boolean {
		if (component.toolName !== "read") return false;
		const args = asObject(component.args);
		const path = asString(args?.path) ?? asString(args?.file_path);
		return !!path && isSkillReadPath(path);
	}

	private compactCollapsedLines(lines: string[], titleOnly = false): string[] {
		const firstContentIndex = lines.findIndex((line) => this.plainText(line).trim().length > 0);
		if (firstContentIndex === -1) return lines;

		const keep = new Set<number>();
		for (let index = 0; index < lines.length; index++) {
			if (!isTerminalImageLine(lines[index]!)) continue;
			keep.add(index);
			// Keep native box padding and image spacers, including iTerm2's
			// leading height reservations before its cursor-up image sequence.
			for (let before = index - 1; before >= 0; before--) {
				if (isTerminalImageLine(lines[before]!) || this.plainText(lines[before]!).trim()) break;
				keep.add(before);
			}
		}
		for (let index = 0; index <= firstContentIndex; index++) {
			keep.add(index);
		}

		if (!titleOnly) {
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
		}

		// Keep one bottom-padding row, not trailing newlines from streaming
		// content: those would make the collapsed block grow and shrink as the
		// next line arrives. Image blocks need their trailing image-height rows.
		const hasImages = lines.some(isTerminalImageLine);
		for (let index = lines.length - 1; index > firstContentIndex; index--) {
			if (this.plainText(lines[index]!).trim().length > 0) break;
			keep.add(index);
			if (!hasImages) break;
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

	private addLeftBorder(line: string, borderBackground: string, width: number): string {
		const lineWithGap = this.insertSpaceAfterFirstVisibleCharacter(line);
		const boundedLine =
			visibleWidth(lineWithGap) > width ? this.removeLastVisibleCell(lineWithGap) : lineWithGap;
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

	private getTarget(component: ExpandableComponent): ToolTarget {
		const existing = this.targetsByComponent.get(component as object);
		if (existing) return existing;

		const target: ToolTarget = {
			url: `${INTERNAL_URL_PREFIX}${++this.nextTargetId}`,
			component,
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

	private handleInternalUrl(url: string): boolean {
		const target = this.targets.get(url);
		if (!target) return false;
		target.component.setExpanded(!target.component.expanded);
		this.tui?.requestRender?.();
		return true;
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

function installCompactionRenderPatch(controller: PiUiCustomizationController): void {
	const prototype = CompactionSummaryMessageComponent.prototype as unknown as PatchedPrototype;
	prototype[CONTROLLER] = controller;

	if (prototype[ORIGINAL_RENDER]) return;

	const originalRender = CompactionSummaryMessageComponent.prototype.render;
	prototype[ORIGINAL_RENDER] = originalRender;

	CompactionSummaryMessageComponent.prototype.render = function (width: number): string[] {
		const component = this as unknown as ExpandableComponent;
		const activeController = (CompactionSummaryMessageComponent.prototype as unknown as PatchedPrototype)[
			CONTROLLER
		] as PiUiCustomizationController | undefined;

		const lines = originalRender.call(this, width);
		return activeController?.decorateExpandable(component, lines) ?? lines;
	};
}

function installUserMessageRenderPatch(): void {
	const prototype = UserMessageComponent.prototype as unknown as PatchedPrototype;
	// Replace the wrapper on reload, always wrapping the saved native renderer.
	const originalRender = (prototype[ORIGINAL_RENDER] ?? UserMessageComponent.prototype.render) as
		typeof UserMessageComponent.prototype.render;
	prototype[ORIGINAL_RENDER] = originalRender;

	UserMessageComponent.prototype.render = function (width: number): string[] {
		const maxWidth = Math.min(width, Math.max(40, Math.min(88, Math.floor(width * 0.8))));
		let blockWidth = maxWidth;
		let lines = originalRender.call(this, maxWidth);
		if (!lines.some(isTerminalImageLine)) {
			const padding = (this as unknown as { outputPad: number }).outputPad;
			// Native rows include left padding; discard only the right-side fill when measuring.
			const longestRowWidth = lines.reduce(
				(longest, line) => Math.max(longest, visibleWidth(stripTerminalSequences(line).trimEnd())),
				0,
			);
			blockWidth = Math.min(maxWidth, Math.max(padding * 2 + 1, longestRowWidth + padding));
			// Reuse Pi's wrapping and background painting, including its one top and
			// one bottom padding row. Do not crop ANSI, links, or code indentation.
			if (blockWidth < maxWidth) lines = originalRender.call(this, blockWidth);
		}
		const inset = " ".repeat(width - blockWidth);
		return mapNonImageLines(lines, (line) => {
			// Fullscreen prompt navigation and marker stripping require byte zero.
			const markers = /^(?:\x1b\]133;[ABC](?:\x07|\x1b\\))+/.exec(line)?.[0] ?? "";
			return markers + inset + line.slice(markers.length);
		});
	};
}

export default function piUiCustomization(pi: ExtensionAPI): void {
	const controller = new PiUiCustomizationController();
	installRenderPatch(controller);
	installCompactionRenderPatch(controller);
	installUserMessageRenderPatch();

	let disposeLinkHover: (() => void) | undefined;
	pi.on("session_start", (_event, ctx) => {
		controller.reset(ctx.ui);
		disposeLinkHover?.();
		disposeLinkHover = ctx.mode === "tui" ? installLinkHover() : undefined;
	});
	pi.on("session_shutdown", () => {
		disposeLinkHover?.();
		disposeLinkHover = undefined;
		controller.reset();
	});
}
