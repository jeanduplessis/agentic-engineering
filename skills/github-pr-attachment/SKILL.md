---
name: github-pr-attachment
user-invocable: false
description: Upload a local review artifact as a GitHub pull-request attachment and place its generated link in the PR description without losing existing content. Use when a validated video, image, log, PDF, or other GitHub-supported file must be attached to an existing PR as evidence. Uses an authenticated agent-browser session for GitHub's web upload flow and gh for conservative PR-body edits.
---

# GitHub PR attachment

Publish an existing local artifact to an existing pull request. This skill owns upload, visibility review, body placement, and
post-publication verification. It does not create, edit, record, transcode, or validate the artifact's substantive content.

For video creation and validation, use `video-evidence` first. For broader PR creation, pushing, title changes, or description
rewrites, use `pr-create`.

## Required input

For each artifact, require:

```text
path: absolute local path
label: human-readable title
claim: what the artifact demonstrates or contains
validation: upstream validation result, when applicable
proposed_placement: target PR section or comment, defaulting to Human Verification in the body
```

Also require the exact PR number/URL or enough repository context to resolve it unambiguously. Reject missing files and
unsupported formats before requesting confirmation.

## Non-negotiable rules

Mutation safety:

- Keep artifacts out of git unless the user asks to commit them.
- Preserve the existing PR title and body unless the user asks for broader changes.
- Never reconstruct the existing body from memory.
- Ask for confirmation immediately before the first upload or PR edit.
- Selecting a file in GitHub uploads it immediately, before comment submission.

Upload safety:

- Use GitHub's documented web attachment flow, not an undocumented upload API.
- Do not request passwords or 2FA codes, extract cookies, or automate login without user participation.
- Verify the final link, rendering, access expectations, and playback/download behavior.

## 1. Load tools and inspect inputs

Before any browser command, load the installed agent-browser workflow:

```sh
agent-browser skills get core --full
```

Require `agent-browser` and `gh`. For each path:

- Resolve the absolute path and verify it is a regular readable file.
- Record filename, extension, and byte size.
- Confirm the file matches the supplied label/claim and has the stated upstream validation.
- Do not re-edit or re-encode it. Return to the producing workflow if the artifact is not ready.

## 2. Resolve the target without mutation

Resolve the repository and exact existing PR. Capture immutable working context before any upload:

```sh
gh pr view <number-or-url> --json number,title,body,url,headRefName,baseRefName
```

Confirm that the PR belongs to the intended repository and branch. Save the exact current body to a temporary file outside the
repository. If the PR cannot be resolved unambiguously, stop and ask.

Determine whether the repository is public, private, or internal. GitHub documents that public-repository attachments are
accessible without authentication; private/internal attachments require repository access. If the artifact should not inherit
that visibility, do not upload it.

## 3. Check GitHub attachment compatibility

GitHub currently supports these media types in PRs and issues:

- Images: `.png`, `.gif`, `.jpg`, `.jpeg`, `.svg`.
- Video: `.mp4`, `.mov`, `.webm`; H.264 is recommended for cross-browser playback.
- Other documented types include PDFs, office documents, text/data/code files, archives, and audio.

Documented size limits:

- Images and GIFs: 10 MB.
Video limits by repository plan:

- Free: 10 MB.
- Paid: 100 MB, subject to uploader eligibility above 10 MB.
- Other files: 25 MB.

Recheck GitHub's official attachment documentation when a format is unusual, a file is near a limit, the repository plan is
unknown, or an upload fails. Do not compress, rename deceptively, or change the artifact within this skill.

## 4. Propose the exact mutation and confirm

Before the first upload, show:

- Exact PR URL, title, repository visibility, and number.
- Each artifact's path, label, claim, extension, and size.
- The visibility implication.
- Whether placement is in the PR body or a submitted comment.
- The exact target section and proposed surrounding text.
- A statement that file selection uploads immediately and may leave an unreferenced upload if later mutation fails.

Ask once for confirmation to upload the listed artifacts and perform the proposed PR mutation. Confirmation for another GitHub
workflow does not count unless it explicitly included these uploads and this body/comment change.

## 5. Upload through GitHub's web flow

Use a user-approved authenticated GitHub browser session. If none exists, ask the user to authenticate in a headed browser.
Do not record GitHub login.

Locate and upload:

1. Open the exact PR conversation.
2. Take a fresh snapshot and locate a PR comment composer plus its file input or "Attach files" control.
3. Use `agent-browser upload <file-input-ref> "/absolute/path/to/artifact"`; avoid native file-picker automation.
4. Wait until GitHub inserts generated attachment Markdown or a URL in the composer.

Capture and clean up:

1. Read and preserve the generated snippet exactly.
2. Verify the URL uses the expected `github.com/user-attachments/assets/...` shape.
3. Do not submit the temporary comment when the requested destination is the PR body.
4. Clear or discard the composer after safely storing the snippet.

GitHub uploads the file during selection. Clearing the composer removes the draft reference, not necessarily the uploaded blob.
If the upload fails or no snippet appears, stop rather than guessing a URL.

If the user requested a submitted PR comment instead of body placement, show the exact composed comment before submitting it;
the earlier upload confirmation covers submission only when the proposed comment text and destination were included.

## 6. Apply a conservative PR-body edit

Skip this section for a confirmed comment-only publication.

Start from the exact captured PR body. Add or update only the approved target section. Preserve all unrelated text, headings,
issue links, reviewer notes, user-authored context, and existing attachment snippets.

Default structure when no suitable section exists:

```md
## Human Verification

- <claim supplied with the artifact>

### <artifact label>

<exact Markdown or URL generated by GitHub upload>
```

For multiple artifacts, use one labeled subsection per artifact. Do not rewrite the rest of the description to match a template.
Write the proposed body to a temporary file and inspect its diff against the captured body before mutation.

Before editing, fetch the body again. If it changed since capture, merge the approved addition into the new body or ask when the
merge is ambiguous; never overwrite concurrent edits.

Apply the body with:

```sh
gh pr edit <number-or-url> --body-file <temporary-body-file>
```

When replacing an attachment, upload the replacement first and replace only the old referenced snippet. The old upload may
remain unreferenced; do not commit a file merely to replace it.

## 7. Verify publication

After mutation:

- Fetch the PR body again and verify each exact generated URL appears once in the intended section.
- Confirm all unrelated body content remains present.
- Reload the PR and inspect the rendered label and attachment/player.
- Open or play each attachment at normal size and verify it is the expected artifact.
- Confirm access behavior matches repository visibility.

If upload succeeds but body/comment mutation fails, report the unreferenced upload and leave the existing body unchanged rather
than applying an uncertain rewrite. If verification fails, report the precise failure and do not claim publication succeeded.

## Output contract

Report:

```text
pr_url: exact PR URL
placement: body section or submitted comment URL
attachments:
  - label
  - source_path
  - generated_snippet
  - attachment_url
  - verification result
body_preserved: whether unrelated content remained unchanged
repository_visibility: public, private, or internal
media_committed: normally no
orphaned_uploads: any uploaded URLs not referenced by the final PR
```

## Completion checklist

- [ ] Existing PR and repository visibility were resolved.
- [ ] Local files, formats, sizes, labels, and claims were checked.
- [ ] Existing PR body was captured exactly.
- [ ] Exact upload and mutation scope was confirmed before file selection.
- [ ] Upload used GitHub's authenticated web attachment flow.
- [ ] Generated snippets were preserved exactly; no URL was guessed.
- [ ] Temporary comments were not accidentally submitted.
- [ ] Concurrent body changes were detected before editing.
- [ ] Unrelated PR content remained unchanged.
- [ ] Final links, rendering, access, and playback/download were verified.
- [ ] Media was not committed unless explicitly requested.

## Reference

- GitHub Docs, "Attaching files": https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files
