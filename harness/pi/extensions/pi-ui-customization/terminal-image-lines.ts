const KITTY_GRAPHICS_PREFIX = "\x1b_G";
const ITERM2_IMAGE_PREFIX = "\x1b]1337;File=";

export function isTerminalImageLine(line: string): boolean {
	return line.includes(KITTY_GRAPHICS_PREFIX) || line.includes(ITERM2_IMAGE_PREFIX);
}

export function mapNonImageLines(lines: string[], mapLine: (line: string) => string): string[] {
	return lines.map((line) => (line.length === 0 || isTerminalImageLine(line) ? line : mapLine(line)));
}
