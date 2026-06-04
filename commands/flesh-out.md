---
description: "Flesh out an idea, file, or the current conversation through focused decision questions"
argument-hint: "[file path | idea | current conversation]"
skills:
  - flesh-out
---

## Required skills

- `flesh-out`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Context target: <context-target>$ARGUMENTS</context-target>.

Resolve context target:
- No argument or `current conversation`: use current conversation context.
- Looks like a file path: read it first and use it as starting context.
- Otherwise: treat it as the idea to flesh out.
- Ambiguous: ask one concise clarification before starting.
