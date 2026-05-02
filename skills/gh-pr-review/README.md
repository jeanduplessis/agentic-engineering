# gh-pr-review

A GitHub CLI extension for reading and responding to PR review comments. Built for coding agents that need structured JSON access to review threads.

## Features

- **View reviews** with inline comments and full thread history
- **Reply to threads** directly from the command line
- **List threads** with resolution and outdated status filters
- **Resolve/unresolve threads** after addressing feedback
- **JSON output** designed for programmatic consumption
- **Zero runtime dependencies** — standalone binary via Bun

## Installation

```bash
gh extension install jeanduplessis/gh-pr-review
```

Requires the [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated.

## Usage

### View reviews

```bash
# View all reviews for a PR
gh pr-review view --pr 42

# View using a PR URL
gh pr-review view https://github.com/owner/repo/pull/42

# Filter by reviewer and state
gh pr-review view --pr 42 --reviewer octocat --states CHANGES_REQUESTED

# Show only unresolved, non-outdated comments
gh pr-review view --pr 42 --unresolved --not-outdated

# Limit thread replies to last 3
gh pr-review view --pr 42 --tail 3
```

### List review threads

```bash
# List all threads
gh pr-review threads --pr 42

# List only unresolved threads
gh pr-review threads --pr 42 --unresolved
```

### Reply to a thread

```bash
gh pr-review reply --pr 42 --thread-id PRRT_... --body "Fixed in latest commit"
```

### Resolve / unresolve a thread

```bash
gh pr-review resolve --pr 42 --thread-id PRRT_...
gh pr-review unresolve --pr 42 --thread-id PRRT_...
```

### Repository selection

All commands accept `-R owner/repo` to specify the repository, or you can provide a full PR URL as a positional argument. If you're in a git repository with a GitHub remote, the repository is inferred automatically.

```bash
# Explicit repository
gh pr-review view -R owner/repo --pr 42

# PR URL (repository and number extracted automatically)
gh pr-review view https://github.com/owner/repo/pull/42
```

## Development

### Prerequisites

- [Bun](https://bun.sh/) v1.0+
- [GitHub CLI](https://cli.github.com/) (`gh`)

### Running locally

```bash
# Run directly with Bun
bun run src/index.ts view --pr 42

# Or install as a local extension
gh extension install .
gh pr-review view --pr 42
```

### Building

```bash
# Build for all platforms
bash script/build.sh

# Binaries are output to dist/
ls dist/
```

### Type checking

```bash
bun run typecheck
```

## Architecture

- **TypeScript** compiled to standalone binaries with `bun build --compile`
- **GraphQL-only** API interaction via `gh api graphql`
- **Zero dependencies** — no npm packages, no token management
- **Hand-rolled arg parser** — minimal, no external CLI framework

## License

MIT
