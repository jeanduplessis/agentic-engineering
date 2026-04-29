# Ubiquitous Language

## Skill evaluation

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Skill** | A reusable agent capability described by skill metadata and instructions, optionally with references, scripts, templates, or other bundled resources. | Prompt, command, helper |
| **Skill Eval Framework** | The shared system that runs, captures, grades, compares, and reports skill evaluations across the repository. | Eval approach, eval system, test harness |
| **Central Runner** | The canonical repo-level executable entry point for running skill evals with consistent schemas and result layout. | Runner script, per-skill runner, eval script |
| **Skill-local Eval Data** | The datasets, fixtures, rubrics, and optional custom checks owned by a specific skill. | Skill tests, eval files, datasets |
| **Skill Maintainer** | A person or agent responsible for improving a skill while preserving its expected behavior. | Developer, author, evaluator |
| **Vertical Slice** | A minimal end-to-end implementation that proves the framework path from eval definition through execution, grading, comparison, and reporting. | Tracer bullet, MVP, prototype |
| **PRD Epic** | A beads epic that records the approved product requirements for a planned capability. | PRD task, tracking issue, parent task |

## Eval suites and cases

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Eval Manifest** | A skill-local index that declares which eval suites belong to a skill and how the runner should load them. | Manifest, config, eval index |
| **Eval Suite** | A named collection of eval cases with a shared purpose, such as workflow, trigger, capability, or regression. | Dataset, test suite, eval file |
| **Eval Case** | One prompt plus its expected grading rules, inputs, suite metadata, and execution requirements. | Test case, prompt, scenario |
| **Golden Prompt Set** | A small curated set of high-value eval cases used to measure core skill behavior. | Prompt set, sample prompts, benchmark prompts |
| **Workflow Eval** | An eval case that tests whether a skill improves task behavior once the skill is intentionally made available. | Behavior eval, with-skill eval, output eval |
| **Trigger Eval** | An eval case that tests whether the agent naturally selects or avoids a skill for a user prompt. | Invocation eval, description eval, selection eval |
| **Capability Suite** | A suite of hard or aspirational eval cases used to measure skill growth over time; currently represented in manifests but not executed by the central runner. | Hard-case suite, improvement suite |
| **Regression Suite** | A suite of known-fixed eval cases that should stay near 100% passing; currently executed through the same case runner as workflow suites. | Safety suite, backslide suite |
| **Regression Case** | An eval case created from a real observed failure to prevent that failure from recurring. | Failure case, bug repro, old failure |
| **Negative Control** | A trigger eval case where the skill should not be selected despite adjacent vocabulary or apparent relevance. | Negative eval, should-not-trigger case, false-positive test |

## Execution and isolation

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Sandbox** | An isolated per-run workspace used to prevent dirty state or previous runs from affecting an eval. | Workspace, temp dir, environment |
| **Fixture** | A predefined starting state copied or materialized into a sandbox before an eval run begins. | Repo fixture, test repo, sample project |
| **Empty Fixture** | A trivial fixture that provides an isolated sandbox without copying a prebuilt project state. | No fixture, temp workspace |
| **Configuration** | A named execution variant being compared, such as with-skill, without-skill, or previous-skill. | Baseline, mode, variant |
| **With-skill Configuration** | A configuration where the target skill is available or force-loaded for a workflow eval. | With skill, skill run |
| **Without-skill Configuration** | A configuration where the model runs without the target skill so skill value can be measured. | Baseline, no-skill run |
| **Previous-skill Configuration** | A configuration using an older skill version to measure regressions or improvements. | Old skill, snapshot, prior version |
| **Forced Workflow Mode** | A workflow execution mode where the target skill is explicitly provided so the eval tests behavior after loading. | Prompt injection, forced skill loading |
| **Real Trigger Mode** | A trigger execution mode where the harness exposes skills normally and the agent must decide whether to select one. | Natural invocation, real harness invocation |

## Trace and run capture

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Eval Run** | One execution of one eval case under one configuration. | Run, attempt, sample |
| **Trace Bundle** | The complete captured evidence for an eval run, including raw output, normalized events, artifacts, metrics, diffs, and grades. | Run output, transcript, results folder |
| **Raw Harness Output** | The unmodified output emitted by the agent harness during an eval run. | Raw trace, transcript, stdout |
| **Normalized Trace** | A JSONL event stream using the framework's common event schema; currently it records run start, harness finish, and run finish events. | Trace, event log, JSONL trace |
| **Trace Event** | One normalized observation from an eval run. Current events are process-level lifecycle events; future harnesses may add tool calls, skill selection, file reads, command execution, errors, or final answers. | Event, tool event, process event |
| **Workspace Diff** | The file-system changes produced by an eval run relative to its starting fixture. | Diff, final patch, workspace changes |
| **Artifact** | A final file or response produced by an eval run and considered during grading or human review. | Output, final answer, deliverable |
| **Run Metrics** | Quantitative measurements captured for an eval run, such as tokens, wall time, command count, tool errors, retries, and cost. | Stats, benchmark numbers, telemetry |

## Grading and reporting

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Deterministic Check** | An objective grading rule evaluated by code without an LLM judge. | Assertion, expectation, test assertion |
| **Declarative Check** | A deterministic check expressed directly in eval data using generic rules such as contains, not-contains, regex, schema-valid, or file-exists. | Generic check, data-driven assertion |
| **Skill-local Grader** | Optional skill-owned code that evaluates domain-specific deterministic checks the central runner cannot express generically. | Custom grader, grader script |
| **LLM Judge** | An optional model-based grader for subjective quality dimensions that deterministic checks cannot reliably assess; the current framework records judge metadata/placeholders but does not execute judges yet. | Judge, model grader, qualitative grader |
| **Rubric** | A written standard used by an LLM judge or human reviewer to assess subjective quality consistently. | Scoring guide, judging prompt |
| **Outcome Score** | A measure of whether the eval task reached the desired externally visible result. | Completion score, quality score |
| **Process Score** | A measure of whether the agent followed required behavioral steps such as loading references, using scripts, and avoiding forbidden tools. | Trace score, procedure score |
| **Style Score** | A measure of whether the response or artifact follows expected communication and formatting conventions. | Formatting score, presentation score |
| **Efficiency Score** | A measure of whether the skill's quality gain justifies its time, token, command, retry, and cost overhead. | Performance score, overhead score |
| **Benchmark Report** | A comparable summary of eval results across configurations, suites, metrics, and historical runs. | Benchmark, report, summary |
| **Human Review** | Manual inspection of eval outputs and grades to catch quality issues that automated checks miss. | Reviewer pass, qualitative review |

## Relationships

- A **Skill Eval Framework** has exactly one canonical **Central Runner**.
- A **Skill** owns zero or more **Eval Manifests**; each **Eval Manifest** declares one or more **Eval Suites**.
- An **Eval Suite** contains one or more **Eval Cases**.
- A **Golden Prompt Set** is composed of selected **Eval Cases** from one or more **Eval Suites**.
- A **Workflow Eval** usually runs in **Forced Workflow Mode**; a **Regression Suite** reuses the workflow case runner; a future **Trigger Eval** runner will use **Real Trigger Mode**.
- A **Negative Control** is a kind of **Trigger Eval** where the correct result is non-selection of the **Skill**.
- An **Eval Case** runs under one or more **Configurations**.
- Each pair of **Eval Case** and **Configuration** produces one or more **Eval Runs**.
- Each **Eval Run** executes inside exactly one **Sandbox** initialized from exactly one **Fixture**.
- Each **Eval Run** produces exactly one **Trace Bundle**.
- A **Trace Bundle** contains one **Raw Harness Output**, zero or more **Trace Events**, zero or one **Workspace Diff**, zero or more **Artifacts**, one set of **Run Metrics**, and one grading result.
- A **Deterministic Check** belongs to an **Eval Case** and is evaluated against the **Trace Bundle**.
- A **Declarative Check** is evaluated by the **Central Runner**; a **Skill-local Grader** evaluates domain-specific **Deterministic Checks**.
- An **LLM Judge** evaluates an **Eval Case** only when a subjective **Rubric** is required.
- A **Benchmark Report** compares **Eval Runs** across **Configurations** and historical results.
- A real observed failure should become a **Regression Case** before the **Skill** is changed.
- The **PRD Epic** is the parent planning artifact for future implementation tasks.

## Example dialogue

> **Dev:** "For `custom-command`, should I add another per-skill script or use the **Central Runner**?"
>
> **Domain expert:** "Use the **Central Runner**. Put the prompts and checks in **Skill-local Eval Data**, then declare them through the **Eval Manifest**."
>
> **Dev:** "If I force-load the skill text, is that a **Trigger Eval**?"
>
> **Domain expert:** "No. That is a **Workflow Eval** in **Forced Workflow Mode**. A **Trigger Eval** uses **Real Trigger Mode** and checks whether the agent selects the **Skill** naturally."
>
> **Dev:** "Where do I check that `$ARGUMENTS` is used and `agent` frontmatter is avoided?"
>
> **Domain expert:** "Those are **Deterministic Checks**. Use **Declarative Checks** where possible, and a **Skill-local Grader** only when Markdown command parsing needs domain logic."
>
> **Dev:** "What do I save when the run finishes?"
>
> **Domain expert:** "Save the full **Trace Bundle**: **Raw Harness Output**, **Normalized Trace**, final **Artifacts**, **Run Metrics**, optional **Workspace Diff**, and the grading result."
>
> **Dev:** "If a real prompt later causes the skill to miss invocation, what happens?"
>
> **Domain expert:** "Capture it as a **Regression Case** before changing the description, then verify the fix through the **Regression Suite**."

## Flagged ambiguities

- "Eval", "test", and "benchmark" were used interchangeably. Use **Eval Case** for one prompt scenario, **Eval Suite** for a collection of cases, and **Benchmark Report** for comparable results across runs.
- "Skill invocation", "skill trigger", and "skill loading" can mean different things. Use **Trigger Eval** for natural skill selection, **Forced Workflow Mode** for explicit skill loading, and **Workflow Eval** for behavior once the skill is available.
- "Assertion" and "expectation" both appeared in current repo artifacts. Use **Deterministic Check** as the canonical domain term; reserve `expectations` only as a legacy schema field until migrated.
- "Runner", "framework", and "harness" were overloaded. Use **Skill Eval Framework** for the whole system, **Central Runner** for the repo-owned executable, and "agent harness" only for external runtimes such as Claude Code, Pi, OpenCode, or Daedalus.
- "Workspace", "sandbox", and "fixture" were blurred. Use **Sandbox** for the isolated per-run working area, **Fixture** for the starting state, and **Workspace Diff** for changes after execution.
- "Baseline" can mean without-skill or previous-skill. Use **Configuration** as the general term, with **Without-skill Configuration** and **Previous-skill Configuration** for specific baselines.
- "Trace", "transcript", and "raw output" were conflated. Use **Raw Harness Output** for unmodified harness output, **Normalized Trace** for JSONL events, and **Trace Bundle** for the complete captured run evidence.
- "Negative eval" can mean failure expectation or no-trigger control. Use **Negative Control** only for should-not-trigger cases.
- "Capability" and "regression" suites serve different purposes. Use **Capability Suite** for hard cases that may improve over time and **Regression Suite** for known-fixed behavior that should remain stable.
