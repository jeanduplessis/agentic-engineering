---
description: "Flesh out an idea, file, or the current conversation through focused decision questions"
argument-hint: "[file path | idea | current conversation]"
---

Strictly follow `flesh-out` skill for <context-target>$ARGUMENTS</context-target>.

Resolve context target:
- No argument or `current conversation`: use current conversation context.
- Looks like a file path: read it first and use it as starting context.
- Otherwise: treat it as the idea to flesh out.
- Ambiguous: ask one concise clarification before starting.
