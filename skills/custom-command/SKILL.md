---
name: custom-command
description: Helps create Markdown slash commands/prompt templates that work compatibly in both OpenCode and Pi. Use this skill whenever the user asks to create, port, audit, or edit a custom command, prompt template, slash command, .opencode/commands file, .pi/prompts file, or one command file intended to run in both agents. It focuses on the shared safe subset and flags agent-specific features that would change core behavior.
---

# Custom Command

OpenCode and Pi store commands differently but share a basic Markdown shape. Use the shared subset to preserve core behavior in both.
Agent-specific features are acceptable only when they degrade gracefully and do not affect the command's essential result.

## Goal

Produce a command file copyable into both ecosystems:

- OpenCode global: `~/.config/opencode/commands/<name>.md`
- OpenCode project: `.opencode/commands/<name>.md`
- Pi global: `~/.pi/agent/prompts/<name>.md`
- Pi project: `.pi/prompts/<name>.md`

If the user wants a file installed, ask which target(s) to write unless already specified.

## Compatibility contract

Use this portable Markdown shape:

```markdown
---
description: Short description shown in command autocomplete
---

Prompt body here. Use $ARGUMENTS for user-provided input.
```

Shared behavior:

- Filename without `.md` becomes the slash command name.
- YAML frontmatter is delimited by `---`.
- Both support `description`.
- The body becomes the prompt/template.
- Both support `$ARGUMENTS`; it is the safest argument placeholder.

## Safe default workflow

1. Identify command name, purpose, and whether it needs arguments.
2. Use only shared behavior unless there is a clear reason not to.
3. Prefer `$ARGUMENTS` for all user input.
4. Avoid automatic shell output and file inclusion in shared templates.
5. Make the prompt explicit enough that either agent can perform the same work with its normal tools.
6. Validate strict YAML frontmatter.
7. Provide install/copy paths for both agents.

## Portable argument rules

Prefer `$ARGUMENTS`:

```markdown
Analyze this target and report risks: $ARGUMENTS
```

Use numbered placeholders only when the command has fixed, simple, usually single-token arguments and extra words should not be accepted.
Pi treats `$1` as the first parsed argument. OpenCode's final numbered placeholder may absorb the remaining argument string.
If a command takes freeform text, filenames with spaces, or an arbitrary tail, use `$ARGUMENTS` instead.

Avoid these in shared commands:

- `$@` — Pi supports it; OpenCode does not document it.
- `${@:N}` and `${@:N:L}` — Pi-only slicing.
- Complex positional parsing where differences would change the result.

If the user asks for multiple arguments, design the prompt so `$ARGUMENTS` is acceptable, e.g.:

```markdown
Use the arguments as: `<target> <mode> [notes...]`.
Arguments: $ARGUMENTS

Infer the target, mode, and notes from that argument string. If ambiguous, ask a concise clarification.
```

## Frontmatter rules

Portable core frontmatter:

```yaml
description: "Review a pull request or diff"
```

Allowed only as graceful degradation:

```yaml
argument-hint: "<target> [notes]"
```

`argument-hint` is useful in Pi autocomplete and should be harmless elsewhere. Use it only as UI help; never rely on it for behavior.

Avoid in shared files unless the user explicitly accepts OpenCode-specific behavior:

```yaml
agent: build
model: anthropic/claude-3-5-sonnet-20241022
subtask: true
```

These alter OpenCode execution and are ignored by Pi, so they can change core behavior across agents.
If needed, create an OpenCode-specific variant or clearly label the file as not behavior-identical.

When rewriting an existing agent-specific command into one shared file, remove `agent`, `model`, and `subtask` from emitted frontmatter.
Do not only audit these fields and keep them in the rewritten shared command.
If the user explicitly wants to preserve them, produce a separate OpenCode-specific variant instead of a behavior-identical shared file.

YAML hygiene:

- Quote values containing `:`, `{}`, `[]`, `#`, leading `<`, or other YAML-sensitive characters.
- Keep frontmatter valid YAML; Pi is stricter than OpenCode's fallback parser.
- Use simple scalar strings unless there is a strong reason for multiline YAML.

## Avoid non-portable automatic expansion

Do not rely on OpenCode-only expansions for core behavior:

```markdown
!`npm test`
@src/file.ts
```

OpenCode can inject shell output with ``!`command` `` and include file references with `@path`.
Pi does not document the same behavior inside prompt templates.
If that context is required, tell the agent to perform the work:

```markdown
Run `npm test` and summarize failures. If tests fail, inspect the relevant files and propose fixes.
```

```markdown
Read the file path supplied in the arguments, then review it for performance issues.
Target: $ARGUMENTS
```

Agent-specific expansion may be acceptable only as extra convenience when the prompt still works correctly without it.

## File and naming rules

- Use `.md` extension.
- Prefer flat filenames (`review.md`, `fix-tests.md`) because Pi's default prompt discovery is non-recursive.
- Avoid names that collide with built-in commands unless the user intentionally wants to override them.
- Use lowercase kebab-case for portability and clarity.
- If subdirectories are required, mention that Pi needs explicit prompt path configuration or a flattened copy.

## Output format when creating a command

Unless the user explicitly asks you to write or install files, return:

1. Recommended filename.
2. Complete Markdown contents.
3. Install paths for OpenCode and Pi.
4. Short compatibility note naming intentional graceful-degradation features.

If writing files directly, create the requested file(s), then summarize written paths.
For returned Markdown commands with fenced code blocks, use a four-backtick outer fence so nested triple-backtick examples remain valid Markdown.

## Compatibility review checklist

Before finalizing, check:

- [ ] The core prompt works if only `description`, body text, and `$ARGUMENTS` are interpreted.
- [ ] No `agent`, `model`, or `subtask` is required for correct behavior.
- [ ] No ``!`shell` `` output is required.
- [ ] No `@file` inclusion is required.
- [ ] Positional placeholders are absent or fixed-arity and safe.
- [ ] YAML frontmatter is valid and quoted where needed.
- [ ] Filename is flat, kebab-case, and `.md`.

## Examples

### Freeform command, fully portable

Filename: `review-changes.md`

```markdown
---
description: "Review code changes with emphasis on correctness and maintainability"
argument-hint: "[scope or instructions]"
---

Review the requested changes.

Scope or instructions: $ARGUMENTS

Focus on:
- Bugs and logic errors
- Tests that should be added or updated
- Security or data-loss risks
- Maintainability concerns

If no scope is provided, inspect the current working tree changes.
```

Portable because `$ARGUMENTS` carries all user input and `argument-hint` is only UI help.

### Test command without OpenCode shell injection

Filename: `fix-tests.md`

```markdown
---
description: "Run the test suite, diagnose failures, and propose or apply fixes"
argument-hint: "[test command or focus area]"
---

Run the relevant tests and diagnose failures.

User instructions: $ARGUMENTS

If no test command is provided, infer the project's standard test command from package/config files.
Explain the failing behavior, make the smallest safe fix, and rerun the relevant tests.
```

Portable because it asks the agent to run tests rather than relying on OpenCode's ``!`npm test` `` pre-expansion.

### Avoid: behavior differs by agent

```markdown
---
description: "Analyze coverage"
agent: build
---

Here is current coverage:
!`npm test -- --coverage`

Suggest improvements.
```

Not compatible: OpenCode changes execution agent and injects shell output while Pi sees a normal prompt template.
