# genie (`g`)

Run a natural-language task once through your installed Pi:

```sh
g find the file that defines the login form
g "rename the local variable 'usr' to 'user' in src/login.ts"
g 'find references to $HOME; do not change any files'
```

`genie` is the package name; `g` is the command. It is a small wrapper, not a separate agent runtime or model client.

## Requirements and installation

- macOS or Linux.
- Rust 1.88 or newer to build/install. Rust dependencies are `serde_json`, `signal-hook`, and `libc`, pinned with their transitive dependencies in `Cargo.lock`.
- An installed, authenticated `pi` on PATH, supporting `--mode json` and `--`. The protocol and cleanup contract were checked against Pi 0.85.0 source. Run Pi directly first to configure it and resolve any trust or interactive setup prompts.

Check for an existing command, alias, or function named `g` before installing:

```sh
type -a g
```

Resolve any collision first; an alias or function can still shadow the installed binary. From the repository root:

```sh
cargo install --path tools/genie --locked
g --help
g --version
```

This command does not force replacement of an existing binary. Alternatively, repository setup discovers the package under **Tools → genie** and installs `g`. The setup tool installer uses Cargo's `--force`, so check collisions before selecting it. No setup changes are needed for this package.

## Input

```text
g [-q|--quiet] [--] <message words...>
g --help | -h
g --version | -V
```

Arguments are joined with one space between them. Contents within each argument, including whitespace, quotes, newlines, and Unicode, are preserved. Quote text that your shell would otherwise expand or interpret; the wrapper does not run a shell. For example:

```sh
g 'find files containing $(whoami) or *.log'
g 'find the config file
and return its path'
g -- --help
g '@notes.md is a filename; find it'
g '/review is text here, not a Pi command'
```

Help/version, `--quiet`/`-q`, and `--` are recognized only before the first message word. `--quiet` hides activity only, not results or diagnostics. Other leading options are usage errors; use `--` to submit option-like text. After the first word, every argument is literal message text, so `g explain --help` submits `explain --help`. There is no Pi flag passthrough or model/backend configuration.

Empty or whitespace-only requests are usage errors. Requests must be Unicode. Help, version, and usage errors never start Pi. Stdin is ignored and Pi receives EOF: piped content is not part of the request, and this command cannot answer interactive prompts.

## Execution and output

**Explicit requests execute immediately. There is no extra confirmation gate and no sandbox.** Pi can modify files or perform external actions using your existing tools and permissions. Use only requests that grant the authority you intend. Installed Pi policies, trust decisions, extensions, and other instructions remain in effect and can still block work.

`g` supervises a direct `pi --mode json -- <one prompt>` child in the current directory with the existing environment. It adds short user-prompt guidance to execute the explicit request, preserve unrelated changes, stop on ambiguity or blockers, verify the result, and return a concise confirmation or file paths. The message follows the neutral label `User request:` and a newline, so leading `@file`, `/command`, and option-like text are natural-language input rather than Pi CLI syntax. This guidance is **not an enforced safeguard or an output guarantee**. No system-prompt override is used; Pi's normal instruction/context loading is preserved.

Each invocation starts a normal new Pi session. `g` does not continue, resume, suppress, or manage sessions. Pi owns session persistence and all configuration, authentication, model selection, context, extensions, and trust behavior. Nothing is automatically approved or disabled by the wrapper.

### Activity and streams

When stderr is a TTY and `TERM` is not `dumb`, one animated line shows `Starting Pi`, then `Working` or `Running <tool name>`, monotonic elapsed seconds, and completed tool calls. Concurrent tools stay active until all have ended. Counts include failed calls; they are **not successful operations, task percentages, or time estimates**. Names come only from actual tool execution events, are ASCII-sanitized and capped at 48 characters, and the line is clipped to the current terminal width. Very narrow terminals show less detail; unknown width hides the line.

Use `g --quiet find the login form` (or `-q`) to hide activity. Redirected stderr never receives animation or ANSI from Genie. Pi's own stderr bytes are forwarded, including with `--quiet`; on a TTY the indicator clears for diagnostics and waits for a complete diagnostic line before repainting. It clears on completion, failure, or cancellation before final output. Pi itself may emit terminal controls; Genie does not strip its diagnostics.

Stdout contains only the latest authoritative assistant response, **after Pi exits and both pipes reach EOF**. Each text block prints in order with one added newline, matching Pi print mode. Intermediate text, reasoning, tool arguments/results, and JSON events are not printed. A terminal assistant error/abort reports its `errorMessage` on stderr when present (up to 4,096 characters, without terminal/bidi controls), with a generic fallback; errors later recovered by another response stay hidden. Later retries or extension turns can replace earlier responses, including with a genuinely empty response. Genie does not implement Pi's retry or compaction policies.

JSON records are limited to 8 MiB each; oversized, malformed, truncated, or unsupported final responses fail without echoing the payload. Unknown valid event types are ignored. Memory holds one bounded record, the latest assistant text (plus its final output handoff), and at most 1,024 active calls, not a session transcript. A bounded writer lane preserves diagnostic order without letting a full output pipe block signal handling or reaping; it does not change inherited descriptor flags. A complete final record without a trailing newline is accepted. After child exit, ongoing tail output is drained; pipes still open after two seconds with no data cause an explicit failure, not partial success.

### Exit and cancellation

- Usage errors exit 2. Launch, protocol, missing-final-response, final assistant error/abort, cancelled retry, unresolved tool-use, and output-write failures are nonzero (normally 1).
- Nonzero Pi exit status is preserved, with no successful stdout. During supervision, signal termination uses the conventional `128 + signal` code, not signal termination of Genie itself. A Pi process terminated during wrapper error cleanup can therefore produce 143 or 137.
- A terminal `length` response prints its text with a terse truncation warning and exits zero if Pi otherwise succeeds. Intermediate length/errors can recover. An empty terminal assistant response prints nothing; it never substitutes an earlier answer.
- Ctrl-C/SIGINT cancels with 130; SIGTERM with 143; SIGHUP with 129. Pi is isolated from the foreground Ctrl-C process group. Genie translates INT to Pi TERM so Pi can clean up its tracked detached tools; TERM/HUP use Pi's corresponding cleanup handlers. Cleanup gets two seconds before forcing the owned child group, then up to half a second of tail drainage. A repeated cancellation forces shutdown promptly. The owned child is reaped. Cancellation also works while final stdout or diagnostics are blocked. With a stalled sink, bounded cancellation can abandon queued output/clearing; bytes already written cannot be recalled. Normal completion waits for output writes to finish.
- Launch and other pre-supervision errors restore inherited signal dispositions after reaping any spawned Pi. Their diagnostics can terminate by an OS signal; inherited ignored signals remain ignored.
- **Cleanup is not a guarantee for arbitrary daemonized or untracked extension descendants.** Forced killing cannot run Pi's cleanup handlers. Do not treat this wrapper as process-tree containment or a sandbox.

A zero exit code is **not independent proof that the requested task succeeded**; read the result and verify important outcomes. These checks validate the transport and terminal outcome, not semantic task success.

## Development

Automated runtime checks are offline and use isolated fake Pi executables, never a real model. Fetch Cargo dependencies once if they are not cached. The additional process/PTY checks require Python 3.9+ on Unix:

```sh
cd tools/genie
cargo fmt --all -- --check
cargo clippy --offline --locked --all-targets --all-features -- -D warnings
cargo test --offline --locked --all-targets
cargo build --offline --locked --release
./target/release/g --help
./target/release/g --version
python3 -I tests/offline.py target/release/g
```

PTY checks cover animation, quiet/dumb terminals, resize, diagnostics, and cleanup without a model. Live Pi/model behavior and Linux execution still need separate validation when authorized; current execution evidence is macOS, plus Pi 0.85.0 source inspection. Other Pi versions and arbitrary extension protocols are not guaranteed compatible.

See [AGENTS.md](AGENTS.md) for implementation constraints and [CHANGELOG.md](CHANGELOG.md) for change notes. Licensed under [MIT](LICENSE).
