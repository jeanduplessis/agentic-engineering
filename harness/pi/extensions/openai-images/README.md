# openai-images

A Pi extension for generating and editing raster images through the hosted OpenAI Codex `image_generation` tool.

## Requirements

- Pi with `openai-codex` OAuth credentials.
- Run `/login openai-codex` before using the extension.
- Node.js 22.19 or newer.

This extension follows the image implementation in [`pi-better-openai`](https://github.com/mattleong/pi-better-openai). It uses the private Codex Responses endpoint rather than the public OpenAI Images API. That endpoint and its headers are undocumented and may change.

## Usage

The model can call `openai_image` for generation or editing. The interactive command is:

```text
/openai-image <prompt>
```

Tool parameters include:

- `prompt`: generation or editing prompt.
- `action`: `auto`, `generate`, or `edit`.
- `images`: local reference/edit image paths.
- `model`: optional Codex model override.
- `outputFormat`: `png`, `jpeg`, or `webp`.
- `save`: `none`, `project`, `global`, or `custom`.
- `saveDir`: directory used by `save=custom`.

Input images must be inside the current workspace. At most five images are accepted, with a 20 MB per-image and 50 MB combined limit.

## Configuration

Project configuration:

```text
.pi/extensions/openai-images.json
```

Global configuration:

```text
$PI_CODING_AGENT_DIR/extensions/openai-images.json
```

Project values override global values:

```json
{
  "image": {
    "enabled": true,
    "defaultModel": "gpt-5.5",
    "defaultSave": "project",
    "outputFormat": "png",
    "timeoutMs": 180000
  }
}
```

Saved images use these locations:

- `project`: `.pi/generated-images/`
- `global`: `$PI_CODING_AGENT_DIR/generated-images/`
- `custom`: `saveDir` or `PI_IMAGE_SAVE_DIR`
