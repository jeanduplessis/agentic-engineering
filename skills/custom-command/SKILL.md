---
name: custom-command
description: Create, port, audit, and edit shared Pi/OpenCode Markdown commands or harness-local prompt templates. Use when working with slash commands, command files, prompt-template files, shared command sources, .pi/prompts, .opencode/commands, package prompt entries, command migration, or prompt-template syntax audits. Covers canonical ownership, symlink activation, portable metadata, skill loading, and shared argument placeholders.
---

# Custom Command

Author Markdown commands, including Pi prompt templates, for Pi, OpenCode, or both. Filename stem becomes command name.

## Decide scope first

Classify command before choosing syntax or location:

- **Shared repo command:** intended to behave the same in Pi and OpenCode. Keep one canonical source.
  In this repo, default canonical source is `commands/<name>.md`.
- **Harness-local one-off:** intentionally uses one harness's behavior or belongs only to one user/project setup. Store it in that harness's native prompt directory; do not promote it to this repo's shared `commands/` library.

If user asks to install a harness-local file but does not identify Pi or OpenCode, ask one concise clarification. Otherwise default this repo command work to a shared source under `commands/`.

## Canonical source and activation

For shared commands:

1. Edit one canonical Markdown source, normally this repo's `commands/<name>.md`.
2. Expose that same source to each harness through package discovery or symlinks.
3. Never maintain generated, built, copied, or hand-synchronized harness variants.

This repo's root Pi package manifest already exposes `commands/*.md`. Activate a shared source elsewhere with symlinks when needed:

- Pi project: `.pi/prompts/<name>.md`
- Pi global: `~/.pi/agent/prompts/<name>.md`
- OpenCode project: `.opencode/commands/<name>.md`
- OpenCode global: `~/.config/opencode/commands/<name>.md`

Use relative symlinks for project-local activation when practical. Before proposing a symlink, verify target harness discovers that directory and does not require a regular file.

Harness-local one-offs may live directly in native locations above. Pi also supports package `pi.prompts` entries and `pi --prompt-template <path>`.

## Shared command shape

Use a flat lowercase kebab-case `.md` filename and behavior-complete body:

```markdown
---
description: "Short description shown in command autocomplete"
argument-hint: "[optional input]"
---

Perform the requested task.
Raw user input: $ARGUMENTS
```

Rules:

- Use valid scalar YAML. `description` is portable baseline metadata.
- `argument-hint` is harmless UI metadata only when every target harness accepts or safely ignores it.
- Shared body must preserve baseline behavior if any harness ignores nonessential metadata.
- Do not put behavior-changing routing metadata such as `agent`, `model`, or `subtask` in shared sources.
- Additional harness-specific metadata is allowed only after verifying other target harnesses parse and safely ignore it. Never rely on it for core behavior.

## Skills metadata

`skill` or `skills` metadata may help a supporting harness, but is not portable command behavior. Whenever a shared command includes skills metadata, repeat the requirement explicitly in body:

```markdown
---
description: "Review changes"
skills:
  - code-review-workflow
---

Load and follow the `code-review-workflow` skill before reviewing changes.
Review scope: $ARGUMENTS
```

Body instruction is required even when current activation injects skill automatically. Command must remain understandable and behavior-complete when metadata is ignored.

## Shared arguments

Use only shared placeholder intersection in canonical shared sources:

- `$ARGUMENTS` for complete raw/freeform input.
- `$1`, `$2`, and other simple positional arguments when each position has a fixed meaning.

Do not use `$@`, `${@:N}`, or `${@:N:L}` in shared sources. Do not use slicing to represent a freeform tail. Instead expose `$ARGUMENTS` and tell agent how to interpret first fixed value and remaining text, or redesign contract around bounded simple positions.

State missing or ambiguous required-argument behavior in body: ask one concise clarification and stop.

Harness-local one-offs may use native placeholders when user intentionally accepts lock-in.

## Shared workflow

- Classify command as shared repo command or harness-local one-off.
- Identify name, purpose, canonical source, activation paths, and argument contract.
- Choose `$ARGUMENTS` by default or simple positional placeholders for fixed meanings.
- Keep shared behavior independent of harness-specific metadata.
- Add explicit body skill loading for every `skill` or `skills` metadata entry.
- Use normal agent tools, not pre-expanded shell output or implicit file inclusion.
- Validate filename, frontmatter, placeholders, baseline behavior, and symlink/package activation.

## Migration and audit rules

When making a command shared between Pi and OpenCode: Remove unsupported frontmatter such as `agent`, `subtask`, and legacy model-routing fields when they affect behavior.

- Move canonical ownership to `commands/<name>.md` in this repo unless user requests another shared source.
- Remove behavior-changing harness metadata such as `agent`, `model`, and `subtask`; express required behavior in body.
- Keep harmless harness metadata only when ignored safely and body retains baseline behavior.
- Add explicit body skill loading whenever `skill` or `skills` metadata remains.
- Replace shell interpolation such as ``!`npm test` `` with instructions to run command.
- Replace implicit file inclusion such as `@src/file.ts` with instructions to read supplied path.
- Replace `$@` and argument slicing with `$ARGUMENTS` or simple fixed positional arguments.
- Replace copied/generated harness variants with symlinks to canonical source.

For harness-local one-offs, audit against target harness's native contract instead; label lock-in clearly and do not claim source is shared.

## Output when creating command

Unless user explicitly asks to write/install files, return:

1. Scope classification: shared repo command or named harness-local one-off.
2. Canonical filename/path and complete Markdown contents.
3. Activation paths; recommend symlinks for shared sources.
4. Validation note covering metadata, skill loading, placeholders, and migrated syntax.

If writing files, create only requested canonical or harness-local source. Do not create generated harness variants. For returned Markdown containing nested fences, use four-backtick outer fence.

## Checklist

- [ ] Scope is explicitly shared or harness-local.
- [ ] Shared repo source defaults to `commands/<name>.md` in this repo.
- [ ] Filename is flat lowercase kebab-case and ends with `.md`.
- [ ] Frontmatter is valid YAML; shared baseline does not depend on harness-specific metadata.
- [ ] Skills metadata has matching explicit body skill-loading instruction.
- [ ] Shared placeholders are `$ARGUMENTS` and/or simple positional arguments; no `$@` or slicing.
- [ ] Missing or ambiguous required arguments have concise clarification path.
- [ ] Body does not rely on shell pre-expansion or implicit file inclusion.
- [ ] Shared activation uses package discovery or symlinks, never generated variants.

## Shared example

Canonical path: `commands/pr-review.md`

```markdown
---
description: "Review a pull request"
argument-hint: "<PR URL> [extra instructions]"
---

Review pull request at $1 for bugs, missing tests, security risks, and maintainability concerns.
Interpret remaining text from raw input as optional extra instructions: $ARGUMENTS

If pull request URL is missing or ambiguous, ask one concise clarification and stop.
```

Activate same source for OpenCode with symlink at `.opencode/commands/pr-review.md`; Pi discovers it through this repo's package manifest.
