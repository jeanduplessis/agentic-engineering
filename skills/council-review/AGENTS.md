# AGENTS.md — council-review skill maintenance

## Purpose

Maintain `SKILL.md` as the contract for convening a three-model advisory council in T3 Code on any topic: question,
plan, decision, document, design, or code. The skill is adapted from the `council` skill in
[t3dotgg/tstack](https://github.com/t3dotgg/tstack/blob/main/skills/council/SKILL.md). Unlike the original, it is
topic-agnostic and advice-only: the chair does not fix code before or after a round, and it does not edit PR
descriptions with results.

## How the skill works

- The chair resolves three fixed default members with `orchestrator_capabilities`: Claude Opus 5.5 on Claude
  Personal, GPT-6.1 Sol on Codex (OpenAI), and Grok 4.7 on Grok, each at high reasoning effort.
- It writes one neutral, self-contained brief and starts all three members in parallel with `delegate_task`.
- Members may read files, search the web, and fetch pages. They must not change files or external state.
- The chair compares `git status --porcelain` before and after, then synthesizes a verdict table with agreement,
  disagreement, single-member points, next steps, and gaps.
- Later rounds run only at the user's request, as new `delegate_task` calls.

## Safety and behavior contracts

- Advice only. Members and the chair take no action within the skill. Bash is not a sandbox, so the brief's rules
  and the workspace check are the safeguards; report changes and never revert them silently.
- Never substitute a provider instance, model, or effort. Report unavailable members and ask the user.
- Never fabricate a member verdict, score, or source. Write `no score` when a member gave none.
- Use `delegate_task` for every member, including one on the parent's own provider. Do not use native subagents,
  `t3_thread_send`, or new threads.
- Outside T3 Code, use the harness's own subagent tool only if it can run each exact member model; otherwise stop.
- Leave `runtimeMode` and `interactionMode` unset. T3 Code says narrow runtime modes wait for human approval rather
  than make a child read-only. Plan interaction mode is untested across the member harnesses.

## Eval and validation

`evals/manifest.json` defines no-tool workflow cases with deterministic checks for member resolution, the
advice-only brief, refusal to substitute, the synthesis format, and stopping without action.

Run from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/council-review
```

Do not run live harness or model-backed evals without explicit approval. A live council run starts three paid
model sessions.

## Change guidelines

- When default members, model IDs, provider instance IDs, or option IDs change, update the members table in
  `SKILL.md`, the synthesis table, the frontmatter description, and `evals/manifest.json` together.
- Keep the skill harness-agnostic within T3 Code. Refer to T3 tools by base name, and note that prefixes vary.
- Keep trigger wording distinct from `idea-challenger`, `premortem`, and `review-for-me`.
- Do not add steps that let the chair or members implement recommendations.
