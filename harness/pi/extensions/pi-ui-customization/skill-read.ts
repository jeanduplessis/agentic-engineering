export function isSkillReadPath(path: string): boolean {
	const normalized = path.replaceAll("\\", "/");
	const separator = normalized.lastIndexOf("/");
	const fileName = separator === -1 ? normalized : normalized.slice(separator + 1);
	return fileName === "SKILL.md";
}

export function replaceBackgroundAnsi(line: string, fromAnsi: string, toAnsi: string): string {
	if (!fromAnsi || fromAnsi === toAnsi || !line.includes(fromAnsi)) return line;
	return line.split(fromAnsi).join(toAnsi);
}
