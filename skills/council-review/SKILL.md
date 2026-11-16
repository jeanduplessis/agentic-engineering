---
name: council-review
description: Convene a three-model advisory council in T3 Code (Claude Opus 5.5, GPT-6.1 Sol, and Grok 4.7, each at high reasoning effort) for independent verdicts on any question, plan, decision, document, design, or code, then synthesize agreements, disagreements, and recommended next steps. Use when the user says "council", "council review", or "ask the council", or wants independent opinions from several AI models or providers. Advice only; neither the members nor you take action. Do not use for single-agent idea challenges or premortems (idea-challenger, premortem) or for posting PR reviews (review-for-me).
---

# Council review

Get independent verdicts from three models on three providers, then synthesize them for the user.

- The council gives advice only. Members research and judge; they never change anything.
- You chair: you brief the members, collect their verdicts, and synthesize them.
- Do not act on the recommendations within this skill.

## Members

Default members, unless the user names others:

| Member | Provider display name | `providerInstanceId` | `model` | `options` |
| --- | --- | --- | --- | --- |
| Claude Opus 5.5 | Claude Personal | `claudeAgent_claude_personal` | `claude-opus-5-5` | `{"effort": "high"}` |
| GPT-6.1 Sol | Codex (OpenAI) | `codex` | `gpt-6.1-sol` | `{"reasoningEffort": "high"}` |
| Grok 4.7 | Grok | `grok` | `grok-4.7` | `{"reasoningEffort": "high"}` |

### Resolving members

- If the user names a member, model, provider, or effort, use it for that seat. Keep the defaults for the others.
- Call `orchestrator_capabilities` once per thread, before the first `delegate_task`.
- Match each member by provider display name and model ID.
- If the catalog's IDs differ from the table, use the catalog's IDs for the same provider and model.
- If a model is not in the short list, call `orchestrator_capabilities` again with `search`.
- Use each model's own option ID, and confirm `high` is a listed value.

### Unavailable members

A member is unavailable when any of these is true:

- Its provider or model is missing or disabled.
- Its provider lists a constraint.
- Its provider reports `canRunChildTask: false`.
- Its provider is not yours and reports `canRunCrossProviderChildTask: false`.

Never substitute a provider instance, model, or effort. "Claude Work" is not "Claude Personal", and Grok 4.7 Fast
is not Grok 4.7. Tell the user which member is unavailable and why. Ask whether to continue without it or stop.

## Tools

T3 Code exposes these tools to every harness it runs, such as Claude Code, Codex, Grok, and Pi:

- `orchestrator_capabilities`: resolve the members.
- `delegate_task`: start each member.
- `task_status`: read a member's result after it completes.
- `task_cancel`: stop members you no longer need.

Their names carry a harness-specific prefix, such as `mcp__t3-code__`. Some harnesses defer them. Load them (for
example with ToolSearch) and try each tool once before you treat it as absent.

Start every member with `delegate_task`, including a member on your own provider and model. Every member then gets
the same brief, explicit settings, and lifecycle. Do not use native subagent tools, `t3_thread_send`, or new threads
for members.

Outside T3 Code, use the harness's own subagent tool only if it can run each member's exact model at high effort.
Otherwise tell the user that the council needs T3 Code, and stop. Never role-play a member or write its verdict
yourself.

## Workflow

### 1. Prepare

1. Identify what the user wants judged and the decision the advice informs.
2. If the question is too vague to judge, ask the user one clarifying question first.
3. Collect the context members need: facts from the conversation, constraints, decisions made, and options ruled out.
4. Collect the materials and criteria: file paths, links, excerpts, and the user's criteria.

### 2. Write one brief

Use the template in "Member brief". Members receive only the brief, not this conversation.

- Make it self-contained.
- Keep it neutral: leave out your own opinion and any preferred answer.
- Leave out secrets, credentials, and personal data the members do not need. The brief goes to three providers.

### 3. Launch

1. If the working directory is a git repository, record `git status --porcelain`.
2. In one turn, call `delegate_task` once per member, so all three run in parallel.

Pass these fields to each `delegate_task`:

- `task`: the brief, identical for every member
- `title`: `Council: <member> - <topic>`
- `role`: `review`
- `target`: the member's `providerInstanceId`, `model`, and `options`
- default `isolation` (`shared`, so members can read the workspace) and default async `mode`
- no `runtimeMode` and no `interactionMode`

### 4. Wait and handle interruptions

- Follow the `next` guidance that each `delegate_task` result returns.
- Do not poll with `task_status`, sleep, or watchers. When a member completes, read its result with `task_status`.
- If a member asks a question, answer from the brief's context, or ask the user.
- Refuse any member request to edit files, run commands that change state, or contact external systems.
- If a member fails or times out, report it. Offer to retry that member with a new `delegate_task`.
- Do not replace a failed member with a different model.
- If the user cancels or changes the question, call `task_cancel` for every running member.

### 5. Check the workspace

1. Run `git status --porcelain` again and compare it with the snapshot.
2. If anything changed, tell the user which paths changed during the council and that a member may have changed them.
3. Do not revert anything unless the user asks.

### 6. Synthesize and stop

Reply with the synthesis below, then stop. Act on a recommendation only if the user asks in a later request.

## Member brief

Fill in every placeholder:

```text
You are one of three independent advisors on a council. Advisors from other AI providers receive this same brief.
Give your own verdict. Do not guess what the others will say.

Your role is to advise. Do not take action.
- Allowed: read files, search the web, fetch pages, and run commands that only read state (for example `git log`,
  `ls`, `rg`). Also allowed: <commands the user explicitly approved, or "nothing else">.
- Not allowed: create, edit, move, or delete files; build, test, install, format, or migrate; commit, push, or switch
  branches; open, comment on, or close pull requests or issues; send messages; call APIs that change state.
- Not allowed: start subagents or new threads.
- If you think an action is needed, recommend it instead of doing it.

Topic: <the question or subject, in one or two sentences>
Decision this informs: <what the user will decide with this advice>
Context: <facts, constraints, decisions already made, options ruled out>
Materials: <file paths in the working directory, URLs, pasted excerpts>
Criteria: <the user's criteria, or "use your judgment">

Stay on the topic. Raise a related issue only if it changes your verdict.
Cite a source (file:line or URL) for each factual claim your verdict depends on, and mark claims you could not verify.

Reply in this format:
Verdict: <one-sentence answer>
Confidence: <low | medium | high>
Score: <N/10 for the quality of the subject, or "n/a" if the topic is not something to grade>
Reasoning: <3-6 bullets, strongest first>
Risks and concerns: <bullets, most serious first>
What would change my verdict: <specific evidence or conditions>
Recommendations: <concrete next steps for the user, highest priority first>
Sources: <list>
```

## Synthesis

Reply in chat with:

```markdown
## Council review: <topic>

**Council verdict:** <the consensus answer, or "Split:" followed by the split>

<One short paragraph with the reasoning that matters most for the decision.>

| Member | Verdict | Confidence | Score |
| --- | --- | --- | --- |
| Claude Opus 5.5 (high) | <one line> | <level> | <N/10, n/a, or no score> |
| GPT-6.1 Sol (high) | <one line> | <level> | <N/10, n/a, or no score> |
| Grok 4.7 (high) | <one line> | <level> | <N/10, n/a, or no score> |

### Agreement
### Disagreement
### Raised by one member
### Recommended next steps
### Gaps
```

Report only what members said:

- Attribute each point to the members who made it.
- Never invent a verdict, score, or source.
- Write `no score` when a member gave none. Mark an absent member as `unavailable` or `failed`.
- Under **Disagreement**, state each side and who holds it. Say which side the cited evidence favors, or that it is
  unresolved.

Weigh and scope the advice:

- Weigh arguments by evidence, not by vote count. Say when a majority view rests on an unverified claim.
- You may check a contested factual claim that the verdict depends on, using read-only tools. Label the result as
  your own check.
- Keep the synthesis on the user's question. Leave out members' tangents unless they change the verdict.
- If you disagree with the council, add a short **Chair's note** after the members' views, labeled as your own view.

Close out:

- Under **Gaps**, list absent members, unverified claims, and missing context that limited the advice.
- Put the results only in your reply. Do not write them to files, PR descriptions, or comments.

## Later rounds

Run another round only when the user asks, for example after they revise the subject or if they ask you to keep improving something until the council reaches a threshold of agreement.

- Start a new `delegate_task` for each member with a complete, fresh brief.
- Add what changed since the last round and the last round's main concerns, without naming which member raised them.
- Do not reuse a member's thread with `t3_thread_send`.
- Add one column per round to the member table, for example `| Member | Round 1 | Round 2 |`. Show each member's
  score, or its verdict when the topic has no score.
