# br - Beads Rust Issue Tracking

This repository uses **beads_rust** (`br`) for local, dependency-aware issue tracking stored under `.beads/`.

## What is br?

`br` is a local-first issue tracker for AI coding agents and developers. It stores issues in SQLite and exports JSONL for git-friendly collaboration.

**Learn more:** [github.com/Dicklesworthstone/beads_rust](https://github.com/Dicklesworthstone/beads_rust)

## Quick Start

### Essential Commands

```bash
# Create new issues
br create "Add user authentication"

# View all issues
br list

# View ready/unblocked issues
br ready

# View issue details
br show <issue-id>

# Claim or update work
br update <issue-id> --claim
br update <issue-id> --status in_progress

# Close completed work
br close <issue-id> --reason "Completed"

# Explicit final JSONL export before committing .beads/
br sync --flush-only
```

## Working with Issues

Issues in br are:

- **Repo-local**: state lives under `.beads/`.
- **AI-friendly**: every command supports structured output with `--json`.
- **Dependency-aware**: use `br dep add`, `br ready`, and `br blocked` to manage ordering.
- **Non-invasive**: br never commits, pushes, pulls, or installs hooks for you.

## Sync and Git

Mutating commands auto-flush JSONL by default. When preparing a git commit that should include tracker state, run:

```bash
br sync --flush-only
git add .beads/
```

Commit `.beads/` only when the project workflow/user asks for it.

## Setup

```bash
# Initialize in your repo when explicitly requested
br init

# Add/update agent instructions only when requested
br agents --check
br agents --add --dry-run
```

## Learn More

- **Documentation**: [github.com/Dicklesworthstone/beads_rust/docs](https://github.com/Dicklesworthstone/beads_rust/tree/main/docs)
- **CLI reference**: `br --help` and `br <command> --help`
- **Diagnostics**: `br info`, `br where`, `br doctor --json`
