---
name: custom-command
description: Create, port, audit, and edit Pi-owned Markdown commands in this repository or Pi-local prompt templates. Use when working with slash commands, command files, prompt-template files, .pi/prompts, package prompt entries, command migration, or prompt-template syntax audits. Covers repository ownership, Pi project/global locations, metadata, skill loading, and argument placeholders.
---

# Custom command

Author Markdown commands as Pi prompt templates. The filename stem becomes the command name.

## Decide scope first

- **This repository's Pi command:** store it at `harness/pi/commands/<name>.md`.
- **Pi project one-off:** store it at `.pi/prompts/<name>.md` in the target project.
- **Pi global one-off:** store it at `~/.pi/agent/prompts/<name>.md`.

If a one-off installation target is ambiguous, ask one concise clarification. Otherwise default command work in this repository to `harness/pi/commands/`.

## Activation

Root `package.json` exposes this repository's commands through `pi.prompts`. Setup can link selected commands into Pi's global prompts directory after confirmation. Edit the repository source, not an installed link.

Pi discovers project one-offs after project trust is granted and global one-offs from its prompts directory. Discovery is flat; use explicit package/settings entries for nested files. Pi extensions are separate resources under `harness/pi/extensions/`. Do not create copied or generated command variants.

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

- Use valid YAML with a non-empty scalar `description`.
- Keep core behavior in the body, including required skill loading.
- Native Pi templates use `description` and optional `argument-hint`. This repository's `extended-commands` extension supports additional routing/skill metadata; do not assume bare Pi applies it.
- Add extension metadata only when requested and supported by the target. Keep optional metadata safely ignorable without losing the body workflow.

## Skills metadata

When a command includes `skill` or `skills` metadata, repeat the requirement explicitly in its body:

```markdown
---
description: "Review changes"
skills:
  - code-review-workflow
---

## Required skills

- `code-review-workflow`

Load and follow the `code-review-workflow` skill before continuing. If it is unavailable, stop and report it.
Review scope: $ARGUMENTS
```

The body instruction remains necessary when metadata is ignored. For repository commands, keep the ordered `Required skills` list identical to the declared skills and resolve each skill locally.

## Arguments

For this repository's templates, use only:

- `$ARGUMENTS` for complete raw/freeform input.
- `$1`, `$2`, and other simple positional arguments with fixed meanings.

Do not use `$@`, `${@:N}`, or `${@:N:L}` in repository commands; `command_valid` enforces this narrower contract. Use `$ARGUMENTS` for a freeform tail and state what happens when required input is missing or ambiguous.

Pi-local one-offs may use native Pi syntax: `$@` for all arguments, `${@:N}` or `${@:N:L}` for slicing, and `${1:-default}` or `${ARGUMENTS:-default}` for defaults. Label the one-off scope explicitly; do not assume the repository extension implements every native form.

## Migration and audit rules

- Choose the Pi source path from the scope above.
- Remove unsupported frontmatter such as `agent`, `subtask`, and legacy model-routing fields when the target is bare Pi; for repository commands, verify any requested extension metadata against `extended-commands` and `command_valid`.
- Replace shell pre-expansion and implicit file inclusion with explicit body instructions to run commands and read files.
- Replace `$@`, slicing, and defaults with `$ARGUMENTS` or fixed positional arguments when migrating into the repository command library.
- Preserve required skill loading and the original task behavior. Avoid copied or generated variants.

## Output when creating a command

Unless writing was requested, return:

1. Scope classification: repository command, Pi project one-off, or Pi global one-off.
2. Canonical path and complete Markdown contents.
3. Pi activation guidance.
4. A validation note covering metadata, skill loading, and argument placeholders.

For returned Markdown containing nested fences, use a four-backtick outer fence.

## Checklist

- [ ] Scope and canonical path are explicit.
- [ ] Filename is flat lowercase kebab-case and ends with `.md`.
- [ ] Frontmatter is valid YAML and body retains core behavior.
- [ ] Skills metadata has a matching explicit body skill-loading instruction.
- [ ] Repository placeholders are `$ARGUMENTS` and/or simple positional arguments; no `$@`, slicing, or defaults.
- [ ] Activation guidance matches the selected Pi scope and preserves existing installs.

## Repository example

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

Pi discovers this template through this repository's package manifest.
