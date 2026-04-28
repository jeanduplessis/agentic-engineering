---
description: "Flesh out an idea, file, or the current conversation through focused decision questions"
argument-hint: "[file path | idea | current conversation]"
---

Strictly follow `flesh-out` skill on <context-target>$ARGUMENTS</context-target>. 

Interpret the context target as follows:
- If no argument is provided, or the argument says `current conversation`, use the current conversation context.
- If the argument appears to be a file path, read that file first and use it as the starting context.
- Otherwise, treat the argument as the idea to flesh out.
- If the target is ambiguous, ask one concise clarification before starting.
