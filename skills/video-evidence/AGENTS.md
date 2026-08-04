# AGENTS.md — video evidence skill maintenance

## Purpose

Maintain `SKILL.md` as the destination-neutral runtime contract for producing truthful, concise video evidence. Keep journey validation, recording, semantic editing, technical inspection, privacy review, and artifact reporting here. Keep GitHub and other publication workflows outside this skill.

## How the skill works

`SKILL.md` tells the assistant to define a narrow proof, prepare deterministic state, dry-run the journey, record a clean take, inspect and truthfully trim it, validate playback/privacy/format, and return a structured artifact record. A separate publishing skill may consume that record.

## Safety and behavior contracts

- Require a successful dry run before recording.
- Keep generated media outside the repository by default.
- Preserve chronology and one-take provenance; edits may remove dead time but must not manufacture success.
- Require visual inspection plus full-file decode validation.
- Prefer H.264 MP4 with `yuv420p` and `+faststart` for broad playback compatibility.
- Never expose credentials, session state, production data, or unrelated private data.
- Keep destination-specific upload, visibility, authentication, and mutation instructions out of `SKILL.md`.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. They use a no-command planning scenario and deterministic checks for preparation, recording separation, editing integrity, media validation, and the artifact output contract.

Run the focused validator from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/video-evidence
```

Run repository Python tests when changing framework-facing eval files:

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

Do not run live harness or model-backed evals without explicit approval.

## Change guidelines

- Keep commands compatible with the current agent-browser workflow; retain the instruction to load `agent-browser skills get core --full` before browser work.
- Keep FFmpeg examples semantically safe rather than over-automating cut decisions.
- Keep the output contract stable enough for independent publishing skills to consume.
- Update deterministic evals whenever the artifact, integrity, privacy, or validation contract changes.
