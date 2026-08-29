import type { compact, ExtensionAPI, SessionBeforeCompactEvent } from "@earendil-works/pi-coding-agent";
import { loadConfig } from "./config.ts";

interface Runtime {
	compact: typeof compact;
	agentDir: string;
	configDirName: string;
}

/** Pi skips fromHook file lists during preparation, even when compact() produced them. */
function restoreFileOperations(event: SessionBeforeCompactEvent): void {
	const previous = event.branchEntries.findLast((entry) => entry.type === "compaction");
	if (!previous || !previous.details || typeof previous.details !== "object") return;
	const details = previous.details as Record<string, unknown>;
	// Only adopt our own hook results, not arbitrary extension-owned details.
	if (details.compactionModel !== true) return;
	for (const [key, target] of [
		["readFiles", event.preparation.fileOps.read],
		["modifiedFiles", event.preparation.fileOps.edited],
	] as const) {
		const files = details[key];
		if (Array.isArray(files)) {
			for (const file of files) if (typeof file === "string") target.add(file);
		}
	}
}

export function registerCompactionModel(pi: ExtensionAPI, runtime: Runtime): void {
	pi.on("session_before_compact", async (event, ctx) => {
		if (event.signal.aborted) return { cancel: true };
		// Also preserve tracking when routing is disabled, filtered, or falls back.
		restoreFileOperations(event);

		function warn(message: string): void {
			const text = `[compaction-model] ${message}; using Pi's active model.`;
			if (ctx.hasUI) ctx.ui.notify(text, "warning");
			else console.warn(text);
		}

		try {
			const config = await loadConfig(runtime.agentDir, ctx.cwd, ctx.isProjectTrusted(), runtime.configDirName);
			if (event.signal.aborted) return { cancel: true };
			if (!config || !config.reasons.includes(event.reason)) return;

			const model = ctx.modelRegistry.find(config.provider, config.modelId);
			const provider = ctx.modelRegistry.getProvider(config.provider);
			if (!model || !provider) {
				warn("Configured compaction model or provider is unavailable");
				return;
			}
			const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
			if (event.signal.aborted) return { cancel: true };
			if (!auth.ok) {
				warn("Authentication for the compaction model failed");
				return;
			}

			const result = await runtime.compact(
				event.preparation,
				auth.baseUrl ? { ...model, baseUrl: auth.baseUrl } : model,
				auth.apiKey,
				undefined,
				event.customInstructions,
				event.signal,
				config.thinkingLevel,
				(requestModel, context, options) => {
					// Use the effective provider, including extension-defined stream behavior.
					// compact()'s legacy header type cannot represent deletion (null).
					const stream = provider.streamSimple(requestModel, context, { ...options, headers: auth.headers });
					const getResult = stream.result.bind(stream);
					stream.result = async () => {
						const response = await getResult();
						if (response.stopReason === "aborted" || response.stopReason === "error" ||
							!response.content.some((block) => block.type === "text" && block.text.trim())) {
							throw new Error("Compaction model did not return a usable summary");
						}
						return response;
					};
					return stream;
				},
				auth.env,
			);
			if (event.signal.aborted) return { cancel: true };
			return {
				compaction: {
					...result,
					details: { ...(result.details as object), compactionModel: true },
				},
			};
		} catch {
			if (event.signal.aborted) return { cancel: true };
			// Provider and JSON errors can contain credentials or conversation text.
			warn("Compaction model configuration or request failed");
			return;
		}
	});
}

export default async function compactionModel(pi: ExtensionAPI): Promise<void> {
	const { compact, getAgentDir, CONFIG_DIR_NAME } = await import("@earendil-works/pi-coding-agent");
	registerCompactionModel(pi, { compact, agentDir: getAgentDir(), configDirName: CONFIG_DIR_NAME });
}
