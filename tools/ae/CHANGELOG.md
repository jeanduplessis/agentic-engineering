# Changelog

## Unreleased

- Added Claude Code resources: `prompts/OUTPUT_STYLE.md` links into each Claude Code home's `output-styles/` folder. Choose it in the new **Claude** tab (`4`) or with `ae add -c output-style [-H <claude id>]`; `ae remove -c` unlinks it.
- `status`, `status --json` (`claude`), the Claude tab and `doctor` show whether each home's `settings.json` selects the style. After linking, `ae` prints the `outputStyle` setting to add. It never edits `settings.json`.

## 0.1.0

- First release. It replaces the Bash picker in `setup.sh`, which now builds `ae` and runs it.
- Detects T3 Code and its Claude Code instances, Codex, Grok, Pi and Kilo, with versions, homes and the skill folders each one loads.
- Interactive installer: a skills × harnesses grid, Pi and Tools tabs, filtering, plan review with per-conflict approval, live apply progress with a cargo build bar, and a summary.
- Places each link so that every selected harness loads one copy and no other harness picks it up. Respects folders that harnesses share (`~/.claude/skills`, `~/.agents/skills`).
- `status`, `doctor`, `add`, `remove`, `prune` and `completions` commands, with `--dry-run`, `--yes`, `--replace` and `--json`.
- `doctor` asks Grok, Kilo and Codex which skills they load and reports any mismatch.
- Creates and removes only symlinks into the checkout. Anything else in the way is backed up, and only after approval.
