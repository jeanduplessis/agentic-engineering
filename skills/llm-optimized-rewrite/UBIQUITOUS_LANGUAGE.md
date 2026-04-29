# Ubiquitous Language

## Analysis domain

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Smell test** | A heuristic static analysis that reports likely optimization issues without proving correctness. | Linter, validator, optimizer, judge |
| **Optimized state** | A file condition where token cost and LLM execution reliability are good enough by the smell test's heuristic thresholds. | Valid state, perfect state, compressed state |
| **Finding** | A single reported smell with a stable rule identity, severity, category, location, evidence, message, and suggestion. | Issue, warning, violation, lint |
| **Rule** | A deterministic static check that can produce zero or more findings. | Check, heuristic, lint rule |
| **Suggestion** | Human-readable guidance for addressing a finding without providing an automatic edit. | Fix, patch, replacement |
| **Evidence** | The source text fragment or structural fact that caused a finding. | Example, match, snippet |
| **Score** | A deterministic number starting at 100 and reduced by severity penalties from findings. | Grade, rating, quality score |
| **Status** | The pass, warn, or fail label derived from the score thresholds. | Result, outcome, validity |

## Optimization qualities

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Token-cost smell** | A finding category for wording or structure likely to waste tokens. | Compression issue, verbosity issue |
| **Reliability smell** | A finding category for wording or structure likely to reduce LLM execution reliability. | Prompt issue, execution issue |
| **High-signal rule** | A scored rule expected to have low false-positive risk. | Core rule, confident rule |
| **Experimental finding** | A low-penalty or informational finding from a noisier heuristic. | Weak finding, maybe issue |
| **Static analysis** | Deterministic inspection of file text and structure without an LLM. | Analysis, automated review |
| **Semantic review** | Human or LLM-assisted review that checks whether a proposed rewrite preserves meaning and constraints. | Verification, judgment, validation |
| **Candidate discovery** | Using findings to identify possible rewrite opportunities before semantic review. | Precheck, triage, scan |

## File and region concepts

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Target file** | The file supplied to the smell test for analysis. | Input file, subject, document |
| **Leading frontmatter** | The first YAML metadata block at the start of a Markdown-like target file. | YAML header, metadata block |
| **Analyzed body** | The target file content remaining after leading frontmatter is excluded. | Body, analyzed text, content |
| **Fenced block** | A Markdown fenced code or text block that remains part of the analyzed body. | Code fence, fenced code |
| **Skill-like file** | A target file whose static cues indicate it contains agent skill instructions. | Skill file, skill document |
| **Command-like file** | A target file whose static cues indicate it contains an agent command or prompt template. | Command file, prompt command |

## Programmatic contract

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **JSON report** | The smell test's only successful output format for programmatic callers. | Output, report, result |
| **Completed analysis** | A run that successfully produces a JSON report, regardless of pass, warn, or fail status. | Successful run, passing run |
| **Usage failure** | A non-analysis failure caused by invalid invocation, such as a missing path. | User error, CLI error |
| **Runtime failure** | A non-analysis failure caused by an operational problem, such as an unreadable file or token-count failure. | Tool error, execution error |
| **Programmatic caller** | Software or an agent wrapper that invokes the smell test and parses its JSON report. | Consumer, caller, client |
| **Token metrics** | Exact token-count data produced through the existing static token-counting path. | Token counts, tokenizer output |

## Planning and tracking

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **PRD epic** | The parent beads issue that stores the approved product requirements document. | PRD task, parent ticket |
| **Implementation task** | A child beads issue representing an independently implementable vertical slice of the PRD. | Sub-task, ticket, slice |
| **AFK slice** | An implementation task that can be completed without human interaction. | Automated task, non-HITL task |
| **HITL slice** | An implementation task that requires human interaction or approval. | Manual task, review task |

## Relationships

- A **Smell test** performs **Static analysis** on one **Target file** and emits one **JSON report**.
- A **Target file** may contain zero or one **Leading frontmatter** region and exactly one **Analyzed body** after region extraction.
- A **Fenced block** belongs to the **Analyzed body** and is analyzed by default.
- A **Rule** produces zero or more **Findings**.
- A **Finding** has exactly one **Rule**, one **Status**-relevant severity, one category, and one **Suggestion**.
- A **Token-cost smell** and a **Reliability smell** are distinct finding categories.
- A **Score** is calculated from **Findings**, and **Status** is derived from the **Score**.
- A **Completed analysis** exits successfully even when **Status** is warn or fail.
- A **Usage failure** or **Runtime failure** prevents a **Completed analysis** and exits nonzero.
- **Candidate discovery** may use **Findings**, but accepted rewrites still require **Semantic review**.
- A **PRD epic** owns multiple **Implementation tasks**.
- An **Implementation task** can be an **AFK slice** or a **HITL slice**.

## Example dialogue

> **Dev:** "If the **Smell test** returns fail, did it prove the **Target file** is wrong?"
>
> **Domain expert:** "No. A fail **Status** only means the **Score** crossed a heuristic threshold because of **Findings**. It is candidate discovery, not semantic proof."
>
> **Dev:** "Should a **Finding** include a replacement so the caller can apply it automatically?"
>
> **Domain expert:** "No. It should include a **Suggestion** and **Evidence**, but not a patch. The rewrite workflow still needs **Semantic review** before edits."
>
> **Dev:** "Do we analyze the YAML metadata in a command file?"
>
> **Domain expert:** "No. The **Leading frontmatter** is excluded, but the **Analyzed body**, including any **Fenced block**, remains in scope."
>
> **Dev:** "So a program can treat nonzero exit as a bad **Status**?"
>
> **Domain expert:** "No. A **Completed analysis** exits 0 even for warn or fail. Nonzero means a **Usage failure** or **Runtime failure** prevented the **JSON report**."

## Flagged ambiguities

- "smell test" must not be treated as a **Semantic review** or validator; use **Smell test** only for heuristic static candidate discovery.
- "optimized" must not mean "perfect" or "semantically proven"; use **Optimized state** for threshold-based heuristic quality.
- "issue" is overloaded between a reported smell and a beads tracker item; use **Finding** for analyzer output and **Implementation task** or **PRD epic** for beads work.
- "success" is ambiguous between process success and optimization quality; use **Completed analysis** for exit-code success and **Status** for pass/warn/fail quality.
- "fix" implies an automatic edit; use **Suggestion** because v1 findings do not include machine-applicable replacements or patches.
- "body" can mean the whole file or the post-frontmatter region; use **Analyzed body** for the content actually checked.
