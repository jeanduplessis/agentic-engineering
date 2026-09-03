# AGENTS.md — human-writing skill maintenance

## Purpose

Maintain `SKILL.md` as automatic writing guidance for durable, human-facing prose. It is not a humanization command,
an authorship detector, or a general assistant-response style guide.

## How the skill works

The description selects artifact creation and revision, including drafts delivered in chat for use elsewhere.
Ordinary conversation, progress updates, code/data transformations, and agent-facing instructions are excluded.
The body preserves meaning and evidence, matches the writer and audience, and treats stylistic patterns as contextual
editing hints. The primary task owns tools, delivery, and reporting; the skill adds no invocation workflow.
Copy-ready output contains only the artifact. Editorial commentary is allowed when requested, outside the artifact;
unchanged text is returned verbatim rather than accompanied by a no-change explanation.

`user-invocable: false` is an optional harness hint. The description and body carry the complete behavior when
that field is ignored. Keep automatic model discovery enabled in Pi.

## Eval and validation

`evals/manifest.json` contains declarative workflow cases for drafting artifacts, factual limits, missing evidence,
voice preservation, copy-ready delivery, and migration history. Its regression suite owns the confirmed current-state
README failure and two Opus editorial-commentary failures, without duplicating those cases in workflow.
`evals/evidence/readme-history.json` and `evals/evidence/editorial-notes.json` retain the real responses, failed checks,
input skill hashes, and traced confirmation that the models read the skill.

Prompts request ordinary writing tasks rather than invoking the skill as a command. The founding-period fixture
explicitly marks the decade as an unverified estimate; preserving uncertainty about the exact date alone is insufficient.
The supported-operations fixture explicitly makes its list exhaustive. Workflow/regression cases have no copy fixtures or custom graders; the trigger suite uses `evals/fixtures/trigger` with `cache.py` and `design.md`.
`evals/test_checks.py` tests semantic-equivalence boundaries, copy-ready delivery, and recorded regressions with fixed
samples, not models. The `copy-ready-unchanged-sentence` and `copy-ready-rotation-instructions` workflow cases are separate
from the original failure prompts and can be selected for a bounded repeated check. Set the case/model/repetition budget
before live execution; do not rerun until passing or change checks without retaining the original results.

The with-skill configuration exposes the target skill; the baseline omits it. Pi's explicit skill path registers it
for discovery rather than guaranteeing a body read. Inspect read events before attributing a result to the full skill.
Checks cover specific observable failures, not complete factual fidelity or writing quality. The trigger suite has three
positive and seven negative scope cases with complete inputs. It uses Pi's natural, target-only read-only profile and its own
`discovery` configuration; successful target reads and avoidance are graded from observed events, not response text.
This profile does not measure competition among skills or prove that the loaded instructions were followed.

When a live output reveals a grader false positive, preserve the original grades, add valid and invalid checker samples,
and label any regrading of saved outputs separately. Do not present regrading as a new model run.

From the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/human-writing
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
PYTHONPATH=skill-factory python3 -m unittest discover -s skills/human-writing/evals -p 'test_*.py' -v
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/human-writing/evals/manifest.json workflow \
  --results /tmp/human-writing-eval/workflow --require-real
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/human-writing/evals/manifest.json regression \
  --results /tmp/human-writing-eval/regression --require-real
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/human-writing/evals/manifest.json trigger \
  --configuration discovery --results /tmp/human-writing-trigger-new-run --require-real
```

Use a new/empty trigger results directory each time; the runner preserves frozen inputs and refuses to overwrite evidence.
`skill_valid --include-trigger` also checks this suite and runs it only with live opt-in. Trigger failure promotion into
workflow regressions is rejected; retain the trace and add a natural trigger case instead.

The suite commands should skip real runs without live opt-in. Run live harness/model evaluations only with explicit
approval; skipped runs and synthetic checks are not evidence of skill effectiveness. The optimization check may
flag the intentional filler phrase in the first Before example (TC001); retain that teaching example rather than
optimizing to clear the warning.

## Change guidelines

- Preserve artifact-only scope and automatic, guidance-only use. Do not add modes, flags, mandatory audits, or scores.
- Keep facts, uncertainty, obligations, exhaustive scope, technical meaning, and exact non-prose content ahead of style.
- Distinguish selecting relevant notes for a new artifact from preserving substantive claims during a phrasing pass.
- Accept equivalent dates, technical-term hyphenation, and evidence-gap phrasing in checks; do not weaken factual constraints.
- Do not add blanket word/punctuation bans, detector targets, or instructions to manufacture personality.
- Examples must preserve the supplied information. For no-change examples, show the unchanged text as the output,
  not an editorial explanation that a model might append to the artifact.
- Coordinate `SKILL.md` and `evals/manifest.json` when scope or behavior changes. Prefer built-in checks over new tooling.

## Editorial references

These informed the guidance; none is a runtime dependency or a rulebook to import wholesale:

- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing): original pattern catalog.
- [no-ai-slop](https://github.com/petergyang/no-ai-slop): minimal edits, voice preservation, and generic filler.
- [humanizer](https://github.com/blader/humanizer): preservation, genre-sensitive voice, and false-positive safeguards.
- [slopbeth](https://github.com/ehmo/slopkit/tree/main/skills/slopbeth): artifact/chat boundary and preservation of obligations.
- [anti-slop](https://github.com/elithrar/dotfiles/blob/main/.agents/skills/anti-slop/SKILL.md): restraint and deliberate rhetoric.
- [soundshuman](https://github.com/aashaexo/soundshuman): current-state documentation versus change-oriented artifacts.
