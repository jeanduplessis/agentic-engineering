from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_UNSUPPORTED_FRONTMATTER = ("agent", "model", "subtask")
_EXPECTED_FILENAMES = {
    "1": "fix-tests.md",
    "3": "pr-review.md",
    "4": "review-file.md",
}


def grade(*, response: str, case: Any | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context = context or {}
    expected_filename = _EXPECTED_FILENAMES.get(str(getattr(case, "id", "")))
    source = _command_source(response, context, expected_filename)
    markdown = source["markdown"]
    frontmatter = _extract_frontmatter(markdown)
    checks = []

    checks.append(_check(
        "custom-command.artifact_source",
        "custom_artifact_source",
        True,
        f"Grading command from {source['kind']}",
        {"kind": source["kind"], "path": source.get("path")},
    ))

    filename = source.get("filename") or _extract_filename(response, expected_filename)
    filename_ok = bool(filename and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md", filename))
    if expected_filename:
        filename_ok = filename_ok and filename == expected_filename
    checks.append(_check(
        "custom-command.filename",
        "custom_filename",
        filename_ok,
        f"Filename {filename!r} is flat kebab-case Markdown" if filename_ok else f"Filename {filename!r} is not the expected flat kebab-case Markdown filename",
        {"filename": filename, "expected": expected_filename},
    ))

    has_code_block = source["kind"] == "artifact" or _has_markdown_fence(response)
    checks.append(_check(
        "custom-command.markdown_block",
        "custom_markdown_block",
        has_code_block,
        "Command content came from a Markdown artifact" if source["kind"] == "artifact" else (
            "Response contains a Markdown command code block" if has_code_block else "Missing Markdown command code block"
        ),
    ))

    has_description = bool(frontmatter and re.search(r"^description\s*:", frontmatter, re.MULTILINE))
    checks.append(_check(
        "custom-command.markdown_frontmatter",
        "custom_markdown_frontmatter",
        has_description,
        "Markdown frontmatter contains description" if has_description else "Missing markdown frontmatter description",
    ))

    unsupported = [key for key in _UNSUPPORTED_FRONTMATTER if re.search(rf"^{key}\s*:", frontmatter or "", re.MULTILINE)]
    checks.append(_check(
        "custom-command.no_behavior_frontmatter",
        "custom_markdown_frontmatter",
        not unsupported,
        "No unsupported Pi prompt-template frontmatter" if not unsupported else f"Unsupported frontmatter: {', '.join(unsupported)}",
        {"unsupported": unsupported},
    ))

    pi_argument = re.search(r"\$ARGUMENTS|\$@|\$\d+|\$\{@:\d+(?::\d+)?\}", markdown)
    checks.append(_check(
        "custom-command.arguments",
        "custom_arguments",
        pi_argument is not None,
        f"Uses Pi argument placeholder {pi_argument.group(0)}" if pi_argument else "Does not use a Pi argument placeholder",
    ))

    shell_interpolation = re.search(r"!`[^`]+`", markdown)
    checks.append(_check(
        "custom-command.no_required_shell_interpolation",
        "custom_pi_template",
        shell_interpolation is None,
        "Does not require legacy shell interpolation" if shell_interpolation is None else "Requires legacy !`...` shell interpolation",
    ))

    required_at_file = re.search(r"@(?:[\w./-]+)", markdown)
    checks.append(_check(
        "custom-command.no_required_at_file",
        "custom_pi_template",
        required_at_file is None,
        "Does not require template @file inclusion" if required_at_file is None else f"Requires @file inclusion: {required_at_file.group(0)}",
    ))

    if str(getattr(case, "id", "")) == "1":
        has_pi_path = any(token in response for token in (
            "~/.pi/agent/prompts",
            ".pi/prompts",
            "pi.prompts",
            "commands/fix-tests.md",
            "commands/",
        ))
        checks.append(_check(
            "custom-command.install_paths",
            "custom_install_paths",
            has_pi_path,
            "Includes Pi install/discovery path" if has_pi_path else "Missing Pi install/discovery path",
            {"pi": has_pi_path},
        ))

    return checks


def _command_source(response: str, context: dict[str, Any], expected_filename: str | None) -> dict[str, Any]:
    artifact = _read_markdown_artifact(context, expected_filename)
    if artifact:
        return artifact
    return {
        "kind": "response",
        "markdown": _extract_markdown_command(response),
        "filename": _extract_filename(response, expected_filename),
        "path": None,
    }


def _read_markdown_artifact(context: dict[str, Any], expected_filename: str | None) -> dict[str, Any] | None:
    sandbox_path = context.get("sandbox_path")
    manifest = context.get("artifact_manifest") or {}
    if not sandbox_path:
        return None
    sandbox = Path(str(sandbox_path))
    files = [entry for entry in manifest.get("files", []) if str(entry.get("path", "")).endswith(".md")]
    if not files:
        return None

    def rank(entry: dict[str, Any]) -> tuple[int, str]:
        path = str(entry.get("path", ""))
        name = Path(path).name
        if expected_filename and name == expected_filename:
            return (0, path)
        if entry.get("change") in {"added", "modified"}:
            return (1, path)
        return (2, path)

    for entry in sorted(files, key=rank):
        relative = str(entry.get("path", ""))
        path = sandbox / relative
        if path.exists() and path.is_file():
            return {
                "kind": "artifact",
                "markdown": path.read_text(),
                "filename": Path(relative).name,
                "path": relative,
            }
    return None


def _extract_markdown_command(response: str) -> str:
    blocks = _fenced_blocks(response)
    for block in blocks:
        label = block["label"].lower()
        if label in {"markdown", "md"} and _extract_frontmatter(block["content"]):
            return block["content"].strip()
    for block in blocks:
        label = block["label"].lower()
        if label in {"markdown", "md"}:
            return block["content"].strip()
    for block in blocks:
        if _extract_frontmatter(block["content"]):
            return block["content"].strip()
    return response.strip()


def _fenced_blocks(response: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    lines = response.splitlines()
    index = 0
    opener_re = re.compile(r"^(`{3,}|~{3,})\s*([^`]*)\s*$")
    while index < len(lines):
        opener = opener_re.match(lines[index])
        if not opener:
            index += 1
            continue
        fence = opener.group(1)
        marker = fence[0]
        length = len(fence)
        label = opener.group(2).strip().split()[0] if opener.group(2).strip() else ""
        close_re = re.compile(rf"^{re.escape(marker)}{{{length},}}\s*$")
        content_start = index + 1
        index = content_start
        while index < len(lines) and not close_re.match(lines[index]):
            index += 1
        if index < len(lines):
            blocks.append({"label": label, "content": "\n".join(lines[content_start:index])})
        index += 1
    return blocks


def _has_markdown_fence(response: str) -> bool:
    return any(block["label"].lower() in {"markdown", "md"} for block in _fenced_blocks(response))


def _extract_frontmatter(markdown: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---", markdown.strip(), re.DOTALL)
    return match.group(1) if match else ""


def _extract_filename(response: str, expected_filename: str | None = None) -> str | None:
    candidates = _filename_candidates(response)
    if expected_filename and expected_filename in candidates:
        return expected_filename
    for candidate in candidates:
        if re.fullmatch(r"[a-zA-Z0-9_-]+\.md", candidate):
            return candidate
    return None


def _filename_candidates(response: str) -> list[str]:
    candidates: list[str] = []
    explicit_patterns = [
        r"(?:recommended\s+)?filename\s*:\s*`?([a-zA-Z0-9_./-]+\.md)`?",
        r"(?:recommended\s+)?file\s*:\s*`?([a-zA-Z0-9_./-]+\.md)`?",
    ]
    for pattern in explicit_patterns:
        candidates.extend(match.group(1) for match in re.finditer(pattern, response, re.IGNORECASE))
    for block in _fenced_blocks(response):
        text = block["content"].strip()
        if re.fullmatch(r"[a-zA-Z0-9_./-]+\.md", text):
            candidates.append(text)
    candidates.extend(match.group(1) for match in re.finditer(r"`([a-zA-Z0-9_./-]+\.md)`", response))

    normalized: list[str] = []
    for candidate in candidates:
        name = Path(candidate).name
        if name not in normalized:
            normalized.append(name)
    return normalized


def _check(check_id: str, check_type: str, passed: bool, evidence: str, details: Any = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": check_type,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }
