---
name: custom-command
description: Create, port, audit, and edit Pi Markdown prompt templates and slash commands. Use when the user asks for a Pi prompt template, slash command, command file, prompt-template file, .pi/prompts file, global Pi prompt, package prompt entry, command migration, or prompt-template syntax audit. Focuses on Pi locations, frontmatter, argument placeholders, package discovery, and legacy syntax cleanup.
---

# Custom Command

Author Pi prompt templates: Markdown snippets invoked as slash commands. Filename stem becomes the slash command name.

## Goal

Produce Pi-native prompt templates for one of these locations:

- Global: `~/.pi/agent/prompts/<name>.md`
- Project: `.pi/prompts/<name>.md`
- Package conventional directory: `prompts/<name>.md`
- Package manifest entry: `package.json` `pi.prompts`
- This repo: `commands/<name>.md`, exposed by root `package.json` `pi.prompts`
- CLI one-off: `pi --prompt-template <path>`

If the user wants a file installed and no target is specified, ask one concise clarification. For this repo, default to `commands/<name>.md`.

## Pi template shape

```markdown
---
description: "Short description shown in Pi autocomplete"
argument-hint: "[optional args]"
---

Prompt body. User input: $ARGUMENTS
```

Rules:

- Use flat lowercase kebab-case filenames with `.md`.
- Keep frontmatter scalar YAML.
- `description` is optional in Pi but required for clean repo templates.
- `argument-hint` is optional autocomplete help; use `<required>` and `[optional]` notation.
- The body is the prompt Pi inserts/executes.

## Arguments

Pi prompt templates support:

- `$1`, `$2`, ... positional arguments.
- `$@` or `$ARGUMENTS` for all args joined.
- `${@:N}` for args from position `N` onward, 1-indexed.
- `${@:N:L}` for `L` args starting at position `N`.

Guidance:

- Prefer `$ARGUMENTS` for freeform text, paths with spaces, or arbitrary tails.
- Use `$1` only when the first argument has a fixed meaning.
- Use `${@:2}` when `$1` is a required target and the rest are freeform notes.
- State ambiguity behavior in the prompt: missing/ambiguous required args should trigger one concise clarification and stop.

## Pi-native workflow

1. Identify command name, purpose, target location, and argument contract.
2. Choose placeholders: `$ARGUMENTS` by default; `$1`/slicing only for clear fixed positions.
3. Write valid scalar frontmatter with `description` and optional `argument-hint`.
4. Make the body executable by a Pi agent using normal tools; do not depend on pre-expanded shell output or file inclusion.
5. Validate filename, frontmatter, placeholders, and install/discovery path.
6. If writing the file, create/update the requested path and summarize it.

## Legacy migration notes

When porting old command files to Pi:

- Remove unsupported frontmatter such as `agent`, `subtask`, and legacy model-routing fields unless a Pi-specific extension explicitly owns them.
- Replace shell interpolation like ``!`npm test` `` with instructions to run the command.
- Replace template file inclusion like `@src/file.ts` with instructions to read the supplied path.
- Keep only Pi-supported frontmatter for normal prompt templates: `description` and `argument-hint`.
- Preserve behavior by making implicit pre-expanded context explicit in the prompt body.

## File and naming rules

- Use `.md` extension.
- Use flat lowercase kebab-case names: `fix-tests.md`, `pr-review.md`.
- Avoid names that collide with Pi built-in slash commands unless the user intentionally overrides them.
- Pi default prompt discovery is non-recursive. Use explicit settings/package entries for nested paths.

## Output format when creating a template

Unless the user explicitly asks you to write or install files, return:

1. Recommended filename.
2. Complete Markdown contents.
3. Pi install/discovery path(s).
4. Short validation note naming placeholders and any migrated legacy syntax.

If writing files directly, create the requested file(s), then summarize written paths.
For returned Markdown commands with fenced code blocks, use a four-backtick outer fence so nested triple-backtick examples remain valid Markdown.

## Pi prompt-template checklist

- [ ] Filename is flat lowercase kebab-case and ends with `.md`.
- [ ] Frontmatter is valid scalar YAML.
- [ ] Frontmatter uses only `description` and optional `argument-hint` for normal Pi templates.
- [ ] The argument contract uses `$ARGUMENTS`, `$@`, `$1`, or Pi slicing deliberately.
- [ ] Missing/ambiguous required arguments have a concise clarification path.
- [ ] The body does not rely on legacy shell interpolation or template file inclusion.
- [ ] The template is discoverable through a Pi prompt directory, package `pi.prompts`, settings, or CLI flag.

## Examples

### Freeform command

Filename: `review-changes.md`

```markdown
---
description: "Review code changes with emphasis on correctness and maintainability"
argument-hint: "[scope or instructions]"
---

Review the requested changes.

Scope or instructions: $ARGUMENTS

If no scope is provided, inspect the current working tree changes.
Focus on bugs, missing tests, security risks, and maintainability concerns.
```

### Fixed first argument plus freeform tail

Filename: `component.md`

```markdown
---
description: "Create a React component"
argument-hint: "<name> [features...]"
---

Create a React component named $1.

Requested features: ${@:2}

If the component name is missing or ambiguous, ask one concise clarification and stop.
```

### Legacy shell interpolation migrated to Pi instructions

Before:

```markdown
Here are current test results:
!`npm test`
```

After:

```markdown
Run `npm test`, summarize failures, make the smallest safe fix, and rerun the relevant tests.
User focus: $ARGUMENTS
```
