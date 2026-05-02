---
description: "Migrate a repo from original beads bd to beads_rust br"
argument-hint: "[repo-path] [--rename-prefix-to-br] [notes]"
---

Migrate an existing repo from original beads (`bd`) to beads_rust (`br`).

Arguments: $ARGUMENTS

Interpret arguments as optional repo path plus options/notes.
If no repo path is provided, use the current working directory.
Default to preserving existing issue IDs/prefixes.
Rename IDs to `br-*` only when the user passes `--rename-prefix-to-br` or explicitly asks.

## Safety rules

Approval gates:

- Do not silently install `br`, initialize beads, repair data, import, rebuild, rename IDs, or commit.
- Before any mutating step, summarize the plan and ask for confirmation.
- After any `br sync --import-only` failure, stop and reconfirm before changing recovery strategy.

Data safety:

- Name the target `.beads/` directory before mutating.
- If migrating a nested package, keep root `.beads/` out of scope unless the target repo path is root.
- Back up the target `.beads/` before changing it.
- Preserve target `.beads/issues.jsonl` as the import source.
- Quarantine old `bd` local metadata before `br init` only after confirmation and backup.
- Do not keep using both `bd` and `br` on the same repo after migration.

Sync/git rules:

- Do not run bare `br sync`.
- Treat `br` as non-invasive: it never commits, pushes, pulls, installs hooks, or runs git.
- Use `br sync --flush-only` only for explicit final JSONL export before staging/committing `.beads/`.

## 1. Preflight

Run read-only checks from the target repo/package path:

```bash
pwd
git rev-parse --show-toplevel
git status --short
br --version
ls -la .beads
ls -la .beads/issues.jsonl
```

State the target `.beads/` path explicitly. In monorepos, distinguish package-local `.beads/` from root `.beads/` before any mutation.

If `br` is unavailable, tell the user and ask before installing.
If `.beads/issues.jsonl` is missing or appears stale, explain that `br` imports JSONL.
Ask before using old `bd` to export/sync.
Old `bd sync` may perform git operations depending on version/config.

Inspect existing IDs/prefixes without modifying files:

```bash
python3 - <<'PY'
import json, pathlib, re
p = pathlib.Path('.beads/issues.jsonl')
prefixes = {}
for line in p.read_text().splitlines():
    if not line.strip():
        continue
    i = json.loads(line).get('id', '')
    m = re.match(r'([A-Za-z0-9_]+)-', i)
    if m:
        prefixes[m.group(1)] = prefixes.get(m.group(1), 0) + 1
print(prefixes)
PY
```

Recommend preserving the dominant existing prefix unless the user explicitly wants `br-*` IDs.

Pre-scan old `bd` comment IDs before import:

```bash
python3 - <<'PY'
import json, pathlib
p = pathlib.Path('.beads/issues.jsonl')
bad = []
for line_no, line in enumerate(p.read_text().splitlines(), 1):
    if not line.strip():
        continue
    issue = json.loads(line)
    for idx, c in enumerate(issue.get('comments') or []):
        cid = c.get('id')
        if cid is not None and not isinstance(cid, int):
            bad.append((line_no, issue.get('id'), idx, cid))
print({'non_integer_comment_ids': len(bad), 'samples': bad[:10]})
PY
```

If non-integer `comments[].id` values are found, include a confirmed recovery plan.
The plan must map legacy string/UUID comment IDs to integer IDs while preserving comment text, author, timestamps, and issue IDs.

## 2. Confirm migration plan

Before mutating, present:

- target repo path;
- current git status;
- target `.beads/` path and any root/package `.beads/` paths that are out of scope;
- `.beads/` backup path;
- whether issue IDs will be preserved or renamed;
- whether non-integer legacy comment IDs need normalization;
- whether docs/agent instructions will be updated;
- old `bd` local-state files to quarantine before `br init`;
- expected repo quality gate before commit;
- whether final export/staging/commit should happen after verification.

Ask for confirmation.

## 3. Back up and import into br

After confirmation:

```bash
backup="/tmp/beads-bd-backup-$(basename "$PWD")-$(date +%Y%m%d%H%M%S)"
quarantine="$backup-quarantine"
cp -a .beads "$backup"
mkdir -p "$quarantine"
echo "$backup"
```

Quarantine old `bd` local state before `br init`, preserving `.beads/issues.jsonl`:

```bash
for p in metadata.json config.yaml export-state.json backup embeddeddolt hooks .local_version; do
  if [ -e ".beads/$p" ]; then
    mkdir -p "$(dirname "$quarantine/$p")"
    mv ".beads/$p" "$quarantine/$p"
  fi
done
```

Move additional `.beads/` files only after a fresh confirmation.

If approved, normalize legacy string/UUID comment IDs before import:

```bash
cp .beads/issues.jsonl "$quarantine/issues.before-comment-id-normalize.jsonl"
python3 - <<'PY'
import json, pathlib
p = pathlib.Path('.beads/issues.jsonl')
out = []
for line in p.read_text().splitlines():
    if not line.strip():
        continue
    issue = json.loads(line)
    comments = issue.get('comments') or []
    used = {c.get('id') for c in comments if isinstance(c.get('id'), int)}
    next_id = 1
    for c in comments:
        if c.get('id') is None or isinstance(c.get('id'), int):
            continue
        while next_id in used:
            next_id += 1
        c['id'] = next_id
        used.add(next_id)
    out.append(json.dumps(issue, separators=(',', ':'), ensure_ascii=False))
p.write_text('\n'.join(out) + ('\n' if out else ''))
PY
```

Preserve comment text, author, timestamps, and issue IDs. Do not run this unless the pre-scan found non-integer comment IDs and the user approved normalization.

Preserve existing prefix/IDs, replacing `<prefix>` with the dominant prefix from JSONL:

```bash
br init --prefix <prefix>
br sync --import-only --json
```

Or rename imported IDs to the configured `br` prefix only if explicitly requested:

```bash
br init --prefix br
br sync --import-only --rename-prefix --json
```

If import fails, stop.
Report the exact error, backup path, and quarantine path.
Ask for confirmation before:

- trying a different recovery plan;
- moving more `.beads/` files;
- using `--force` or `--rebuild`;
- manually editing JSONL;
- running repair commands.

## 4. Verify br state

Run:

```bash
br info
br sync --status --json
br ready --json
br doctor --json > /tmp/br-doctor.json
```

Summarize `br doctor --json` without flattening it to pass/fail:

```bash
python3 - <<'PY'
import json

d = json.load(open('/tmp/br-doctor.json'))
checks = d.get('checks') or []
non_ok = [c for c in checks if c.get('status') not in (None, 'ok', 'pass', 'passed')]
print({
    'ok': d.get('ok'),
    'workspace_health': d.get('workspace_health'),
    'reliability_anomalies': (d.get('reliability_audit') or {}).get('anomalies'),
    'non_ok_checks': non_ok,
})
PY
```

Do not call doctor output clean if warnings, recoverable health, degraded health, or reliability anomalies remain.

Verify the full imported issue count, including closed and deferred issues:

```bash
br list --all --deferred --limit 0 --json > /tmp/br-issues.json
python3 - <<'PY'
import json

d = json.load(open('/tmp/br-issues.json'))
issues = d.get('issues', d if isinstance(d, list) else [])
print({
    'total': d.get('total', len(issues)) if isinstance(d, dict) else len(issues),
    'sample_ids': [i.get('id') for i in issues[:10]],
})
PY
```

Do not rely on plain `br list --json` for count verification; it omits closed issues by default.

Spot-check one or more known issues:

```bash
br show <known-issue-id> --json
```

If IDs were renamed, use a renamed ID from the import output or inclusive list summary.

## 5. Update docs and agent instructions

Search for old references:

```bash
rg -n '\bbd\b|bd-[A-Za-z0-9]' . --glob '!.git/**'
```

Apply mechanical replacements where they describe current repo operations:

```text
bd ready              -> br ready
bd list               -> br list
bd show <id>          -> br show <id>
bd create             -> br create
bd update             -> br update
bd close              -> br close
bd dep add            -> br dep add
bd stats              -> br stats
bd sync               -> br sync --flush-only plus explicit git add/commit when committing .beads/
```

Also update common CLI differences:

```text
bd comment <id> ...       -> br comments add <id> --message ... --json
bd comments <id>          -> br comments list <id> --json
bd assign <id> <agent>    -> br update <id> --assignee <agent> --json
bd dep relate A B         -> br dep add A B --type related --json
bd doctor --agent --json  -> br doctor --json
```

Remove or rewrite obsolete assumptions:

- `bd`/daemon/RPC mode;
- automatic git commits/pushes/pulls;
- hook installation as part of normal issue tracking;
- instructions to run bare `br sync`;
- instructions to hand-edit `.beads/*.jsonl` for normal workflows.

Add the key behavioral note wherever needed:

```markdown
`br` is non-invasive: it updates `.beads/` only and never runs git. Run `br sync --flush-only` only for final JSONL export before staging/committing `.beads/`.
```

Re-run the search until no unintended `bd` command references remain. Preserve historical mentions only when clearly labeled as history/migration context.

## 6. Ignore local runtime artifacts

After `br init`, review `.beads/` status before staging:

```bash
git status --short .beads/
```

Ensure local-only artifacts are ignored before staging `.beads/`:

```text
beads.db
beads.db-*
*.db-wal
*.db-shm
.write.lock
.br_history/
.br_recovery/
interactions.jsonl
```

Update `.beads/.gitignore` only after confirmation.

## 7. Doctor cleanup, if needed

Before deleting local recovery or sidecar artifacts, copy `.beads/` to a temp directory and test cleanup there.
Apply only the minimal proven cleanup to the real repo after confirmation.

If cleaning `.beads/.br_recovery/`, verify in this order:

1. Remove stale recovery artifacts only after approval.
2. Run `br doctor --json`.
3. Inspect non-OK checks, `workspace_health`, and `reliability_audit.anomalies`.
4. Avoid extra `br sync --status` or `br list` calls unless you rerun cleanup or state that they may recreate WAL/recovery artifacts.

Do not escalate warning-only doctor output to repair when all are true:

- `ok: true`;
- issue counts match JSONL;
- sync dirty count is zero;
- warnings are limited to local recovery/sidecar artifacts.

In that case, do not run `br doctor --repair`, `br sync --import-only --rebuild`, or manual JSONL edits without fresh explicit approval.

## 8. Final export, quality gate, and optional commit

Ask: "Finalize with `br sync --flush-only` and optional commit?"

When verification passes and the user confirms final export/staging:

```bash
br sync --flush-only
git status --short .beads/
git diff .beads/
git add .beads/
```

Stage changed docs/agent instructions too.
Run the repo quality gate before committing if one is known/configured.
If generated `br` metadata fails formatting, apply only the minimal formatter-compatible change and restage.

After every `git add` in nested package work, verify staged scope:

```bash
git diff --cached --name-status
```

If unrelated files are staged, run `git reset` and restage exact target paths from the current cwd, or use `git -C <repo-root> add <repo-root-relative-paths>`.

Commit only if the user confirmed:

```bash
git commit -m "Migrate beads tracking to br"
```

If the user does not want a commit, leave changes unstaged or staged as requested and report exact next commands.

## 9. Final response

Report:

- backup path;
- import mode used: preserved IDs or renamed to `br-*`;
- verification commands run and results;
- doctor summary: `ok`, `workspace_health`, `reliability_audit.anomalies`, and non-OK checks;
- residual warning class, if any;
- docs/agent files updated;
- comment-ID normalization, if applied;
- repo quality gate run and result;
- whether `.beads/` was exported with `br sync --flush-only`;
- ignored/quarantined local-only artifacts;
- commit hash, or exact remaining manual steps.
