# gh-pr-review — Implementation Plan

A GitHub CLI extension built in TypeScript, focused exclusively on **reading and responding to PR review comments** for coding agent use.

## Overview

This extension provides coding agents with structured JSON access to PR review threads — view comments, reply to feedback, and resolve threads — without the noise of the full GitHub API. It is compiled to standalone binaries using `bun build --compile` and interacts with the GitHub API by shelling out to `gh api graphql`.

Inspired by [agynio/gh-pr-review](https://github.com/agynio/gh-pr-review) (Go), but scoped down to the read-and-respond workflow and rewritten in TypeScript.

## Scope

### In scope (read + reply only)

| Command | Purpose |
|---|---|
| `gh pr-review view` | View reviews with inline comments and thread replies |
| `gh pr-review reply` | Reply to a review thread |
| `gh pr-review threads` | List review threads (with filters) |
| `gh pr-review resolve` | Resolve a thread |
| `gh pr-review unresolve` | Unresolve a thread |

### Out of scope

- Review creation (`review --start`, `--add-comment`, `--submit`)
- Human-readable / interactive output
- REST API fallbacks

## Command API

All commands output JSON to stdout. Errors go to stderr with non-zero exit codes. Optional fields are omitted rather than set to `null`. Array responses default to `[]`.

### Input conventions

Every command accepts:
- `-R owner/repo` — repository selector (required unless in a git repo with a gh remote)
- `--pr <number>` — pull request number
- Alternatively, a PR URL as a positional argument (e.g. `https://github.com/owner/repo/pull/42`)

### Commands

```
gh pr-review view [<pr-url>] [-R owner/repo] [--pr <number>]
    [--reviewer <login>]
    [--states <APPROVED|CHANGES_REQUESTED|COMMENTED|DISMISSED>]
    [--unresolved]
    [--not-outdated]
    [--tail <n>]

gh pr-review reply [<pr-url>] [-R owner/repo] [--pr <number>]
    --thread-id <PRRT_...>
    --body <text>

gh pr-review threads [<pr-url>] [-R owner/repo] [--pr <number>]
    [--unresolved]

gh pr-review resolve [<pr-url>] [-R owner/repo] [--pr <number>]
    --thread-id <PRRT_...>

gh pr-review unresolve [<pr-url>] [-R owner/repo] [--pr <number>]
    --thread-id <PRRT_...>
```

## Output Schemas

### ReviewReport (from `view`)

```json
{
  "reviews": [
    {
      "id": "PRR_...",
      "state": "CHANGES_REQUESTED",
      "author_login": "reviewer",
      "body": "optional review body",
      "submitted_at": "2024-01-15T10:30:00Z",
      "comments": [
        {
          "thread_id": "PRRT_...",
          "path": "src/file.ts",
          "line": 42,
          "author_login": "reviewer",
          "body": "Consider refactoring this",
          "created_at": "2024-01-15T10:30:00Z",
          "is_resolved": false,
          "is_outdated": false,
          "thread_comments": [
            {
              "author_login": "author",
              "body": "Good point, will fix",
              "created_at": "2024-01-15T11:00:00Z"
            }
          ]
        }
      ]
    }
  ]
}
```

### ReplyMinimal (from `reply`)

```json
{
  "comment_node_id": "PRRC_..."
}
```

### ThreadSummary[] (from `threads`)

```json
[
  {
    "threadId": "PRRT_...",
    "isResolved": false,
    "path": "src/file.ts",
    "line": 42,
    "isOutdated": false
  }
]
```

### ThreadMutationResult (from `resolve` / `unresolve`)

```json
{
  "thread_node_id": "PRRT_...",
  "is_resolved": true
}
```

## Architecture

### Project structure

```
gh-pr-review/
├── src/
│   ├── index.ts              # CLI entry point, argument routing
│   ├── commands/
│   │   ├── view.ts           # review view command
│   │   ├── reply.ts          # comments reply command
│   │   ├── threads.ts        # threads list command
│   │   ├── resolve.ts        # threads resolve command
│   │   └── unresolve.ts      # threads unresolve command
│   ├── graphql/
│   │   ├── queries.ts        # GraphQL query strings
│   │   └── mutations.ts      # GraphQL mutation strings
│   ├── gh.ts                 # gh api graphql wrapper (child_process)
│   ├── types.ts              # TypeScript interfaces for all schemas
│   └── utils.ts              # Shared utilities (arg parsing, error handling)
├── script/
│   └── build.sh              # Cross-compilation build script
├── .github/
│   └── workflows/
│       └── release.yml       # Release workflow
├── SKILL.md                  # Agent skill definition
├── README.md                 # Human-readable documentation
├── PLAN.md                   # This file
├── package.json
├── tsconfig.json
└── .gitignore
```

### Technical decisions

1. **Argument parsing** — Minimal hand-rolled parser operating on `process.argv`. No external dependency (commander, yargs, etc.). Keeps the binary small and avoids needless deps.

2. **GitHub API interaction** — Shell out to `gh api graphql -f query=... -F variables=...` via `child_process.execFileSync`. This inherits `gh` authentication automatically — no token management needed. All commands use GraphQL exclusively (no REST).

3. **Build toolchain** — `bun build --compile` with cross-compilation:
   - `bun-darwin-arm64` (macOS Apple Silicon)
   - `bun-darwin-x64` (macOS Intel)
   - `bun-linux-x64` (Linux x64)
   - `bun-linux-arm64` (Linux ARM)
   - `bun-windows-x64` (Windows x64)

4. **Release automation** — `cli/gh-extension-precompile@v2` with `build_script_override: "script/build.sh"`. The build script produces binaries in `dist/` with the `{os}-{arch}{ext}` naming convention expected by the action.

5. **Local development** — `bun run src/index.ts -- <args>` for quick iteration. `gh extension install .` for local testing after `bun build --compile`.

6. **Error handling** — All errors are written to stderr as JSON `{ "error": "message" }` and the process exits with code 1. GraphQL errors from the GitHub API are surfaced in the same structure.

## Implementation order

### Phase 1: Scaffolding

- `package.json` with project metadata and scripts
- `tsconfig.json` for strict TypeScript compilation
- `.gitignore` for node_modules, dist, binaries

### Phase 2: Core infrastructure

- `src/gh.ts` — wrapper to call `gh api graphql`, parse JSON response, handle errors
- `src/types.ts` — TypeScript interfaces matching the output schemas
- `src/utils.ts` — argument parser, PR URL/number resolver, error formatter, JSON output helper

### Phase 3: GraphQL

- `src/graphql/queries.ts` — queries for `view` (reviews + comments + thread replies) and `threads` (thread list)
- `src/graphql/mutations.ts` — mutations for `reply` (addPullRequestReviewThreadReply), `resolve` (resolveReviewThread), `unresolve` (unresolveReviewThread)

### Phase 4: Commands

- `src/commands/view.ts` — fetch reviews, apply client-side filters (reviewer, states, unresolved, not-outdated, tail), output ReviewReport
- `src/commands/reply.ts` — mutation to reply to a thread, output ReplyMinimal
- `src/commands/threads.ts` — fetch thread list with optional unresolved filter, output ThreadSummary[]
- `src/commands/resolve.ts` — mutation to resolve a thread, output ThreadMutationResult
- `src/commands/unresolve.ts` — mutation to unresolve a thread, output ThreadMutationResult

### Phase 5: CLI entry point

- `src/index.ts` — parse first positional arg as command name, dispatch to command handler, handle `--help` / `--version`, catch top-level errors

### Phase 6: Build & release

- `script/build.sh` — cross-compile for all targets using `bun build --compile --target=...`, output to `dist/`
- `.github/workflows/release.yml` — trigger on `v*` tags, use `cli/gh-extension-precompile@v2` with build script override

### Phase 7: Documentation

- `SKILL.md` — structured skill definition for AI coding agents (name, description, commands, schemas, workflows, best practices)
- `README.md` — human-readable project documentation with quickstart, usage examples, and development instructions

## Key differences from agynio/gh-pr-review

| Aspect | agynio/gh-pr-review | This project |
|---|---|---|
| Language | Go | TypeScript (Bun) |
| Scope | Full review lifecycle | Read + reply only |
| Commands | 7+ subcommands with nested flags | 5 focused commands |
| Review creation | Yes (start, add-comment, submit) | No |
| API layer | go-gh library | Shell out to `gh api graphql` |
| Build | Go cross-compile | Bun compile |
| Runtime deps | None (Go binary) | None (Bun standalone binary) |
| Binary size | ~10MB | ~50MB (Bun runtime embedded) |
