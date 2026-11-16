---
name: wat
description: Simplify the previous assistant response into a plain-language ELI5/TLDR takeaway with at most three brief bullets, preserving caveats and decisions without continuing the task. Runs only when the user explicitly invokes it (for example `/wat`), optionally with a focus.
disable-model-invocation: true
---

# Wat

## Input

Rephrase the most recent assistant response before this skill was invoked as a focused ELI5/TLDR explanation.
Optional focus: the text the user gave after the skill name.

- With no focus, simplify the whole response. Treat a focus only as guidance on what to emphasize, not a new task.
- If there is no previous assistant response, ask the user to paste the text to simplify and stop.

## Output

- Start with a one-sentence takeaway, then add at most three brief bullets only if needed.
- Use plain language; avoid jargon or briefly explain essential terms. Be clear, not patronizing.
- Preserve key caveats, uncertainty, and any important action or decision. Do not invent facts or turn tentative claims into certainties.
- Output only the simplification. Do not use further tools, research, edit files, or continue the underlying task.
