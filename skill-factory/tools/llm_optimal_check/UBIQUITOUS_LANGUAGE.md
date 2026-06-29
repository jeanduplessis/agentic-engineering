# Ubiquitous Language

## LLM optimization validation

- **LLM Optimal Check**: A deterministic repo-level check that evaluates whether a text file is optimized
  enough for reliable and efficient LLM consumption. Avoid aliases: Smell test, optimizer, linter.

- **Optimization Readiness**: The judgment that a file is acceptable for LLM consumption according to
  deterministic token-cost and reliability heuristics. Avoid aliases: Prompt quality, cleanliness, compliance.

- **Optimization Finding**: One actionable issue emitted by the **LLM Optimal Check**, with rule, severity,
  location, evidence, message, and suggestion. Avoid aliases: Finding item, smell, lint error.

- **Check Status**: The native `pass`, `warn`, or `fail` status emitted by the **LLM Optimal Check**. Avoid
  aliases: Result, outcome.

- **Blocking Optimization Failure**: A `fail` **Check Status** that makes the target skill invalid. Avoid
  aliases: Hard failure, invalid prompt.

- **Non-Blocking Optimization Warning**: A `warn` **Check Status** that remains visible but does not make the
  target skill invalid. Avoid aliases: Soft failure, advisory issue.

- **Tool Error**: A failure of the checker or its dependencies to run to completion, distinct from a
  **Blocking Optimization Failure** found in target text. Avoid aliases: Crash, infra failure, check failure.

## Token measurement

- **LLM Token Count**: A standalone repo-level tool that counts model-token metrics for text. Avoid aliases:
  Token script, tokenizer helper.

- **Token Metrics**: Exact measured counts such as tokens and characters returned by **LLM Token Count**.
  Avoid aliases: Usage, token estimate.

- **Analyzed Body**: The file content analyzed after excluding leading YAML frontmatter when applicable. Avoid
  aliases: Body text, prompt text.

- **Frontmatter Exclusion**: The policy of omitting leading YAML metadata from optimization and token metrics
  unless explicitly requested. Avoid aliases: Header stripping, metadata ignore.

## Skill validation integration

- **LLM Optimal Check Gate**: The `skill_valid` validation gate keyed as `llm_optimal_check` that runs the
  **LLM Optimal Check** on the target skill's `SKILL.md`. Avoid aliases: Smell-test gate, optimization gate.

- **Warn Gate Status**: A non-blocking `skill_valid` gate status that reports advisory issues while allowing
  overall validity if no blocking gates fail. Avoid aliases: Warning pass, soft pass.

- **Compact Optimization Report**: The `skill_valid` gate details containing check status, score, useful
  metrics, and all findings while excluding bulky preview/body fields. Avoid aliases: Embedded report,
  summarized report.

- **Friendly Validation Summary**: The human-readable `tools/skill_valid/skill_validate.sh` output that
  renders gate statuses and all optimization findings inline. Avoid aliases: Pretty output, wrapper report.

- **Primary Skill Instructions**: The target skill's `SKILL.md`, which is the only file analyzed by the v1
  **LLM Optimal Check Gate**. Avoid aliases: Skill prompt, skill file.

## Compatibility

- **Compatibility Wrapper**: An old skill-local script entry point that preserves its existing CLI and JSON
  contract while delegating to a new repo-level tool. Avoid aliases: Shim, adapter.

- **Smell Test Script**: The legacy `smell_test.py` entry point retained as a **Compatibility Wrapper** for
  existing users. Avoid aliases: LLM optimal check, new checker.

- **Count Tokens Script**: The legacy `count_tokens.py` entry point retained as a **Compatibility Wrapper**
  for existing users. Avoid aliases: LLM token count, token tool.

## Relationships

- The **LLM Optimal Check Gate** runs the **LLM Optimal Check** on exactly one **Primary Skill Instructions** file in v1.

- The **LLM Optimal Check** depends on **LLM Token Count** for exact **Token Metrics**.

- A **Blocking Optimization Failure** makes `skill_valid.valid` false.

- A **Non-Blocking Optimization Warning** produces a **Warn Gate Status** but does not make `skill_valid.valid` false by itself.

- A **Tool Error** fails the **LLM Optimal Check Gate** closed and prevents live gates from running.

- The **Compact Optimization Report** is embedded in `skill_valid` JSON and rendered by the **Friendly Validation Summary**.

- **Compatibility Wrappers** preserve legacy script behavior while moving canonical implementation to repo-level tools.

## Example dialogue

- **Dev:** The **LLM Optimal Check** returned `warn` for a skill. Is the skill invalid?

  **Domain expert:** No. A `warn` becomes a **Warn Gate Status**, so it is visible in validation output but
  non-blocking.

- **Dev:** What if the checker returns `fail`?

  **Domain expert:** That is a **Blocking Optimization Failure**. The **LLM Optimal Check Gate** fails and
  `skill_valid.valid` is false.

- **Dev:** Do we run it on every reference doc?

  **Domain expert:** No. In v1 it analyzes only the **Primary Skill Instructions**, the target skill's
  `SKILL.md`.

- **Dev:** Is `smell_test.py` still the canonical implementation?

  **Domain expert:** No. It is a **Compatibility Wrapper**. The canonical implementation is the repo-level
  **LLM Optimal Check** tool.

## Flagged ambiguities

- "Smell test" should refer only to the legacy **Smell Test Script** or historical wording; use **LLM Optimal Check** for the canonical repo-level tool.

- "Fail" can mean a checker-discovered **Blocking Optimization Failure** or a **Tool Error**; distinguish content failures from execution errors in messages.

- "Pass with warnings" should be expressed as **Warn Gate Status**, not as `passed`, so humans and CI do not miss advisory findings.

- "Token count" should mean exact **LLM Token Count** output, not an estimate or provider usage metric.

- "Skill prompt" should be called **Primary Skill Instructions** when discussing v1 analysis scope, because only `SKILL.md` is checked.
