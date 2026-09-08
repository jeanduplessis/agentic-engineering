# Genie development

## Contract

- `genie` is an independent Rust package; its binary is `g`. Support macOS and Linux. It is a one-shot wrapper around installed Pi, not another agent runtime.
- Recognize help/version/`--quiet`/`-q`/`--model <model>`/`--thinking <level>`/`--` before the first message word. Reject other leading options; preserve all words after the first message word. Join arguments with single spaces without trimming their contents. Reject empty/whitespace-only or non-Unicode requests before launching Pi.
- Resolve model and thinking independently: `GENIE_MODEL`/`GENIE_THINKING` > corresponding CLI option > Pi defaults. Unset/empty/whitespace-only environment values are absent; otherwise preserve model strings unchanged, including provider/id and suffix semantics. Omit unselected Pi options. Forward explicit thinking as `--thinking` so Pi gives it precedence over a model `:thinking` suffix. Accept only `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Reject non-Unicode configuration and every missing/blank/leading-`-` CLI value or invalid thinking level before launch, even if overridden. Repeated valid options use the last value. Diagnostics must not echo configuration values. Help/version short-circuit without reading configuration environment.
- Supervise `pi --mode json [--model <model>] [--thinking <level>] -- <one prompt>` directly with `Command`. Never interpolate through a shell. Use `serde_json` for protocol parsing, `signal-hook` and `libc` for bounded Unix supervision; keep dependencies small and locked.
- Put concise execution/output guidance in the user prompt, followed by `User request:` and a newline before the original message. This prevents leading Pi attachment, command, or option syntax from being parsed as CLI input.
- Do not set system-prompt flags: `--append-system-prompt` can suppress Pi's normal `APPEND_SYSTEM.md` discovery. Inherit cwd, environment, Pi configuration, context, extensions, and trust. Null stdin. Start a normal new session; Pi owns persistence and its retry/compaction policies.
- Drain stdout JSONL and stderr concurrently without accumulating a transcript. Bound records and active tool state, handle split UTF-8 and EOF without newline, ignore unknown valid events, and fail malformed protocol without echoing payloads. No raw JSON, reasoning, tool arguments/results, or intermediate assistant text may reach stdout.
- Only the latest assistant `message_end` can supply final text. New agent/turn/assistant starts invalidate earlier candidates. Wait for child exit and pipe EOF; end/settled/retry hints are not completion fences. Empty/error responses replace earlier text. Preserve text-block order and Pi print's added newline per block.
- Preserve nonzero Pi status without successful stdout. Missing final, error/aborted, cancelled retry, and unresolved tool use are failures even if Pi exits zero. Terminal length prints text with a warning and otherwise successful status; intermediate failures can recover. Report only the terminal error/aborted assistant's bounded, control-sanitized `errorMessage` on stderr, with a generic fallback; recovered errors remain hidden. A zero exit code does not establish semantic task success.
- Animate only TTY stderr with non-dumb TERM and no quiet option. Show Starting Pi, Working, or an actual sanitized tool name, monotonic elapsed seconds and completed calls including failures. Concurrent tools must not appear idle. Fit current width, clear on all terminal paths, preserve visible diagnostics, and never add ANSI to redirected stderr. Quiet suppresses only activity.
- Isolate the Pi child process group. Catch INT/TERM/HUP; INT requests Pi TERM cleanup but exits 130, TERM/HUP exit 143/129. Allow bounded Pi cleanup for tracked detached tools before forced owned-group termination; repeat cancellation accelerates it. Reap the owned child and bound cleanup drainage. Before synchronous pre-supervision error diagnostics, restore inherited signal dispositions (including ignore) after reaping any spawned Pi; OS signal termination is allowed on these early paths. Full/unread downstream stderr or final stdout must not block cancellation; keep the writer handoff bounded, do not mutate inherited descriptor flags, and do not join a stalled writer during cancellation. Idle retained pipes after exit fail explicitly. Do not claim cleanup of arbitrary untracked/daemonized descendants or after forced kill.
- Do not add backend configuration, model settings beyond the two selections above, flag passthrough, approval bypasses, a confirmation gate, sandbox claims, session management, verbose/log UI, or another runtime. Prompt guidance is not an enforced safeguard.

## Verification

Run from this directory (Rust 1.88+, Python 3.9+ for process/PTY fixtures):

```sh
cargo fmt --all -- --check
cargo clippy --offline --locked --all-targets --all-features -- -D warnings
cargo test --offline --locked --all-targets
cargo build --offline --locked --release
./target/release/g --help
./target/release/g --version
python3 -I tests/offline.py target/release/g
```

Resolve/download required crates with Cargo only if the local cache is missing them. Use fake Pi integration tests with child-specific PATH, HOME, and Pi state. Never let automated tests reach real Pi, credentials, or models. Do not mutate global environment in tests. Test transport, final selection, activity, status and cancellation rather than exact guidance prose. Bound subprocess fixtures and use handshakes where possible. No live model tests or installation without separate approval.

Keep changes small. Coordinate public behavior across source, README, this file, tests, and change notes. Preserve unrelated work; do not add release infrastructure. Pi 0.85.0 JSON-mode and signal-cleanup source is the initial compatibility reference, not a live-evaluation guarantee.
