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
- Supports multiple skills via legacy scalar `skill` and YAML-list `skills`, injecting each declared `SKILL.md` as a separate visible custom message before the command prompt.
- Skips declared-skill injection silently when the same skill is already present in the active model context through a native Pi `<skill ...>` user message or prior `extended-command-skill` message; canonical `SKILL.md` path is the primary identity, with skill name as fallback.
- Adds a context-hook safety net that removes only duplicate `extended-command-skill` messages before provider calls, preferring native Pi skill messages and never removing user/native skill messages.
- Resolves all declared skills before injection and fails command execution before skill injection or prompt send when any declared skill is missing or unreadable.
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

1. Create or choose local skills such as `~/.agents/skills/tdd/SKILL.md` and `~/.agents/skills/beads/SKILL.md`.
2. Create a command with:
   ```md
   ---
   description: Skill smoke test
   skills:
     - tdd
     - beads
   ---
   Prompt body
   ```
3. Run the command and confirm one visible custom message per skill appears before the rendered command prompt, in declaration order.
4. Run another command that declares an already-loaded skill and confirm duplicate skill context is skipped silently while the prompt still sends.
5. Change one skill to a missing name and confirm the command fails before injecting skills or sending the prompt.
