export type ToolCollapseInput = {
	expanded: boolean;
};

export type ToolCollapseDecision = {
	clickable: boolean;
	compact: boolean;
};

export function decideToolCollapse(input: ToolCollapseInput): ToolCollapseDecision {
	return {
		clickable: true,
		compact: !input.expanded,
	};
}
