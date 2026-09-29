# Code search maintenance

- Keep this extension a thin jg CLI adapter: one `code_search` tool plus the `before_agent_start` reset and `tool_result` nudge in `policy.ts`. No commands, no automatic searches, no install or login steps, and no changes to other tools' inputs or outputs except the one appended hint.
- The nudge never blocks and fires at most once per prompt. It is silent after `code_search` or a bash `jg` call, after an `UnavailableError`, and when `code_search` is not an active tool.
- `jg.ts` owns data egress. Keep `realpath` workspace confinement, the hidden-segment and git-ignore rejection, and the refusal to search the home or filesystem root. Run jg at the workspace root with root-relative paths and `--` before the query. Do not expose `--all`, `--max-evaluations`, `--no-cache`, `--debug`, or `--dump-candidates`.
- Keep shell-free argv, closed stdin, the timeout, bounded capture, process-group cancellation, and the exit mapping: 0/1 are results, 130 is cancellation, a login diagnostic or missing binary is `UnavailableError`, and anything else is an escaped bounded error. Never echo malformed stdout. Accept only `schemaVersion: 1`.
- `PI_JG_BIN` must be absolute. There is no project-local executable configuration.
- Tests stay offline: fake runner, stub executable, temporary git repositories, and Pi's real loader when installed. Run `node --test harness/pi/extensions/code-search/tests/*.test.mjs`. Live jg searches send source to a third party; run them only with explicit approval.
- Coordinate tool, parameter, nudge, or egress changes with `README.md`, these tests, the root `README.md`, and the root changelog.
