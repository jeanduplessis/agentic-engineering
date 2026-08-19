import type {
	ExtensionAPI,
	ExtensionContext,
	InputEvent,
} from "@earendil-works/pi-coding-agent";
import type { AssistantMessage, ImageContent, Model } from "@earendil-works/pi-ai";
import { Box, Text } from "@earendil-works/pi-tui";

const OPTIONS = {
	/** Do not interrupt smaller prompts, even when their cache may have expired. */
	minContextTokens: 50_000,
	/** Typical upper end of OpenAI's legacy in-memory inactivity window. */
	legacyOpenAiTtlMs: 10 * 60 * 1000,
	/** Minimum cache lifetime for GPT-5.6 and later model families. */
	modernOpenAiMinimumTtlMs: 30 * 60 * 1000,
	/** Default short-lived prompt-cache TTL for other providers. */
	shortTtlMs: 5 * 60 * 1000,
	/** Extended Anthropic cache TTL when PI_CACHE_RETENTION=long. */
	longAnthropicTtlMs: 60 * 60 * 1000,
	/** Maximum extended OpenAI retention for models before GPT-5.6. */
	longOpenAiTtlMs: 24 * 60 * 60 * 1000,
} as const;

const CHOICE_COMPACT = "Compact and continue";
const CHOICE_NEW_CONTEXT = "Start a new context window";
const CHOICE_SEND = "Send anyway";
const CHOICE_CANCEL = "Cancel and restore prompt";
const NEW_CONTEXT_COMMAND = "cache-miss-new-context";
const CACHE_MISS_ENTRY = "cache-miss-warning";
const WARNING_BG = { r: 77, g: 56, b: 18 };
const WARNING_BG_256 = 58;

type CacheMissWarningData = {
	summary: string;
	reasons: string[];
};

function applyWarningBg(theme: { getColorMode(): string }, text: string): string {
	if (theme.getColorMode() === "truecolor") {
		return `\x1b[48;2;${WARNING_BG.r};${WARNING_BG.g};${WARNING_BG.b}m${text}\x1b[49m`;
	}
	return `\x1b[48;5;${WARNING_BG_256}m${text}\x1b[49m`;
}

type GateReason = {
	message: string;
	idleMs?: number;
};

function getLastAssistant(ctx: ExtensionContext): AssistantMessage | undefined {
	for (const entry of ctx.sessionManager.getBranch().toReversed()) {
		if (entry.type === "compaction" || entry.type === "branch_summary") return undefined;
		if (entry.type === "message" && entry.message.role === "assistant") {
			const message = entry.message;
			if (message.usage.totalTokens > 0) return message;
		}
	}
	return undefined;
}

function modelKey(model: Pick<Model<any>, "provider" | "id">): string {
	return `${model.provider}/${model.id}`;
}

function assistantModelKey(message: AssistantMessage): string {
	return `${message.provider}/${message.model}`;
}

function isAnthropicFamily(model: Model<any>): boolean {
	return `${model.provider}/${model.id}/${model.api}`.toLowerCase().match(/anthropic|claude/) !== null;
}

function isOpenAiFamily(model: Model<any>): boolean {
	return `${model.provider}/${model.id}/${model.api}`.toLowerCase().match(/openai|gpt|codex/) !== null;
}

function isGpt56OrLater(model: Model<any>): boolean {
	const match = model.id.toLowerCase().match(/(?:^|[^a-z0-9])gpt-(\d+)(?:\.(\d+))?/);
	if (!match) return false;
	const major = Number(match[1]);
	const minor = Number(match[2] ?? 0);
	return major > 5 || (major === 5 && minor >= 6);
}

function cacheTtlMs(model: Model<any>): number {
	if (isOpenAiFamily(model)) {
		// GPT-5.6+ uses prompt_cache_options.ttl rather than the legacy
		// retention policy. Its default/only value guarantees at least 30m,
		// regardless of PI_CACHE_RETENTION, and the cache may live longer.
		if (isGpt56OrLater(model)) return OPTIONS.modernOpenAiMinimumTtlMs;
		if (process.env.PI_CACHE_RETENTION === "long") return OPTIONS.longOpenAiTtlMs;
		return OPTIONS.legacyOpenAiTtlMs;
	}

	if (process.env.PI_CACHE_RETENTION !== "long") return OPTIONS.shortTtlMs;
	if (isAnthropicFamily(model)) return OPTIONS.longAnthropicTtlMs;
	// Use the more conservative supported long-cache duration for unknown providers.
	return OPTIONS.longAnthropicTtlMs;
}

function formatDuration(ms: number): string {
	const minutes = Math.max(1, Math.round(ms / 60_000));
	if (minutes < 60) return `${minutes}m`;
	const hours = Math.round(minutes / 60);
	return `${hours}h`;
}

function formatTokens(tokens: number): string {
	if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}m`;
	if (tokens >= 1_000) return `${Math.round(tokens / 1_000)}k`;
	return String(tokens);
}

function estimateAvoidableCost(tokens: number, model: Model<any>): number | undefined {
	const inputRate = model.cost?.input;
	const cacheReadRate = model.cost?.cacheRead;
	if (typeof inputRate !== "number" || typeof cacheReadRate !== "number") return undefined;
	return (tokens / 1_000_000) * Math.max(0, inputRate - cacheReadRate);
}

type PromptContent = Array<{ type: "text"; text: string } | ImageContent>;

type PendingNewContext = {
	text: string;
	images: ImageContent[];
	content: PromptContent;
};

function promptContent(text: string, images?: ImageContent[]): PromptContent {
	return [{ type: "text", text }, ...(images ?? [])];
}

function restorePromptText(text: string, images: ImageContent[] | undefined, ctx: ExtensionContext): void {
	ctx.ui.setEditorText(text);
	if (images?.length) {
		ctx.ui.notify("Prompt restored. Reattach its images before sending.", "warning");
	}
}

function restorePrompt(event: InputEvent, ctx: ExtensionContext): void {
	restorePromptText(event.text, event.images, ctx);
}

function buildReasons(last: AssistantMessage, model: Model<any>): GateReason[] {
	const reasons: GateReason[] = [];
	const idleMs = Math.max(0, Date.now() - last.timestamp);
	const ttlMs = cacheTtlMs(model);

	if (idleMs >= ttlMs) {
		const thresholdDescription = isOpenAiFamily(model) && isGpt56OrLater(model)
			? `${formatDuration(ttlMs)} guaranteed minimum cache lifetime (the cache may persist longer)`
			: `assumed ${formatDuration(ttlMs)} cache window`;
		reasons.push({
			message: `${formatDuration(idleMs)} idle exceeds the ${thresholdDescription}`,
			idleMs,
		});
	}
	if (assistantModelKey(last) !== modelKey(model)) {
		reasons.push({ message: `model changed from ${assistantModelKey(last)} to ${modelKey(model)}` });
	}

	return reasons;
}

function continueAfterCompaction(event: InputEvent, pi: ExtensionAPI, ctx: ExtensionContext): void {
	const startsWithSlash = event.text.trimStart().startsWith("/");
	if (startsWithSlash) {
		// sendUserMessage intentionally skips skill/template expansion. Restore slash
		// input so Pi can process it through its normal interactive submission path.
		restorePrompt(event, ctx);
		ctx.ui.notify("Context compacted. Press Enter to continue with the restored command.", "info");
		return;
	}

	pi.sendUserMessage(promptContent(event.text, event.images));
}

export default function cacheMissGate(pi: ExtensionAPI) {
	let pendingNewContext: PendingNewContext | undefined;

	pi.registerEntryRenderer<CacheMissWarningData>(CACHE_MISS_ENTRY, (entry, _options, theme) => {
		const data = entry.data ?? { summary: "A previously cached request may miss.", reasons: [] };
		const box = new Box(1, 1, (text) => applyWarningBg(theme, text));
		const lines = [
			theme.fg("warning", `${theme.bold("Warning:")} ${data.summary}`),
			...data.reasons.map((reason) => theme.fg("warning", `• ${reason}`)),
		];
		box.addChild(new Text(lines.join("\n"), 0, 0));
		return box;
	});

	// Session replacement is available only from command contexts. Stage the
	// prompt as a command so the user can submit it after choosing this action.
	pi.registerCommand(NEW_CONTEXT_COMMAND, {
		description: "Start a new context window with the staged prompt",
		handler: async (_args, ctx) => {
			const pending = pendingNewContext;
			if (!pending) {
				ctx.ui.notify("No prompt is staged for a new context window.", "warning");
				return;
			}
			pendingNewContext = undefined;

			const parentSession = ctx.sessionManager.getSessionFile();
			const result = await ctx.newSession({
				...(parentSession ? { parentSession } : {}),
				withSession: async (replacementCtx) => {
					if (pending.text.trimStart().startsWith("/")) {
						restorePromptText(pending.text, pending.images, replacementCtx);
						replacementCtx.ui.notify(
							"New context window started. Press Enter to continue with the restored command.",
							"info",
						);
						return;
					}

					try {
						await replacementCtx.sendUserMessage(pending.content);
					} catch (error) {
						restorePromptText(pending.text, pending.images, replacementCtx);
						replacementCtx.ui.notify(
							`Could not send the prompt in the new context: ${error instanceof Error ? error.message : String(error)}`,
							"error",
						);
					}
				},
			});

			if (result.cancelled) {
				restorePromptText(pending.text, pending.images, ctx);
				ctx.ui.notify("New context window cancelled.", "info");
			}
		},
	});

	pi.on("input", async (event, ctx) => {
		// Extension-generated messages are used to resume after successful compaction.
		// Mid-stream input is already committed to the active agent run.
		if (event.source === "extension" || event.streamingBehavior) {
			return { action: "continue" };
		}

		// Let exit-alias extensions handle their bare keyword without showing a
		// cache-miss prompt first.
		if (event.text.trim() === "exit") {
			return { action: "continue" };
		}

		if (pendingNewContext && event.text.trim() !== `/${NEW_CONTEXT_COMMAND}`) {
			pendingNewContext = undefined;
		}

		const usage = ctx.getContextUsage();
		if (!usage || usage.tokens === null || usage.tokens < OPTIONS.minContextTokens || !ctx.model) {
			return { action: "continue" };
		}

		const last = getLastAssistant(ctx);
		if (!last) return { action: "continue" };

		// Only gate providers that have demonstrated prompt-cache accounting. A
		// provider reporting no cache data cannot support a useful miss prediction.
		if (last.usage.cacheRead + last.usage.cacheWrite === 0) {
			return { action: "continue" };
		}

		const reasons = buildReasons(last, ctx.model);
		if (reasons.length === 0) return { action: "continue" };

		// Print and JSON modes cannot ask the user, so fail open.
		if (!ctx.hasUI) return { action: "continue" };

		const previousPromptTokens =
			last.usage.input + last.usage.cacheRead + last.usage.cacheWrite;
		const exposedTokens = Math.min(usage.tokens, previousPromptTokens);
		const estimatedCost = estimateAvoidableCost(exposedTokens, ctx.model);
		const estimate = estimatedCost && estimatedCost >= 0.01
			? ` (~$${estimatedCost.toFixed(2)} versus a cache read)`
			: "";
		pi.appendEntry<CacheMissWarningData>(CACHE_MISS_ENTRY, {
			summary: `A request with about ${formatTokens(exposedTokens)} previously cached tokens may miss${estimate}.`,
			reasons: reasons.map((reason) => reason.message),
		});
		const choice = await ctx.ui.select("Possible prompt-cache miss — choose how to proceed", [
			CHOICE_COMPACT,
			CHOICE_NEW_CONTEXT,
			CHOICE_SEND,
			CHOICE_CANCEL,
		]);

		if (choice === CHOICE_SEND) return { action: "continue" };

		if (choice === CHOICE_NEW_CONTEXT) {
			pendingNewContext = {
				text: event.text,
				images: [...(event.images ?? [])],
				content: promptContent(event.text, event.images),
			};
			ctx.ui.setEditorText(`/${NEW_CONTEXT_COMMAND}`);
			ctx.ui.notify("Press Enter to start a new context window with this prompt.", "info");
			return { action: "handled" };
		}

		if (choice === CHOICE_COMPACT) {
			ctx.ui.notify("Compacting context before sending…", "info");
			ctx.compact({
				onComplete: () => continueAfterCompaction(event, pi, ctx),
				onError: (error) => {
					restorePrompt(event, ctx);
					ctx.ui.notify(`Compaction failed: ${error.message}`, "error");
				},
			});
			return { action: "handled" };
		}

		restorePrompt(event, ctx);
		return { action: "handled" };
	});
}
