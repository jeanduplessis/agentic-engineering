## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Quick reference:**
- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work

For full workflow details: `bd prime`

## Terminology

Before changing domain behavior, read `AGENT_LEXICON.md`.
Use canonical terms from `AGENT_LEXICON.md` in code, docs, task descriptions, and agent outputs.
Do not introduce synonyms for existing concepts unless updating `AGENT_LEXICON.md` first.
Do not duplicate the full lexicon inside `AGENTS.md`.

## Project Guidance

- `README.md` is end-user documentation. Keep it focused on installation, usage, output examples, colors, and errors.
- Keep implementation/architecture details in code, tests, beads tasks, or agent notes unless needed for user troubleshooting.
- `gs` is a read-only CLI. Do not add staging, unstaging, discard, commit, or interactive actions unless the product scope changes explicitly.
- Production repository inspection must use the Rust Git library backend; do not shell out to the installed `git` binary from `src/` code.
- Tests may use temporary Git repositories and the `git` binary to set up observable repository states.
- Validate Rust changes with `cargo fmt` and `cargo test`; run `cargo clippy --all-targets --all-features -- -D warnings` for non-trivial code changes.
