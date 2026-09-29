# Code search

Adds a `code_search` tool that runs [jg (jevgrep)](https://github.com/remotehostai/jg) semantic code search. It also nudges the model to use it before `rg`, `grep`, or `find` when it explores code.

## Privacy

`code_search` sends the query and selected source snippets from the current repository to the hosted Jevgrep service. That service calls a model through Vercel AI Gateway. This happens in every repository where the extension is loaded; there is no allowlist. If a repository must not leave your machine, do not load this extension for that session (`pi --no-extensions`, or remove the link).

## Enable

1. Install jg and sign in: `npm install -g @remotehost/jg`, then `jg login`. jg requires Node.js 22+ and ripgrep.
2. Run `./setup.sh` from the repository root. Select **Harness → extensions → code-search**, then run `/reload` in Pi.

If Pi cannot find `jg` on `PATH`, set `PI_JG_BIN` to the absolute path of the executable. This can happen with a per-shell Node manager such as fnm.

## Behavior

- **Tool.** `code_search` takes `query`, optional `paths` (up to 20), `limit` (1–20; jg's default is 5), and `broad`. It runs `jg --json [--limit N] [--broad] -- <query> <paths>` at the workspace root. The workspace root is the git top level, or the current directory outside git. The call uses no shell and no stdin, and has a 120-second timeout. The result is jg's schema-version-1 JSON plus a short note. Match paths are relative to the workspace root.
- **Path confinement.** Every path is resolved with `realpath`. The tool rejects paths outside the workspace root (including symlink escapes), paths with hidden segments, and git-ignored paths. jg would otherwise send explicit ignored or hidden files. The tool also refuses to run when the workspace root is your home directory or the filesystem root.
- **Not exposed.** `--all`, `--max-evaluations`, `--no-cache`, `--debug`, and `--dump-candidates` are not available. `--all` can make up to 20,000 model calls on your account.
- **Prompt.** `promptSnippet` and `promptGuidelines` tell the model to start discovery with `code_search`. It keeps `rg`/`grep` for exact identifiers, regex, and exhaustive references, and it confirms findings with `read`/`rg` before it edits.
- **Nudge.** In each user prompt, the first `grep`/`find` tool result, or the first `bash` result whose command runs `rg`, `grep`, `ag`, `ack`, `find`, `fd`, or `git grep`, gets one appended hint. This happens only if `code_search` has not run yet in that prompt. A bash command that runs `jg` counts as use. Nothing is blocked, and the search output is not changed.
- **Failures.** Exit code 1 (no matches) is a normal result with a note that absence is not proven. If `jg` is missing or not logged in, the tool fails with fallback advice. After that it fails immediately for the rest of the runtime, and the nudge stops. Other jg errors fail the call with a bounded, escaped diagnostic. Malformed stdout is never echoed.

## Subagents

Loading this extension adds `code_search` only to sessions that load it and do not restrict tools. The tool is not available in a `pi-subagents` child unless both of these are true:

- The child loads the extension. Foreground children never load ambient extensions. Background children load them only when the agent does not set `extensions`. `subagents.defaultSubagentOnlyExtensions` loads it into every agent that does not declare its own list.
- The agent's effective `tools` list includes `code_search`. With an explicit allowlist, Pi removes unlisted extension tools from the child's registry. The extension cannot add itself back.

Subagent wiring is not automated yet.

## Check

```sh
node --test harness/pi/extensions/code-search/tests/*.test.mjs
```

The tests run offline. They use a fake jg runner, a stub executable, temporary git repositories, and Pi's real extension loader when Pi is installed. They make no network or model calls.
