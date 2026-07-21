---
name: custom-command
description: Create, port, audit, and edit Pi-owned Markdown commands in this repository or harness-local prompt templates. Use when working with slash commands, command files, prompt-template files, .pi/prompts, .opencode/commands, package prompt entries, command migration, or prompt-template syntax audits. Covers repository ownership, native harness locations, metadata, skill loading, and argument placeholders.
---

# Custom command

Author Markdown commands, including Pi prompt templates, for Pi, OpenCode, or both. Filename stem becomes the command name. This repository owns Pi templates only; it is not a shared Pi/OpenCode command source.

## Decide scope first

- **This repository's Pi command:** store it at `harness/pi/commands/<name>.md`.
- **Harness-local one-off:** store it in the target harness's native command directory.
- **Downstream shared command:** a target repository may choose one source for Pi and OpenCode. This repository does not supply or activate that source.

If a harness-local installation target is ambiguous, ask one concise clarification. Otherwise default command work in this repository to `harness/pi/commands/`.

## This repository's Pi commands

1. Edit `harness/pi/commands/<name>.md`.
2. Root `package.json` exposes these files through `pi.prompts`.
3. Do not claim that this file activates OpenCode or Kilo commands.

Pi extensions are separate resources under `harness/pi/extensions/`. Do not create copied or generated command variants.

## Harness-local and downstream commands

For arbitrary harness-local commands, use the target harness's documented native location:

- Pi project: `.pi/prompts/<name>.md`
- Pi global: `~/.pi/agent/prompts/<name>.md`
- OpenCode project: `.opencode/commands/<name>.md`
- OpenCode global: `~/.config/opencode/commands/<name>.md`

For a downstream command shared by Pi and OpenCode, choose and document its canonical source in that downstream repository. Verify each target's discovery and metadata behavior before recommending symlinks. Do not infer a shared contract from one harness accepting syntax.

## Command shape

Use a flat lowercase kebab-case `.md` filename and a behavior-complete body:

```markdown
---
description: "Short description shown in command autocomplete"
argument-hint: "[optional input]"
---

Perform the requested task.
Raw user input: $ARGUMENTS
```

- Use valid scalar YAML.
- Keep routing metadata compatible with the intended harness. Do not describe Pi-only metadata as portable.
- Keep core behavior in the body, including required skill loading.
- For a downstream shared command, keep nonessential metadata safely ignorable by every target.

## Skills metadata

When a command includes `skill` or `skills` metadata, repeat the requirement explicitly in its body:

```markdown
---
description: "Review changes"
skills:
  - code-review-workflow
---

Load and follow the `code-review-workflow` skill before reviewing changes.
Review scope: $ARGUMENTS
```

The body instruction remains necessary when metadata is ignored.

## Arguments

For this repository's Pi templates, use `$ARGUMENTS` or simple positional placeholders. For a downstream shared command, limit its source to placeholders supported by every target:

- `$ARGUMENTS` for complete raw/freeform input.
- `$1`, `$2`, and other simple positional arguments with fixed meanings.

Do not use `$@`, `${@:N}`, or `${@:N:L}` in a downstream shared source. Use `$ARGUMENTS` for a freeform tail and state what happens when required input is missing or ambiguous.

Harness-local commands may use native syntax when lock-in is explicit.

## Migration and audit rules

For a downstream Pi/OpenCode shared command:

- choose the downstream repository's canonical source; do not use this repository's Pi directory unless the command is Pi-only;
- Remove unsupported frontmatter such as `agent`, `subtask`, and legacy model-routing fields when they affect the downstream shared behavior.
- remove metadata that changes behavior in only one target;
- replace shell pre-expansion and implicit file inclusion with body instructions;
- replace `$@` and slicing with `$ARGUMENTS` or fixed positional arguments;
- avoid copied or generated variants.

## Output when creating a command

Unless writing was requested, return:

1. Scope classification: this repository's Pi command, downstream shared command, or named harness-local one-off.
2. Canonical path and complete Markdown contents.
3. Activation guidance for the actual target harness.
4. A validation note covering metadata, skill loading, and argument placeholders.

For returned Markdown containing nested fences, use a four-backtick outer fence.

## Checklist

- [ ] Scope is explicitly Pi-owned, downstream shared, or harness-local.
- [ ] This repository's Pi source is `harness/pi/commands/<name>.md`.
- [ ] Filename is flat lowercase kebab-case and ends with `.md`.
- [ ] Frontmatter is valid YAML and body retains core behavior.
- [ ] Skills metadata has matching explicit body skill-loading instruction.
- [ ] Downstream shared placeholders are `$ARGUMENTS` and/or simple positional arguments; no `$@` or slicing.
- [ ] Activation guidance does not claim this repository activates OpenCode/Kilo commands.

## This repository's Pi example

Canonical path: `harness/pi/commands/pr-review.md`

```markdown
---
description: "Review a pull request"
argument-hint: "<PR URL> [extra instructions]"
---

Review pull request at $1 for bugs, missing tests, security risks, and maintainability concerns.
Interpret remaining text from raw input as optional extra instructions: $ARGUMENTS

If pull request URL is missing or ambiguous, ask one concise clarification and stop.
```

Pi discovers this template through this repository's package manifest. An OpenCode-only or downstream shared command belongs in the relevant target repository or OpenCode-native command directory.
