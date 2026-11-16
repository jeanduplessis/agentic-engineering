# AGENTS.md — ae

## Project

- `ae` is the Æ installer: it links this checkout's skills, Pi resources and tools into the user's coding harnesses. `../../setup.sh` builds it and passes its arguments through.
- Modules:
  - `paths.rs`: path helpers and `Roots` (what counts as inside the checkout)
  - `repo.rs`: discovers skills, Pi items and tools in the checkout
  - `harness.rs`: detects T3 Code and the harnesses, and each harness's skill folders
  - `state.rs`: a `Snapshot` of what's on disk
  - `plan.rs`: desired state, the folder solver, and plan steps
  - `apply.rs`: runs a plan and emits progress events
  - `doctor.rs`: problems, plus harness introspection probes
  - `output.rs`: non-interactive text
  - `main.rs`: the clap CLI
  - `ui/`: the ratatui installer; `view.rs` only draws, `mod.rs` owns state and keys
- The README documents every harness's skill folders, the solver rules and the safety contract. Update it, `harness.rs` and the tests together.

## Commands

```sh
cargo fmt --all -- --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo build --release --locked
(cd ../.. && python3 -m unittest discover -s tests -v)   # setup.sh/ae end-to-end, offline
```

Run all five before handing off. `Cargo.lock` is committed, and `setup.sh` builds with `--locked`.

## Rules

- Never touch the user's real harness folders from tests or while developing. Use a temp `HOME` (see `tests/test_setup.py`) or `ae ... -n`.
- Every filesystem change goes through `plan::build` → review → `apply::run`. Each apply step re-inspects its destination first.
- Only symlinks into the checkout (`Roots::contains`) count as Æ-owned. Anything else is a conflict. It's replaced only when approved, and files and directories are backed up first. Don't add an operation that copies, edits or deletes something Æ doesn't own.
- When a harness changes where it looks for skills, update `Environment::detect`, the README table and `doctor` parsing together. Confirm the change against the harness itself (`grok inspect --json`, `kilo debug skill`, `codex debug prompt-input`).
- Keep `view.rs` free of side effects. Cover new UI behavior with `TestBackend` tests in `ui/tests.rs`, and CLI behavior in `tests/test_setup.py`.
- Probes run harness binaries with a timeout in an empty temp dir. `AE_NO_PROBE=1` must keep everything offline.
- Exit codes: `0` ok or cancelled, `1` failures or skipped conflicts, `2` usage errors. JSON output (`--json`) is a contract; change it deliberately.
