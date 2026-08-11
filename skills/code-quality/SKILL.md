---
name: code-quality
description: Use this skill when evaluating code changes through a prepared Review Packet or invoking @code-quality-* agents. Defines source-neutral packet and result contracts, shared severity/category rules, and specialized criteria for security, logic, types, data, resources, style, React, and tests.
---

# Code Quality

Judge prepared code-change evidence. Do not discover local changes, fetch pull requests, merge results, publish
reviews, or fix code; caller workflows own those responsibilities.

## Contracts

- Review Packet: `schemas/review-packet.schema.json` and `references/review-packet.md`.
- Quality Result: `schemas/quality-result.schema.json` and `references/quality-result.md`.
- Shared reviewer rules: `references/reviewer-core.md`.
- Severity and categories: `references/severity.md`.

Validate contracts with:

```bash
python3 <skill-root>/scripts/validate_contract.py packet <packet.json>
python3 <skill-root>/scripts/validate_contract.py result <result.json> --focus <focus>
```

## Focus routes

- `security.md` → `@code-quality-security`
- `logic.md` → `@code-quality-logic`
- `types.md` → `@code-quality-types`
- `data.md` → `@code-quality-data`
- `resources.md` → `@code-quality-resources`
- `style.md` → `@code-quality-style`
- `react.md` → `@code-quality-react`
- `tests.md` → `@code-quality-tests`

Every invocation receives one absolute `packet.json` path, loads the shared contracts plus one focus reference, and
returns only one schema-valid Quality Result JSON object. All eight focuses run; use `NOT_APPLICABLE` when the focus
reference's applicability condition fails and `BLOCKED` when required evidence is unavailable or invalid.
