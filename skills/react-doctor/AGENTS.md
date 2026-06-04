# AGENTS.md — react-doctor skill maintenance

## Purpose

Maintain `SKILL.md` as the shared Pi/OpenCode runtime contract for using the `react-doctor` CLI after React code changes and during React codebase cleanup. The skill should tell agents when to run the analyzer, which command to use, and how to respond to score regressions or reported issues.

## How the skill works

`SKILL.md` documents two paths:

- changed React code: run `npx -y react-doctor@latest . --verbose --diff` and confirm the score did not regress;
- general cleanup: run `npx -y react-doctor@latest . --verbose` and fix errors before warnings.

Keep the commands exact unless the upstream `react-doctor` CLI contract changes.

## Eval and validation

`evals/manifest.json` declares workflow smoke cases for the changed-code and cleanup paths. The cases ask for no-command plans so live harness validation can check the skill contract without installing or running the external analyzer.

Run deterministic validation from the repository root:

```sh
python3 -m tools.skill_valid skills/react-doctor
```

Run live harness/model validation only with explicit approval:

```sh
./tools/skill_valid/skill_validate.sh skills/react-doctor --allow-live --harness kilo
```

## Change guidelines

- Keep `SKILL.md` concise and command-focused.
- Preserve the changed-code default command: `npx -y react-doctor@latest . --verbose --diff`.
- Preserve the cleanup command without `--diff`: `npx -y react-doctor@latest . --verbose`.
- Update `evals/manifest.json` when command names, flags, score-regression behavior, or severity-fix ordering changes.
- Do not add project-specific paths or assumptions; this skill must stay portable across React repositories.
