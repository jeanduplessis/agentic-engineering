export const TOOL = "code_search";

export const HINT = "\n[code-search] To find where a behavior or concept lives, call code_search with a plain-language description first. Keep rg/grep for exact identifiers, regex, and exhaustive references.";

const SHELL_SEARCH = /(?:^|[\s;&|(`])(?:rg|grep|egrep|fgrep|ag|ack|find|fd|git\s+grep)(?=\s|$)/;
const SHELL_JG = /(?:^|[\s;&|(`])jg(?=\s)/;

interface PolicyApi {
	on(event: string, handler: (event: any) => unknown): unknown;
	getActiveTools(): string[];
}

/**
 * Per-prompt nudge state. The first search-like tool result in a prompt gets one appended hint when
 * code_search is active, has not been used yet, and has not been marked unavailable. Nothing is blocked.
 */
export function createPolicy(pi: PolicyApi) {
	let used = false;
	let hinted = false;
	let unavailable: string | undefined;

	pi.on("before_agent_start", () => { used = false; hinted = false; });

	pi.on("tool_result", (event: { toolName: string; input: Record<string, unknown>; content: unknown[] }) => {
		if (event.toolName === TOOL) return;
		const command = event.toolName === "bash" && typeof event.input?.command === "string" ? event.input.command : undefined;
		if (command !== undefined && SHELL_JG.test(command)) { used = true; return; }
		const search = event.toolName === "grep" || event.toolName === "find" || (command !== undefined && SHELL_SEARCH.test(command));
		if (!search || used || hinted || unavailable || !pi.getActiveTools().includes(TOOL)) return;
		hinted = true;
		return { content: [...event.content, { type: "text", text: HINT }] };
	});

	return {
		markUsed() { used = true; },
		get unavailable() { return unavailable; },
		markUnavailable(reason: string) { unavailable = reason; },
	};
}
