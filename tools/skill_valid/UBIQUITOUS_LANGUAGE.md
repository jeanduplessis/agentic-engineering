# Ubiquitous Language

## Skill validation domain

- **Skill**: A repo-local agent capability packaged as a directory under the skills collection. Avoid aliases:
  Plugin, command, prompt.

- **Target Skill**: The single **Skill** being validated in one `skill_valid` run. Avoid aliases: Subject,
  candidate, target directory.

- **Skill Validity**: The final boolean judgment that a **Target Skill** satisfies every required **Validation
  Gate**. Avoid aliases: Quality, compliance, certification.

- **Validation Gate**: A required check that must pass or emit an allowed warning before the **Target Skill**
  can be considered valid. Avoid aliases: Step, phase, check.

- **Cheap Gate**: A deterministic **Validation Gate** that does not call live Pi. Avoid aliases: Local check,
  static check.

- **Live Gate**: A **Validation Gate** that depends on a live Pi invocation. Avoid aliases: Model check,
  online check.

- **Skill Spec Gate**: The deterministic **Cheap Gate** keyed `skill_spec` that parses `SKILL.md` and checks
  Pi skill compatibility, resource references, and repo-contract rules before live review. Avoid aliases: Static
  skill lint, spec validator.

- **Prerequisite Accumulation**: The validation policy of checking all deterministic prerequisite gates before
  live work so one result can report multiple missing requirements. Avoid aliases: Bulk lint, exhaustive
  validation.

- **Live Gate Short-Circuit**: The validation policy of skipping live gates when prerequisite gates fail, and
  stopping after the first failed live gate to avoid unnecessary model cost. Avoid aliases: Fail fast, early
  exit.

- **Warn Gate Status**: A non-blocking gate status for deterministic advisory findings that remain visible
  while allowing **Skill Validity** if no blocking gate fails. Avoid aliases: Soft pass, pass with warnings.

## Validate-skills gate

- **Validate-Skills Skill**: The existing skill that reviews skills against the public skill specification and
  repo best practices. Avoid aliases: Skill validator, static linter.

- **Validate-Skills Gate**: The **Live Gate** that invokes the **Validate-Skills Skill** and treats its
  machine-readable result as authoritative. Avoid aliases: Spec check, validation review.

- **Wrapper Prompt**: A tool-owned prompt that constrains the **Validate-Skills Skill** to validate one
  **Target Skill** and emit the required sentinel. Avoid aliases: Prompt template, adapter prompt.

- **Sentinel Line**: The final non-empty stdout line beginning with `SKILL_VALID_RESULT=` that contains the
  gate's JSON result. Avoid aliases: Marker, final JSON line.

- **Sentinel Result**: The JSON object parsed from the **Sentinel Line** with top-level status, target, and
  check results. Avoid aliases: Validation JSON, parsed result.

- **Check Result**: One item in the **Sentinel Result** proving a specific validate-skills rule passed or
  failed. Avoid aliases: Finding, rule result.

## Evaluation domain

- **Eval Manifest**: The skill-owned manifest that describes runnable behavior evaluations for
  `tools.skill_eval`. Avoid aliases: Test manifest, evaluation config.

- **Workflow Suite**: The required executable eval suite that proves the **Target Skill**'s core intended
  behavior. Avoid aliases: Main suite, behavior suite.

- **Regression Suite**: An optional executable eval suite containing known-fixed failures that must remain
  passing. Avoid aliases: Backslide suite, regression tests.

- **Unsupported Suite**: A represented but non-executable suite that does not affect **Skill Validity** in v1.
  Avoid aliases: Ignored suite, metadata suite.

- **With-Skill Configuration**: The eval configuration that runs live Pi with the **Target Skill**
  force-loaded. Avoid aliases: Candidate config, enabled config.

- **Live Eval Gate**: The **Live Gate** that runs required eval suites through `tools.skill_eval` using only
  the **With-Skill Configuration**. Avoid aliases: Behavior gate, eval gate.

- **Strict Real-Run Success**: The eval pass rule requiring every run to be real, non-synthetic,
  process-passed, and content-passed. Avoid aliases: 100% pass, clean eval pass.

## Maintenance documentation

- **Skill AGENTS.md**: The target skill's maintenance guide for future agents modifying that skill. Avoid
  aliases: Agent guide, context file.

- **Maintenance Section**: A required heading in **Skill AGENTS.md** covering purpose, behavior, validation,
  or change guidelines. Avoid aliases: Required heading, doc section.

- **Concrete Reference**: A mention of a specific target-skill file or declared eval asset that future agents
  must know about. Avoid aliases: File reference, link.

## Runtime outcomes

- **Gate-Level Result**: The compact JSON object printed by `skill_valid` to stdout describing overall
  validity and each gate status. Avoid aliases: Summary, report.

- **Failure Artifacts**: Temporary child-run files preserved only when validation fails so failures can be
  debugged. Avoid aliases: Results, report bundle.

- **Live Opt-In**: The explicit user permission required before `skill_valid` may spend live Pi/model calls.
  Avoid aliases: Enable flag, allow live.

- **LLM Optimal Check Gate**: The deterministic gate keyed `llm_optimal_check` that runs
  `tools.llm_optimal_check` on the **Target Skill**'s `SKILL.md`. Avoid aliases: Smell-test gate, prompt lint.

- **Compact Optimization Report**: The `llm_optimal_check` gate details containing checker status, score,
  useful metrics, and all findings while excluding bulky preview/body fields. Avoid aliases: Embedded report,
  optimization summary.

## Relationships

- A **Target Skill** has exactly one **Eval Manifest** for `skill_valid` v1.

- A **Target Skill** must have exactly one **Skill AGENTS.md** that satisfies all required **Maintenance Sections**.

- A **Skill Validity** result is true only when every required **Validation Gate** passes or emits an allowed **Warn Gate Status**.

- **Prerequisite Accumulation** reports deterministic missing requirements together before any live Pi/model call.

- The **Skill Spec Gate** owns deterministic Pi SKILL.md compatibility/resource validation; the **Validate-Skills Gate** owns qualitative judgment after live opt-in.

- The **LLM Optimal Check Gate** analyzes only `SKILL.md` in v1; `warn` is non-blocking, while `fail` and tool errors block live gates.

- The **Validate-Skills Gate** uses exactly one **Wrapper Prompt** and expects exactly one authoritative **Sentinel Line**.

- The **Live Eval Gate** always runs the **Workflow Suite** and also runs the **Regression Suite** when present.

- The **Live Eval Gate** executes only the **With-Skill Configuration** in v1.

- **Failure Artifacts** may exist only for failed runs; successful runs delete temporary child artifacts.

## Example dialogue

- **Dev:** Does a **Target Skill** pass if the **Eval Manifest** exists but the live eval was skipped?

  **Domain expert:** No. The **Live Eval Gate** requires **Strict Real-Run Success** for every
  **With-Skill Configuration** run. Skips fail closed.

- **Dev:** Can the **Validate-Skills Skill** print a Markdown report before the JSON?

  **Domain expert:** Yes, but the final non-empty line must be the **Sentinel Line**. Only the
  **Sentinel Result** decides the **Validate-Skills Gate**.

- **Dev:** Is the stdout JSON a persisted report?

  **Domain expert:** No. It is a **Gate-Level Result** for automation. Only **Failure Artifacts** are preserved,
  and only when validation fails.

## Flagged ambiguities

- "validate-skills" and "skill_valid" are distinct: **Validate-Skills Skill** is the qualitative review skill,
  while `skill_valid` is the orchestrating validation tool and owns the **Skill Spec Gate**.

- "Evals" should mean **Eval Manifest** when discussing specification and **Live Eval Gate** when discussing execution.

- "With skill" should mean **With-Skill Configuration**, not all manifest configurations.

- "Report" should be avoided for `skill_valid` output; use **Gate-Level Result** for stdout JSON and **Failure Artifacts** for preserved debug files.

- "Pass 100%" should be stated as **Strict Real-Run Success** to exclude skipped, process-failed, not-graded, and synthetic runs.
