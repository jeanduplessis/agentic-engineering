# Writing resumable beads

A bead should let a future agent resume without rediscovering the same facts. Write for an agent that has the repository and br database but not this conversation.

## What to record

Record durable state, not every step:

- **CURRENT**: what works now, what changed, and where the branch stands.
- **NEXT**: the next concrete action.
- **DECISIONS**: choices that should not be relitigated.
- **BLOCKERS**: unmet requirements, dependencies, or external waits.
- **VALIDATE**: commands already run and commands still needed.
- **FOLLOW-UP**: linked bead IDs for deferred work.

Good note:

```text
CURRENT: Parser accepts template variables and creates parent/child beads. Unit tests pass.
DECISIONS: Kept variables declarative to avoid code execution.
BLOCKED: Need product decision on shared template location.
NEXT: Add validation errors after location decision.
VALIDATE: cargo test parser_workflow
```

Bad note:

```text
worked on parser, seems okay
```

## Create with useful context

```bash
br create "Add validation errors" \
  -t task -p 2 \
  --description "CURRENT: parser path exists. NEXT: add user-facing validation errors. ACCEPTANCE: invalid input returns actionable messages and tests cover malformed cases." \
  --json
```

For long descriptions, write to a temp file and pass the contents:

```bash
br create "Document handoff" --description "$(cat handoff.md)" --json
```

For long narrative context after creation, prefer comments:

```bash
br comments add br-42 --file handoff.md --json
```

## Update cadence

Update br at natural persistence boundaries:

- before pausing or handing off;
- after a major decision;
- when the next step changes;
- when a blocker appears or clears;
- before closing, with validation context.

Do not update br after every tiny checklist step unless that step changes future resumption context.

## Close with completion evidence

```bash
br close br-42 --reason "Implemented token refresh in auth/session.go; added TestRefreshExpiredToken; follow-up UX polish tracked as br-91" --json
```

A close reason should include what was delivered, how it was validated, and any linked follow-up.

## If you cannot finish

Leave the task open and write a handoff comment:

```bash
br comments add br-42 --message "Handoff: RED test TestRefreshExpiredToken fails because token clock source is still hard-coded. NEXT: inject Clock into session manager, then rerun auth tests." --json
```

Do not close incomplete work just because your session is ending.
