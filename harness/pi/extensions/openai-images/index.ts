import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { resolveConfig } from "./src/config.ts";
import { registerOpenAIImage } from "./src/image.ts";

export default function openaiImages(pi: ExtensionAPI): void {
  registerOpenAIImage(pi, (ctx: ExtensionContext) => resolveConfig(ctx.cwd));
}
