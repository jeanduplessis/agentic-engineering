# Pi subagent policy

This component owns `reviewer.md` and the strict native-child model scope. It does not install `pi-subagents`, copy its builtins, or change other agents.

## Install and check

Select **Harness → subagents** in `./setup.sh`. It is one atomic selection, not an agent picker or a whole-directory link. The plan shows both effects before confirmation:

- Link this checkout's `reviewer.md` into `<PI_AGENT_DIR>/agents/reviewer.md`.
- Merge `settings-overlay.json` into `<PI_AGENT_DIR>/settings.json`, replacing only `subagents.modelScope` with `{"enforce":true,"strict":true,"allow":["inherit"]}`.

All other settings and agents stay intact, including existing model pins, timeouts, concurrency, and role overrides. Incompatible pins or fallbacks will fail strict scope checks; this installer does not silently rewrite them. Cancelling any Pi picker or declining the plan changes nothing in the Pi target. Leave this component unselected to leave its installed state untouched.

For an explicit target, use Python 3.8+ from the repository root:

```sh
python3 harness/pi/subagents/install.py --agent-dir /absolute/path/to/pi-agent --check
python3 harness/pi/subagents/install.py --agent-dir /absolute/path/to/pi-agent --apply
```

`--check` prints only the owned plan, never other settings values. It does not write. Exit codes: **0** means installed, **1** means changes are needed, and **2** means invalid input or an I/O error. `--apply` explicitly authorizes both changes and backups; setup's plan confirmation provides that authorization interactively. Repeating an apply creates no backups and does not rewrite settings when both resources match.

Both JSON files and destination types are checked before any mutation. Malformed JSON, duplicate keys, non-finite numbers, and a non-object `subagents` value are refused. Symlinked `settings.json`, agent target directories, or `agents` directories are refused, including dangling links. Resolve those layouts deliberately rather than allowing this helper to write through them.

Changed existing settings receive a unique adjacent `settings.json.backup.*` with the original bytes. Settings and their backups use mode `0600`. Conflicting reviewer files or symlinks move to a unique adjacent `reviewer.md.backup.*`; a symlink's referent is not touched. Other agents and the whole `agents` directory are never replaced. Keep backups private and retain them until verification is complete.

Do not run the installer concurrently with another settings writer. Each settings replacement and link publication is atomic, but the two-file install is not a transaction. An I/O failure can leave a partial install; inspect the reported paths and backups before retrying. For rollback, restore only the changed settings/reviewer from their reported backups after checking for later edits. If a target was newly created, remove only that owned target after checking it is still the installed version. Do not restore the whole agent directory.

## Effective runtime policy

The native `pi-subagents` scope checks resolved model candidates, including explicit overrides and fallback chains. `inherit` means the active immediate parent's model, not a fixed provider or model ID. With strict enforcement, an out-of-scope candidate fails rather than being silently dropped. Without a parent model, `inherit` fails closed.

This is not an immutable security boundary. Project `subagents.modelScope` replaces the entire user scope. Project agent definitions win over user definitions, and user/project/provider overrides can replace reviewer fields. External runners use their own model and capability contracts; native scope is not a guarantee for them. Before delegation, the root must verify the effective model/fallbacks, tools, context, and skills. Ask the user before an exception or different-model fallback, document the approved scope, and restore restrictions afterward. Do not disable strict mode merely to clear a launch error.

The reviewer defaults to fresh context, inherits project instructions, and selects only `agent-browser` and `testing-principles` by portable skill discovery. It does not inherit the full skill catalog. Missing skills are warnings in the package, so the root must verify readable paths or supply exact installed SKILL.md paths in the handoff. This component does not install skills or assume a home-directory layout.

The reviewer may inspect Git state and run targeted tests, local repros, and browser checks. It cannot use `edit`, `write`, or `subagent`, and its prompt forbids source fixes. **Bash is not a sandbox**: tests and shell commands can mutate files or contact services. The read-only acceptance role and disabled implementation completion guard describe the review contract; they do not enforce filesystem isolation. Use disposable state, bounded checks, and explicit authorization for side effects. Runtime coordination tools may be added by Pi independently of the five declared tools.

After installation, reload Pi and inspect discovery plus `/subagents-models reviewer` in the existing session before any approved smoke run. Confirm the owned definition, parent-model resolution, fresh context, five declared tools, and selected skills. `--check` verifies only disk state, not live model enforcement or project overrides. Package installation and live evaluation remain separate, explicitly authorized actions.

## Offline validation

```sh
bash -n setup.sh
python3 -m unittest discover -s tests -v
python3 harness/pi/subagents/eval/raw_html_visitor.py
```

The [raw-HTML review case](eval/CASE.md) is a small manual/model evaluation for coverage reasoning, not a full evaluation framework. Running its green fixture tests does not evaluate a reviewer's behavior. Model-backed evaluation requires explicit approval.
