# Archive

Retired resources moved out of the active trees. Nothing here is discovered, linked, or installed by
`setup.sh`, Pi, or the package manifest. Keep the content for reference only.

## `skills/`

Skills that are no longer used. They were moved out of `skills/` so skill discovery and installation leave
them untouched. Any matching symlinks in `~/.agents/skills` or `~/.pi/agent/skills` were removed.

- `ait-cli`
- `code-quality`
- `code-review-workflow`
- `epic-implement`
- `epic-orchestrate`
- `pr-create`
- `tdd`
- `to-epic`
- `to-issues`
- `to-prd`
- `to-tasks`

`custom-command` was not archived here. Its eval contract is still exercised by
`skill-factory/tools/skill_eval/tests`, so it now lives at
`skill-factory/tools/skill_eval/tests/fixtures/custom-command` as a repo-owned test fixture.

## `commands/`

Pi prompt templates whose only skill dependencies were archived. Moved out of `harness/pi/commands/` so the
live command inventory stays valid.

- `code-review.md`
- `epic-orchestrate.md`
- `pr-create-update.md`
- `to-epic.md`
- `to-issues.md`
