---
name: user-facing-writing
user-invocable: false
metadata:
  version: "4.0.0"
description: |
  Use when creating or revising durable human-facing prose: documentation, reports, PR descriptions,
  release notes, articles, proposals, and emails. Includes drafts delivered in chat for use outside the conversation.
  Not for ordinary chat, progress updates, or agent-facing instructions.
---

# User-facing writing

Write clear, simple English for the intended reader. State the point early; include enough detail to understand
it without padding. Preserve meaning first, improve readability second, and keep the author's style where it
remains clear.

## Scope and delivery

Use this guidance for text meant to stand alone and be saved, sent, published, or reused, including drafts
in chat. Reading or discussing documents does not qualify. Agent-facing instructions, including prompts and
skills, are excluded. Apply it only to human-facing prose in mixed documents.

The task controls tools, format, and delivery. This skill adds no workflow, audit, score, or required sections.
For copy-ready output, return only the text, with no assistant acknowledgment, offer to help, or edit notes.
Preserve greetings, sign-offs, and requests that belong in a letter or email. Add editorial notes only when requested,
outside the text. If nothing needs changing, return the original alone.

## Preserve meaning and evidence

- Keep facts, names, titles, quantities, dates, limits, obligations, safety notices, legal commitments,
  citations, and technical meaning. "Over 3,000" is not "3,000"; "may" is not "will"; "must" is not "should."
  Keep exhaustive lists exhaustive: "only" must not become "includes."

- Keep the same degree of uncertainty, including when merging hedges. Preserve evidence gaps in the text;
  never present guesses as verified findings.

- Use supplied details or evidence established for the task. Never invent facts, sources, measurements,
  experiences, feelings, or author opinions. Fiction and clearly labeled hypotheticals are allowed when requested.

- Select relevant notes when drafting. When editing, preserve claims that carry information unless the task
  permits removal. Remove empty praise, not information.

- Leave quotations, code, identifiers, structured data, frontmatter, link targets, and words quoted or discussed
  as examples unchanged during prose edits.

## Write plainly

- Lead with the point. Cut wordy phrases: "due to the fact that" becomes "because"; "at this point in time"
  becomes "now."

- Prefer familiar words and direct verbs when they keep the meaning: "use" over "utilize," "can" over
  "has the ability to," and "decide" over "make a decision."

- Keep necessary technical terms; explain unfamiliar ones when the reader needs it. Do not trade precision
  for familiar but vague words.

- Prefer short sentences with one main point. Split hard-to-follow sentences, but keep related ideas together
  when that reads naturally. Avoid choppy fragments.

- Name the responsible person or system when it helps. Prefer active voice; use passive voice when the actor
  is unknown or irrelevant.

- Use the same term for the same concept rather than cycling through synonyms.

- Replace vague praise and claims of importance with supported facts, mechanisms, or consequences.
  Keep useful standard instructions and warnings.

- Use formatting that helps readers find and understand information. Follow the destination's conventions;
  remove decoration and redundant labels.

- Describe current behavior in ordinary documentation. Omit unneeded change history and relative dates such
  as "replaced X last month." Keep history when requested or needed, including in PR descriptions, changelogs,
  release notes, migration guides, and decision records.

## Respect the author's voice

Match the reader, purpose, and supplied writing samples. Preserve effective humor, personality, and rhythm;
neutral factual writing needs none added. Do not manufacture roughness or mistakes to sound human. Leave clear
passages and the author's order of ideas alone unless understanding or the task requires a change.

## Remove padding, not useful writing

- Empty framing: "It is important to note that…" Give the point instead.
- Unsupported importance: "a pivotal moment," "a testament to," "experts agree."
- Drama: repeated "not X, but Y," questions the text answers itself, slogans that restate the last point.
- Repetition: a first sentence that restates the heading, recaps, generic upbeat endings.

Keep framing, contrasts, questions, summaries, and repetition when they help the reader. These patterns are hints,
not bans or signs of AI authorship. Do not judge prose by punctuation, vocabulary lists, or sentence-length limits;
dashes and lists of three are fine.

## Examples

**Cut filler; keep limits.**

Before: "It is important to note that, as of 1 March 2027, renewals may take longer. Members must renew at least
7 days before expiry."

After: "As of 1 March 2027, renewals may take longer. Members must renew at least 7 days before expiry."

**Explain a technical term with plain words.**

Before: "The dashboard utilizes polling, whereby it facilitates the retrieval of status updates every 15 seconds."

After: "The dashboard uses polling: it checks for status updates every 15 seconds."

**Merge hedges; keep the doubt.**

Before: "It would appear that the bridge was most likely built at some point in the 1920s, although the exact year
has not been recorded in any of the available sources."

After: "The bridge was most likely built in the 1920s. Available sources do not record the exact year."

**Select notes for current-state documentation.**

Notes: "The booking service holds reservations for up to ten minutes. It replaced QueueReserve in June."

Documentation: "The booking service holds reservations for up to ten minutes."

**Leave clear voice alone.**

Before: "A quiet launch is my favorite kind."

After: "A quiet launch is my favorite kind."
