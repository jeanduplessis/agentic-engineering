# Ubiquitous Language

## Skill validation domain

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Skill** | A repo-local agent capability packaged as a directory under the skills collection. | Plugin, command, prompt |
| **Target Skill** | The single **Skill** being validated in one `skill_valid` run. | Subject, candidate, target directory |
| **Skill Validity** | The final boolean judgment that a **Target Skill** satisfies every required **Validation Gate**. | Quality, compliance, certification |
| **Validation Gate** | A required check that must pass before the **Target Skill** can be considered valid. | Step, phase, check |
| **Cheap Gate** | A deterministic **Validation Gate** that does not call live Pi. | Local check, static check |
| **Live Gate** | A **Validation Gate** that depends on a live Pi invocation. | Model check, online check |
| **Fail Fast** | The validation policy of stopping at the first failed required gate. | Short-circuit, early exit |

## Validate-skills gate

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Validate-Skills Skill** | The existing skill that reviews skills against the public skill specification and repo best practices. | Skill validator, static linter |
| **Validate-Skills Gate** | The **Live Gate** that invokes the **Validate-Skills Skill** and treats its machine-readable result as authoritative. | Spec check, validation review |
| **Wrapper Prompt** | A tool-owned prompt that constrains the **Validate-Skills Skill** to validate one **Target Skill** and emit the required sentinel. | Prompt template, adapter prompt |
| **Sentinel Line** | The final non-empty stdout line beginning with `SKILL_VALID_RESULT=` that contains the gate's JSON result. | Marker, final JSON line |
| **Sentinel Result** | The JSON object parsed from the **Sentinel Line** with top-level status, target, and check results. | Validation JSON, parsed result |
| **Check Result** | One item in the **Sentinel Result** proving a specific validate-skills rule passed or failed. | Finding, rule result |

## Evaluation domain

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Eval Manifest** | The skill-owned manifest that describes runnable behavior evaluations for `tools.skill_eval`. | Test manifest, evaluation config |
| **Workflow Suite** | The required executable eval suite that proves the **Target Skill**'s core intended behavior. | Main suite, behavior suite |
| **Regression Suite** | An optional executable eval suite containing known-fixed failures that must remain passing. | Backslide suite, regression tests |
| **Unsupported Suite** | A represented but non-executable suite that does not affect **Skill Validity** in v1. | Ignored suite, metadata suite |
| **With-Skill Configuration** | The eval configuration that runs live Pi with the **Target Skill** force-loaded. | Candidate config, enabled config |
| **Live Eval Gate** | The **Live Gate** that runs required eval suites through `tools.skill_eval` using only the **With-Skill Configuration**. | Behavior gate, eval gate |
| **Strict Real-Run Success** | The eval pass rule requiring every run to be real, non-synthetic, process-passed, and content-passed. | 100% pass, clean eval pass |

## Maintenance documentation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Skill AGENTS.md** | The target skill's maintenance guide for future agents modifying that skill. | Agent guide, context file |
| **Maintenance Section** | A required heading in **Skill AGENTS.md** covering purpose, behavior, validation, or change guidelines. | Required heading, doc section |
| **Concrete Reference** | A mention of a specific target-skill file or declared eval asset that future agents must know about. | File reference, link |

## Runtime outcomes

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Gate-Level Result** | The compact JSON object printed by `skill_valid` to stdout describing overall validity and each gate status. | Summary, report |
| **Failure Artifacts** | Temporary child-run files preserved only when validation fails so failures can be debugged. | Results, report bundle |
| **Live Opt-In** | The explicit user permission required before `skill_valid` may spend live Pi/model calls. | Enable flag, allow live |

## Relationships

- A **Target Skill** has exactly one **Eval Manifest** for `skill_valid` v1.
- A **Target Skill** must have exactly one **Skill AGENTS.md** that satisfies all required **Maintenance Sections**.
- A **Skill Validity** result is true only when every required **Validation Gate** passes.
- The **Validate-Skills Gate** uses exactly one **Wrapper Prompt** and expects exactly one authoritative **Sentinel Line**.
- The **Live Eval Gate** always runs the **Workflow Suite** and also runs the **Regression Suite** when present.
- The **Live Eval Gate** executes only the **With-Skill Configuration** in v1.
- **Failure Artifacts** may exist only for failed runs; successful runs delete temporary child artifacts.

## Example dialogue

> **Dev:** "Does a **Target Skill** pass if the **Eval Manifest** exists but the live eval was skipped?"
>
> **Domain expert:** "No. The **Live Eval Gate** requires **Strict Real-Run Success** for every **With-Skill Configuration** run. Skips fail closed."
>
> **Dev:** "Can the **Validate-Skills Skill** print a Markdown report before the JSON?"
>
> **Domain expert:** "Yes, but the final non-empty line must be the **Sentinel Line**. Only the **Sentinel Result** decides the **Validate-Skills Gate**."
>
> **Dev:** "Is the stdout JSON a persisted report?"
>
> **Domain expert:** "No. It is a **Gate-Level Result** for automation. Only **Failure Artifacts** are preserved, and only when validation fails."

## Flagged ambiguities

- "validate-skills" and "skill_valid" are distinct: **Validate-Skills Skill** is the existing review skill, while `skill_valid` is the orchestrating validation tool.
- "Evals" should mean **Eval Manifest** when discussing specification and **Live Eval Gate** when discussing execution.
- "With skill" should mean **With-Skill Configuration**, not all manifest configurations.
- "Report" should be avoided for `skill_valid` output; use **Gate-Level Result** for stdout JSON and **Failure Artifacts** for preserved debug files.
- "Pass 100%" should be stated as **Strict Real-Run Success** to exclude skipped, process-failed, not-graded, and synthetic runs.
