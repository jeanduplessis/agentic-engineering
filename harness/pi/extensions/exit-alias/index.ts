import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function exitAlias(pi: ExtensionAPI) {
	const shutdown = (ctx: { shutdown: () => void }) => {
		ctx.shutdown();
	};

	pi.registerCommand("exit", {
		description: "Exit pi cleanly",
		handler: async (_args, ctx) => {
			shutdown(ctx);
		},
	});

	pi.on("input", async (event, ctx) => {
		if (event.source === "extension") {
			return { action: "continue" };
		}

		if (event.text.trim() === "exit") {
			shutdown(ctx);
			return { action: "handled" };
		}

		return { action: "continue" };
	});
}
