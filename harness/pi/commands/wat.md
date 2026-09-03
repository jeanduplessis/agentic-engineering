---
description: "Simplify the last assistant response into a plain-language takeaway"
argument-hint: "[optional focus]"
---

Rephrase the most recent assistant response as a focused ELI5/TLDR explanation.
Optional focus: $ARGUMENTS

- With no focus, simplify the whole response. Treat a focus only as guidance on what to emphasize, not a new task.
- If there is no previous assistant response, ask the user to paste the text to simplify and stop.
- Start with a one-sentence takeaway, then add at most three brief bullets only if needed.
- Use plain language; avoid jargon or briefly explain essential terms. Be clear, not patronizing.
- Preserve key caveats, uncertainty, and any important action or decision. Do not invent facts or turn tentative claims into certainties.
- Output only the simplification. Do not use tools, research, edit files, or continue the underlying task.
