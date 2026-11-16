# Changelog

## 0.1.0

- First release. It replaces the Bash picker in `setup.sh`, which now builds `ae` and runs it.
- Detects T3 Code and its Claude Code instances, Codex, Grok, Pi and Kilo, with versions, homes and the skill folders each one loads.
- Interactive installer: a skills × harnesses grid, Pi and Tools tabs, filtering, plan review with per-conflict approval, live apply progress with a cargo build bar, and a summary.
- Places each link so that every selected harness loads one copy and no other harness picks it up. Respects folders that harnesses share (`~/.claude/skills`, `~/.agents/skills`).
- `status`, `doctor`, `add`, `remove`, `prune` and `completions` commands, with `--dry-run`, `--yes`, `--replace` and `--json`.
- `doctor` asks Grok, Kilo and Codex which skills they load and reports any mismatch.
- Creates and removes only symlinks into the checkout. Anything else in the way is backed up, and only after approval.
