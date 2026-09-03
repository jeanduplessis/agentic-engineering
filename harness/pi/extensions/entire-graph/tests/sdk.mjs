import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
export let sdkPath;
try {
	sdkPath = require.resolve("@earendil-works/pi-coding-agent");
} catch {
	try {
		const root = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
		sdkPath = require.resolve(join(root, "@earendil-works/pi-coding-agent"));
	} catch { /* Client tests remain usable without Pi. */ }
}

/** Exercise Pi's actual TypeScript loader, without starting a session or calling a model. */
export async function loadGraphExtension(cwd) {
	if (!sdkPath) throw new Error("Install Pi to run the extension-loader checks.");
	const { loadExtensions } = await import(new URL("./core/extensions/loader.js", pathToFileURL(sdkPath)).href);
	return loadExtensions([fileURLToPath(new URL("../index.ts", import.meta.url))], cwd);
}
