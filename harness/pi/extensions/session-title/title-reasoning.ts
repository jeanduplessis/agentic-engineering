const TITLE_REASONING_PREFERENCE = ["minimal", "low", "medium", "high", "xhigh", "max"] as const;

export type TitleReasoningEffort = (typeof TITLE_REASONING_PREFERENCE)[number];

export type TitleReasoningModel = {
	reasoning?: boolean;
	thinkingLevelMap?: Partial<Record<"off" | TitleReasoningEffort, string | null>>;
};

/**
 * Pick a provider-accepted reasoning effort for a one-shot title call.
 * Omitting effort makes Pi send `none` for reasoning models; some OpenAI
 * models reject that value.
 */
export function titleReasoningEffort(model: TitleReasoningModel): TitleReasoningEffort | undefined {
	if (!model.reasoning) return undefined;
	const map = model.thinkingLevelMap;
	for (const level of TITLE_REASONING_PREFERENCE) {
		if (map?.[level] === null) continue;
		if ((level === "xhigh" || level === "max") && map?.[level] === undefined) continue;
		return level;
	}
	return undefined;
}
