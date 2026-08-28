---
name: human-writing
user-invocable: false
metadata:
  version: "3.0.2"
description: |
  Writing guidance applied automatically. Use when creating or revising durable prose for human readers:
  documentation, reports, PR descriptions, release notes, articles, proposals, and emails drafted for sending.
  Includes drafts delivered in chat when intended for use outside the conversation. Not for ordinary chat replies,
  progress updates, code or data transformations, or agent-facing prompts, instructions, and skills.
---

# Human-facing writing

Write clear, trustworthy prose suited to its reader. Apply this guidance within the artifact-producing task,
not as a separate command or editing workflow. The primary task controls tools, delivery format, and reporting;
this skill adds no audit, score, or required response sections.

For copy-ready output, return only the artifact. Include editorial commentary only when the primary task requests
it, outside the artifact. If no edit is needed, return the original text without a "no changes needed" explanation.

## Scope

A durable artifact is intended to stand alone and be saved, sent, published, or reused beyond the conversation.
Its audience and purpose determine applicability, not its file extension or whether it is delivered in chat.
Merely reading or discussing a document does not qualify. Agent-facing Markdown, including prompts and skills,
is outside this scope. In mixed documents, apply these principles only to the human-facing prose.

## Preserve meaning and evidence

When drafting from notes, select information relevant to the artifact; preserving facts does not require copying
every note. When copy-editing existing prose, keep substantive claims unless the task calls for their removal.

- Preserve facts, names, quantities, dates, uncertainty, scope, obligations, citations, and technical meaning.
  "Over 3,000" is not "3,000"; "may" is not "will"; "must" is not "should."
  Keep exhaustive lists exhaustive: "only" must not become an open-ended "includes."

- Use concrete details from the supplied material or evidence established for the task. Never invent facts,
  sources, measurements, anecdotes, experiences, feelings, or author opinions to make writing sound human.
  Invented detail belongs only in requested fiction or clearly labeled hypotheticals.

- Missing information stays missing. Keep material uncertainty visible; do not turn an unverified estimate
  into a sourced finding. In a phrasing pass, flag consequential evidence gaps rather than inventing support
  or silently deleting substantive claims. Remove empty praise, not information.

- Preserve useful qualifications, safety notices, effective dates, and legal commitments. Simplify stacked
  hedges only when the remaining wording expresses the same degree of certainty.

- Leave quotations, code, identifiers, structured data, frontmatter, and link targets unchanged during prose
  edits. Preserve names and titles; do not rewrite words being quoted or discussed as examples.

## Match the voice

Match the audience, purpose, established style, and supplied writing samples. Neutral, precise language is
appropriate for reference, technical, legal, and factual writing; it does not need added personality.

Preserve genuine humor, conviction, uncertainty, asides, and distinctive cadence when they fit the artifact.
Do not manufacture first-person experience, emotional reactions, tangents, mistakes, or roughness. Make the
minimum effective edit: leave clear passages alone and preserve the author's progression unless it impedes
understanding or the task calls for restructuring.

## Prefer clear, specific prose

- State the point directly. Prefer plain words and direct verbs when equally precise: "use" over "utilize,"
  "can" over "has the ability to," and "is" over an empty "serves as." Keep necessary domain terminology.

- Describe mechanisms, evidence, and consequences instead of generic importance or promotional praise.
  If a descriptive sentence could move unchanged to another product's documentation, check whether it says
  anything specific. Standard warnings and conventional instructions can legitimately recur.

- Name the actor when it clarifies responsibility. Active voice is often useful; passive voice is appropriate
  when the actor is unknown or irrelevant. Software and systems can be valid subjects; do not invent a person.

- Repeat the precise term for the same concept rather than cycling synonyms. Connect related thoughts and
  split sentences that are hard to follow. Let sentence and paragraph length follow the content, without quotas.

- Make structure useful. Keep headings, lists, tables, summaries, and explanations that help readers navigate
  or understand. Match the destination's formatting and typography; avoid decoration and redundant labels.

- In ordinary documentation, describe current behavior and omit incidental edit history and relative edit
  dates such as "replaced X last month." Keep history when requested or needed to use the current system,
  and in change-oriented artifacts: PR descriptions, changelogs, release notes, migration guides, and decision records.

## Patterns worth questioning

These are editing hints, not banned forms or evidence of AI authorship. Change them when they add padding,
obscure meaning, or create distracting repetition; keep them when they do useful work.

- **Empty framing:** "It is important to note," "Here's what nobody tells you," or "That last part matters"
  instead of the point and its support.

- **Unsupported importance:** "a pivotal moment," "a testament to," or trailing "highlighting its significance"
  without evidence of that significance. Vague authorities such as "experts agree" are not substitutes for sources.

- **Manufactured drama:** repeated "not X, but Y" contrasts, self-answered rhetorical questions, stacked punchy
  fragments, and aphorisms that merely repackage the preceding claim. Preserve real distinctions and useful objections.

- **Repetition without progress:** headings restated in their first sentence, paragraph-ending recaps, and generic
  optimistic conclusions. A useful takeaway or next action is different from repeating the piece.

- **Chat residue:** assistant acknowledgments, offers to continue, editing commentary, and model knowledge-cutoff
  disclaimers inside the artifact. Preserve greetings, sign-offs, and requests that belong in an actual letter or email.

An em dash, curly quotes, a three-item list, an adverb, or a formal word is not a defect by itself. Do not trade
accurate, readable prose for arbitrary vocabulary bans, punctuation limits, or simulated irregularity.

## Examples

**Remove framing without changing limits.**

Before: "It is important to note that as of 2026-06-10, the pilot may reduce delays. Operators must retain logs
for at least 30 days."

After: "As of 2026-06-10, the pilot may reduce delays. Operators must retain logs for at least 30 days."

**Use supplied details, not invented benefits.**

Before: "The update adds CSV export and keyboard shortcuts, highlighting our commitment to a seamless experience."

After: "The update adds CSV export and keyboard shortcuts."

**Select relevant notes for current-state documentation.**

Notes: "The worker retries failed jobs up to twice. It replaced LegacyWorker last week."

Documentation: "The worker retries failed jobs up to twice."

**Keep uncertainty instead of supplying a date.**

Before: "It appears the company was founded sometime in the 1990s. Its exact founding date is not documented
in the available sources."

After: "It appears the company was founded sometime in the 1990s. Its exact founding date is not documented
in the available sources."

**Leave effective voice alone.**

Before: "I like the quiet releases—the ones nobody notices."

After: "I like the quiet releases—the ones nobody notices."
