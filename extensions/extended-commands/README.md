# extended-commands

Local Pi extension that owns the global command library at `~/.agents/commands`.

## V1 plain command behavior

- Loads direct Markdown files from `~/.agents/commands/*.md` only.
- Registers each filename stem as a Pi slash command.
- Uses frontmatter `description` for autocomplete text when present.
- Sends the rendered Markdown body to Pi as a user message.
- Does not change model or thinking for plain commands.
- Supports exact `provider/model` routing and unique bare model IDs.
- Reports ambiguous, missing, or credential-unavailable model declarations as runtime errors before sending the prompt.
- Supports valid Pi thinking levels.
- Restores previous model/thinking after `agent_end` by default; `restore: false` makes changes sticky.
- Supports one declared `skill` and injects its `SKILL.md` content as a visible custom message before the command prompt.
- Fails command execution before prompt send when a declared skill is missing or unreadable.
- Substitutes `$ARGUMENTS`, `$@`, and simple positional placeholders (`$1`, `$2`, ...).
- Passes legacy shell/file expansion syntax through literally; unsupported syntax produces runtime warnings.
- Warns on unknown frontmatter instead of failing command execution.

No custom renderer is added in V1; injected skill messages use Pi's default custom-message display.

## Manual smoke test

After activation through Pi extension discovery:

1. Create `~/.agents/commands/hello-test.md`:
   ```md
   ---
   description: Say hello for an extension smoke test
   ---
   Say hello to $1. Raw args: $ARGUMENTS
   ```
2. Reload Pi extensions with `/reload` or restart Pi.
3. Run `/hello-test Ada Lovelace`.
4. Confirm Pi receives: `Say hello to Ada. Raw args: Ada Lovelace`.
5. Confirm the current model and thinking level are unchanged by the command.

Routing smoke test:

1. Create `~/.agents/commands/model-test.md` with `model`, `thinking`, and optional `restore` fields.
2. Run the command and confirm Pi switches to the declared exact or unique bare model and thinking level.
3. With default restore, confirm model/thinking return after the agent turn ends.
4. With `restore: false`, confirm model/thinking remain sticky.

Skill injection smoke test:

1. Create or choose a local skill such as `~/.agents/skills/tdd/SKILL.md`.
2. Create a command with `skill: tdd`.
3. Run the command and confirm a visible custom message containing the skill content appears before the rendered command prompt.
4. Change `skill` to a missing name and confirm the command fails before sending the prompt.
