# Changelog

## Unreleased

- Added `genie` 0.1.0, providing the `g` command for one-shot natural-language requests through installed Pi on macOS and Linux.
- Preserve normal Pi instructions, configuration, trust, and new-session persistence; use argv-only input and concise user-prompt guidance without an extra confirmation gate.
- Added one TTY-only animated stderr line with elapsed seconds, actual sanitized tool names, and completed tool-call counts including failures. Added `--quiet`/`-q`; redirected stderr and `TERM=dumb` have no Genie animation.
- Supervise `pi --mode json` using bounded JSONL parsing and concurrent pipe drainage. Print only the latest authoritative assistant text after child exit and drainage. Keep Pi diagnostics and final assistant error causes, suppress recovered errors, preserve nonzero Pi status, reject malformed/missing/error/aborted/unresolved final outcomes, and warn on terminal length truncation.
- Added isolated child process groups, cleanup-supported INT/TERM/HUP forwarding, conventional cancellation status codes, bounded grace/forced shutdown, child reaping, and retained-pipe idle failure. A bounded output writer keeps cancellation responsive even with full/unread stderr or final stdout. Arbitrary untracked descendants and forced-kill cleanup are not guaranteed.
- Added `serde_json`, `signal-hook`, and `libc` dependencies with locked resolution; require Rust 1.88+. Added isolated offline reducer, fake-process, and Python 3.9+ PTY tests, including late continuations, chunk splits, concurrent output/tools, broken/full output pipes, detached-helper cleanup, quiet/dumb terminals, and resize. No live model evaluation is included; initial compatibility reference is Pi 0.85.0 source.
