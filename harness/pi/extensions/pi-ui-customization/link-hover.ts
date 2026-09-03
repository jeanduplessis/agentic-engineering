import { getOsc8LinkAtColumn, TuiAltScreen } from "@earendil-works/pi-tui";

// OSC 22 names are not portable. Only use CSS names on known compatible terminals.
// https://ghostty.org/docs/vt/osc/22
function supportsPointerShape(env: NodeJS.ProcessEnv): boolean {
	const term = env.TERM?.toLowerCase() ?? "";
	if (env.TMUX !== undefined || env.ZELLIJ !== undefined || env.STY !== undefined || /^(tmux|screen)/.test(term)) {
		return false; // Pi intentionally disables unpressed mouse motion in multiplexers.
	}
	return env.TERM_PROGRAM?.toLowerCase() === "ghostty" || /^(xterm-ghostty|xterm-kitty|foot|foot-extra)$/.test(term);
}

type HoverTui = {
	mode: string;
	mouseEnabled: boolean;
	altScreenActive: boolean;
	stopped: boolean;
	selectionPressActive: boolean;
	scrollbarDrag?: unknown;
	previousScreen: string[];
	openUrl?: (url: string) => void;
	terminal: { columns: number; rows: number; write(data: string): void };
};

type HoverState = { x: number; y: number; pointer: boolean };
type PatchState = { controller?: LinkHoverController };
type HoverPrototype = {
	handleViewportInput(this: HoverTui, data: string): unknown;
	doRender(this: HoverTui): void;
	beforeTerminalStop(this: HoverTui, options: unknown): void;
	[key: symbol]: PatchState | undefined;
};

const PATCH_STATE = Symbol.for("pi.pi-ui-customization.link-hover");
const POINTER = "\x1b]22;pointer\x1b\\";
const DEFAULT = "\x1b]22;default\x1b\\";

class LinkHoverController {
	private states = new Map<HoverTui, HoverState>();
	private enabled = supportsPointerShape(process.env);

	afterInput(tui: HoverTui, data: string): void {
		if (data === "\x1b[O") {
			this.clear(tui);
			return;
		}
		if (!this.enabled || tui.mode !== "fullscreen" || !tui.mouseEnabled || !tui.altScreenActive || tui.stopped) return;
		const match = /^\x1b\[<\d+;(\d+);(\d+)[Mm]$/.exec(data);
		if (!match) return;
		const state = this.states.get(tui) ?? { x: 0, y: 0, pointer: false };
		state.x = Number(match[1]) - 1;
		state.y = Number(match[2]) - 1;
		this.states.set(tui, state);
		this.refresh(tui);
	}

	refresh(tui: HoverTui): void {
		const state = this.states.get(tui);
		if (!state) return;
		// Use the same composited screen and column lookup as Pi's click handler.
		// This includes wrapping, scrolling, wide characters, overlays, and tool links.
		const pointer = tui.mode === "fullscreen" && tui.mouseEnabled && tui.altScreenActive && !tui.stopped &&
			!tui.selectionPressActive && !tui.scrollbarDrag && typeof tui.openUrl === "function" &&
			state.x >= 0 && state.x < tui.terminal.columns && state.y >= 0 && state.y < tui.terminal.rows &&
			Array.isArray(tui.previousScreen) &&
			!!getOsc8LinkAtColumn(tui.previousScreen[state.y] ?? "", state.x);
		this.setPointer(tui, state, pointer);
	}

	private setPointer(tui: HoverTui, state: HoverState, pointer: boolean): void {
		if (state.pointer === pointer) return;
		try {
			tui.terminal.write(pointer ? POINTER : DEFAULT);
			state.pointer = pointer;
		} catch {
			// Hover feedback must not interfere with input or terminal teardown.
		}
	}

	clear(tui: HoverTui): void {
		const state = this.states.get(tui);
		if (state) this.setPointer(tui, state, false);
		this.states.delete(tui);
	}

	dispose(): void {
		for (const tui of this.states.keys()) this.clear(tui);
	}
}

export function installLinkHover(): () => void {
	const prototype = TuiAltScreen?.prototype as unknown as HoverPrototype | undefined;
	// These private seams are needed because the viewport consumes mouse input
	// before public input listeners run. Leave unknown SDK versions untouched.
	if (!prototype || typeof prototype.handleViewportInput !== "function" ||
		typeof prototype.doRender !== "function" || typeof prototype.beforeTerminalStop !== "function") return () => {};

	let patch = prototype[PATCH_STATE];
	if (!patch) {
		const binding: PatchState = {};
		const { handleViewportInput, doRender, beforeTerminalStop } = prototype;
		prototype.handleViewportInput = function (data) {
			const result = handleViewportInput.call(this, data);
			binding.controller?.afterInput(this, data);
			return result;
		};
		prototype.doRender = function () {
			doRender.call(this);
			binding.controller?.refresh(this);
		};
		prototype.beforeTerminalStop = function (options) {
			binding.controller?.clear(this);
			beforeTerminalStop.call(this, options);
		};
		prototype[PATCH_STATE] = patch = binding;
	}
	patch.controller?.dispose();
	const controller = new LinkHoverController();
	patch.controller = controller;
	return () => {
		controller.dispose();
		if (patch.controller === controller) patch.controller = undefined;
	};
}
