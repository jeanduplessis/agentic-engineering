export type ToolCollapseInput = {
	toolName: string;
	expanded: boolean;
	isPartial: boolean;
	isError?: boolean;
	hasExpandHint: boolean;
};

export type ToolCollapseDecision = {
	clickable: boolean;
	compact: boolean;
};

export function decideToolCollapse(input: ToolCollapseInput): ToolCollapseDecision {
	const isSubagent = input.toolName === "subagent";
	const isCompletedRead =
		input.toolName === "read" && !input.isPartial && input.isError === false;
	// Pi's edit renderer ignores expanded and always paints the full diff, so
	// treat edit rows as clickable and compact them while collapsed.
	const isEdit = input.toolName === "edit";
	const clickable = isSubagent || input.hasExpandHint || isCompletedRead || isEdit;
	const compact = !input.expanded && (input.hasExpandHint || isEdit);
	return { clickable, compact };
}
