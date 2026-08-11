# Review Packet

A workflow creates a temporary artifact bundle and passes agents the absolute path to `packet.json`.

## Required layout

- `packet.json`: manifest conforming to `review-packet.schema.json`.
- `diff_artifact`: complete normalized diff for the review identity.
- `source_root`: read-only source tree used for surrounding context.
- Per-file patch and previous-version artifacts when available.
- Optional repository instructions and workflow context artifacts.

All artifact paths are absolute or packet-directory-relative and must resolve inside `artifact_root`. `source_root`
may be outside `artifact_root`. Agents may read packet artifacts and `source_root`; they do not run source discovery.

## Source invariants

- `local`: diff artifacts describe one captured working-tree state. Existing changed files include SHA-256 values.
  Validate drift before launching agents and again before accepting results. Any mismatch blocks the review.
- `pull_request`: source root is an exact head-SHA archive; base/head identity is immutable. GitHub retrieval occurs
  once in the PR workflow, never in focus agents.

`changed_files[].line_ranges` identifies changed lines in the current file. A result anchor must target one of these
ranges. Deleted-line findings use status `deleted` and changed ranges representing pre-change diff lines.
