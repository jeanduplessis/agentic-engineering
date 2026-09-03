# Pi subagents: 0.47.1 → exact 0.62.0

This runbook covers the exact 0.62.0 upgrade. The [original cutover plan](switch-to-nicobailon-pi-subagents.md) remains historical. Root owns home-file changes and package replacement; finish repository edits and drain children before replacing the running package.

## Installation and verification record

The home-local npm manifest, lockfile, and installed package are pinned to `0.62.0`. The only dependency addition is `acorn@8.18.0`. Mission storage is explicitly kept at the old project-relative location; the loader, custom agents, frontend guard, and Pi settings are unchanged.

Offline checks passed with Pi `0.84.4` and Node `24.14.1`:

- The real Pi loader accepted the existing wrapper and frontend guard. Session startup registered exactly `subagent`, `bg_wait`, and `subagent_supervisor`; parent resource discovery returned the installed skill/prompt directories. Child mode exposed neither parent tools nor those resources.
- `validate` accepted a normal workflow and rejected invalid JavaScript without launching a child. Agent listing, doctor, and model-listing actions ran in an isolated configuration with no provider authentication; this does not verify provider/model availability.
- Custom agents retained their tools, skills, model, and guard configuration. The frontend hooks blocked native-file `edit`/`write`, permitted TSX, and left the root role unrestricted. The builtin reviewer remained read-only.
- The configured mission path resolved to the original store. Its one pre-upgrade record parsed under 0.62.0, and original mission bytes were unchanged.
- All 99 repository Python tests passed. Preservation checks confirmed unrelated workspace files and the Git index were unchanged.

Verification scripts and logs are retained under the snapshot's `verification/` directory. Already-running Pi sessions still need a full restart. Live child execution, provider access, and supervisor/completion round trips were not tested; the separate live gate below remains open.

## Preserve the installation boundary

The existing home-local loader, `~/.pi/agent/extensions/subagent/index.ts`, imports `../../npm/node_modules/pi-subagents/index.ts`. It also registers the package's skills and prompts through `resources_discover` for the parent session. Keep this loader unchanged. Do **not** add a `settings.json` `packages` entry or run `pi install` alongside it: that would load the extension twice.

Keep the custom Firecrawl `researcher`, `frontend`, and `frontend-path-guard.ts` unchanged. Keep model policy, agent overrides, `setup.sh`, and unrelated home/repository files unchanged. The [root policy](../APPEND_SYSTEM.md) still requires `subagent` with `workflowScript` for every child and forbids concurrent writers on overlapping files. Only its wait-tool name changes to `bg_wait`.

## Apply the upgrade

1. Record the current state and keep the pre-upgrade snapshot at `~/.pi/agent/backups/pi-subagents-0.47.1-to-0.62.0-20260901-153919/`. It includes dirty/untracked repository originals, home configuration, and the npm installation. Stop launching work; let children finish or stop them deliberately, then confirm no child processes remain before the package swap.
2. Merge this one setting into `~/.pi/agent/extensions/subagent/config.json`, preserving all other keys:

   ```json
   {
     "artifactDir": "session",
     "toolDescriptionMode": "full",
     "missions": {
       "directory": ".pi/subagents/missions"
     }
   }
   ```

   `artifactDir` and `toolDescriptionMode` above are existing values, not new defaults. Set `missions.directory` explicitly to keep each project's existing missions **in place**. The new default is `~/.pi/agent/missions/projects/<project-hash>/`; there is no automatic migration. Do not move or copy mission records into that new store.
3. Replace only the home-local npm package with the exact approved version:

   ```sh
   npm --prefix "$HOME/.pi/agent/npm" install --save-exact --ignore-scripts pi-subagents@0.62.0
   ```

4. Restart Pi. Do not rely on an already-running session to pick up new tools, policy, skills, prompts, or configuration.

## Compatibility notes

- `bg_wait` is the only registered wait tool; `subagent_wait` was removed. A `window_elapsed` response is not completion or failure: the work is still running. Use status and returned run identities rather than polling in a loop.
- `prompts.render`, `turnBudget`, and legacy chain surfaces are retired. Use explicit task text in `workflowScript` with `runs.run`/`runs.all`; do not revive top-level `chain`, `tasks`, or `parallel` inputs or old chain-management helpers. Keep writer tasks bounded; do not substitute hard tool/token budgets for removed turn budgets.
- When later steps need a durable report, set the child's `output` field. Use returned `outputReference`, `outputPathMapping`, or `artifactPaths`, not a guessed filename or literal path returned by the script. Read-only children can return the report in their final response for runtime persistence.

## Validation gates

These are checks to run and record, not pass claims. Do not run model-backed checks as part of the non-model gate.

**Non-model gate:**

- Confirm the installed package version and npm manifest/lockfile pin are exactly `0.62.0`; inspect the npm diff for unrelated dependency changes.
- Compare the loader, custom agents, frontend guard, settings/model policy, and existing mission files with the snapshot. Only the intended config setting and npm installation should change in home. Confirm old mission paths still exist and the config retains `artifactDir: "session"` and `toolDescriptionMode: "full"`.
- After restart, check `/subagents-doctor`, agent listing, and model listing without launching a child. Confirm one extension registration, parent skill/prompt discovery, `bg_wait` present, and `subagent_wait` absent. Check `mission.list`/`mission.show` can read an existing mission in place; do not resume it as a test.
- Use `subagent` with `action: "validate"` to check a small `workflowScript` without launching children. Confirm the Firecrawl researcher definition and frontend guard loading remain intact.
- Check repository diffs against the pre-task originals as well as HEAD. Run `git diff --check`, check local documentation links, and confirm no staged or unrelated changes were introduced.

**Separate live smoke gate — requires explicit approval:** In a disposable project, exercise one small background workflow, `status`/`bg_wait`, completion delivery, and a returned output path. Separately check Firecrawl research and frontend allowed/blocked paths if approved. Record lifecycle completion and acceptance evidence separately; non-model success alone does not prove child execution, provider access, or guard behavior.

## Rollback

Stop launching work and drain or deliberately stop children; confirm their processes have exited. Preserve any post-upgrade reports and mission records before restoring anything. Use the pre-upgrade snapshot above, **not HEAD**, because the workspace already had user edits.

Restore only files changed by this upgrade: selectively restore the repository policy/changelog/historical note, undo only the new runbook, and restore the home subagent config plus the saved npm manifest, lockfile, and installation together. Check for later edits before each restore; preserve them rather than replacing whole directories blindly. Do not restore all of Pi home or `.pi/`, overwrite new missions, or copy old mission snapshots over live records. If a mission written by 0.62.0 cannot be read by 0.47.1, retain it unchanged for later recovery instead of attempting an unverified downgrade conversion. Restart Pi and repeat the non-model checks against 0.47.1 and its original policy; any live smoke still needs separate approval.

## Versioned references

The inspected `0.62.0` package manifest and changelog establish the target and removals. Upstream references for that tag: [configuration](https://github.com/nicobailon/pi-subagents/blob/v0.62.0/docs/configuration.md), [missions](https://github.com/nicobailon/pi-subagents/blob/v0.62.0/docs/missions.md), and [tool reference](https://github.com/nicobailon/pi-subagents/blob/v0.62.0/docs/tool-reference.md). Use the installed package's skill and guides for invocation details.
