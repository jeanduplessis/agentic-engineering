import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	let stash: string | undefined;

	function updateStatus(ctx: ExtensionContext) {
		ctx.ui.setStatus("prompt-stash", stash === undefined ? undefined : "Prompt stashed");
	}

	function restore(ctx: ExtensionContext) {
		if (stash === undefined) return;
		try {
			if (ctx.ui.getEditorText() !== "") {
				ctx.ui.notify("Prompt stash kept: the editor is not empty. Clear it, then press Cmd+Shift+S to restore.", "warning");
				return;
			}
			ctx.ui.setEditorText(stash);
			// A custom editor may ignore or normalize writes. Keep our copy unless it round-trips.
			if (ctx.ui.getEditorText() !== stash) {
				ctx.ui.notify("Prompt stash kept: the editor did not restore the exact text.", "warning");
				return;
			}
			stash = undefined;
		} catch {
			// Editor errors can include draft text; never pass their details to Pi's error logger.
			ctx.ui.notify("Could not restore the prompt. The stash is still available.", "warning");
		}
		updateStatus(ctx);
	}

	pi.registerShortcut("super+shift+s", {
		description: "Stash the current prompt, or restore it into an empty editor",
		handler: (ctx) => {
			if (!ctx.hasUI || ctx.mode !== "tui") return;
			if (stash !== undefined) {
				restore(ctx);
				return;
			}
			try {
				const text = ctx.ui.getEditorText();
				if (text === "") return;
				// Save before clearing so even a failed editor write cannot lose the draft.
				stash = text;
				ctx.ui.setEditorText("");
				if (ctx.ui.getEditorText() !== "") {
					ctx.ui.notify("Prompt stashed, but the editor could not be cleared.", "warning");
				}
			} catch {
				ctx.ui.notify("Could not update the editor. Any saved prompt remains in the stash.", "warning");
			}
			updateStatus(ctx);
		},
	});

	pi.on("input", (event, ctx) => {
		if (!ctx.hasUI || ctx.mode !== "tui" || event.source !== "interactive") return;
		if (event.text.trim() === "" && !event.images?.length) return;
		// Pi clears its editor before this hook. Restore synchronously, without changing input.
		restore(ctx);
	});

	function reset(_event: unknown, ctx: ExtensionContext) {
		stash = undefined;
		if (ctx.hasUI && ctx.mode === "tui") updateStatus(ctx);
	}
	pi.on("session_start", reset);
	pi.on("session_shutdown", reset);
}
