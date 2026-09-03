from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_BEHAVIOR_FRONTMATTER = ("agent", "model", "subtask")
_EXPECTED_FILENAMES = {
    "1": "fix-tests.md",
    "2": "analyze-coverage.md",
    "3": "pr-review.md",
    "4": "inspect-session.md",
    "5": "code-review.md",
    "6": "inspect-project.md",
}
_REPOSITORY_CASES = {"1", "2", "3", "5"}
_CANONICAL_PATHS = {
    "1": "harness/pi/commands/fix-tests.md",
    "2": "harness/pi/commands/analyze-coverage.md",
    "3": "harness/pi/commands/pr-review.md",
    "5": "harness/pi/commands/code-review.md",
}


def grade(*, response: str, case: Any | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context = context or {}
    case_id = str(getattr(case, "id", ""))
    expected_filename = _EXPECTED_FILENAMES.get(case_id)
    source = _command_source(response, context, expected_filename)
    markdown = source["markdown"]
    frontmatter = _extract_frontmatter(markdown)
    body = _extract_body(markdown)
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
        f"Filename {filename!r} is expected flat kebab-case Markdown" if filename_ok else f"Filename {filename!r} is not expected flat kebab-case Markdown",
        {"filename": filename, "expected": expected_filename},
    ))

    has_code_block = source["kind"] == "artifact" or _has_markdown_fence(response)
    checks.append(_check(
        "custom-command.markdown_block",
        "custom_markdown_block",
        has_code_block,
        "Command content came from Markdown artifact" if source["kind"] == "artifact" else ("Response contains Markdown command code block" if has_code_block else "Missing Markdown command code block"),
    ))

    has_description = bool(frontmatter and re.search(r"^description\s*:", frontmatter, re.MULTILINE))
    checks.append(_check(
        "custom-command.markdown_frontmatter",
        "custom_markdown_frontmatter",
        has_description,
        "Markdown frontmatter contains description" if has_description else "Missing Markdown frontmatter description",
    ))

    behavior_metadata = [key for key in _BEHAVIOR_FRONTMATTER if re.search(rf"^{key}\s*:", frontmatter or "", re.MULTILINE)]
    checks.append(_check(
        "custom-command.no_behavior_frontmatter",
        "custom_markdown_frontmatter",
        not behavior_metadata,
        "No behavior-changing harness frontmatter" if not behavior_metadata else f"Behavior-changing frontmatter: {', '.join(behavior_metadata)}",
        {"unsupported": behavior_metadata},
    ))

    repository = case_id in _REPOSITORY_CASES
    repository_argument = re.search(r"\$ARGUMENTS|\$\d+", markdown)
    any_argument = re.search(r"\$ARGUMENTS|\$@|\$\d+|\$\{@:\d+(?::\d+)?\}|\$\{(?:\d+|@|ARGUMENTS):-[^}]*\}", markdown)
    argument = repository_argument if repository else any_argument
    checks.append(_check(
        "custom-command.arguments",
        "custom_arguments",
        argument is not None,
        f"Uses {'repository' if repository else 'Pi'} argument placeholder {argument.group(0)}" if argument else "Does not use accepted argument placeholder",
    ))

    if repository:
        unsupported = re.findall(r"\$@|\$\{@:\d+(?::\d+)?\}", markdown)
        checks.append(_check(
            "custom-command.repository_placeholders",
            "custom_arguments",
            not unsupported,
            "Repository source uses no $@ or slicing" if not unsupported else f"Unsupported repository placeholders: {', '.join(unsupported)}",
            {"unsupported": unsupported},
        ))

    shell_interpolation = re.search(r"!`[^`]+`", markdown)
    checks.append(_check(
        "custom-command.no_required_shell_interpolation",
        "custom_pi_command",
        shell_interpolation is None,
        "Does not require legacy shell interpolation" if shell_interpolation is None else "Requires legacy !`...` shell interpolation",
    ))

    required_at_file = re.search(r"(?<![\w$])@[\w./-]+", markdown)
    checks.append(_check(
        "custom-command.no_required_at_file",
        "custom_pi_command",
        required_at_file is None,
        "Does not require implicit @file inclusion" if required_at_file is None else f"Requires implicit @file inclusion: {required_at_file.group(0)}",
    ))

    declared_skills = _declared_skills(frontmatter)
    if declared_skills:
        missing = [skill for skill in declared_skills if not _body_loads_skill(body, skill)]
        checks.append(_check(
            "custom-command.explicit_skill_loading",
            "custom_skill_loading",
            not missing,
            "Body explicitly loads/follows declared skills" if not missing else f"Body lacks explicit loading for: {', '.join(missing)}",
            {"declared": declared_skills, "missing": missing},
        ))

    if case_id == "5":
        baseline_ok = bool(re.search(r"\breview\b", body, re.IGNORECASE) and re.search(r"bug|correctness|test|security|maintain", body, re.IGNORECASE))
        checks.append(_check(
            "custom-command.baseline_behavior",
            "custom_portable_behavior",
            baseline_ok,
            "Body preserves baseline review behavior when metadata is ignored" if baseline_ok else "Body delegates core review behavior to metadata",
        ))

    source_path = str(source.get("path") or "")
    if repository:
        canonical = _CANONICAL_PATHS[case_id]
        canonical_ok = canonical in response or source_path == canonical
        checks.append(_check(
            "custom-command.canonical_source",
            "custom_repository_ownership",
            canonical_ok,
            f"Names canonical Pi source {canonical}" if canonical_ok else f"Missing canonical Pi source {canonical}",
            {"canonical": canonical, "artifact_path": source_path},
        ))
        activation_ok = bool(re.search(r"\bsymlinks?\b|\bpi\.prompts\b|package (?:discovery|manifest)|\.pi/prompts", response, re.IGNORECASE))
        generated_variant = bool(re.search(r"(?:build|generate|copy|sync)[^\n]*Pi[^\n]*(?:variant|command|cop)", response, re.IGNORECASE))
        checks.append(_check(
            "custom-command.pi_activation",
            "custom_pi_activation",
            activation_ok and not generated_variant,
            "Uses package/native-path or symlink activation without generated variants" if activation_ok and not generated_variant else "Missing Pi activation guidance or recommends generated variants",
        ))
        checks.append(_check(
            "custom-command.install_paths",
            "custom_install_paths",
            activation_ok,
            "Includes Pi activation path or package discovery" if activation_ok else "Missing Pi activation path or package discovery",
        ))
    elif case_id in {"4", "6"}:
        local_path = "~/.pi/agent/prompts/inspect-session.md" if case_id == "4" else ".pi/prompts/inspect-project.md"
        local_ok = local_path in response
        not_repository = f"harness/pi/commands/{expected_filename}" not in response and not source_path.startswith("harness/pi/commands/")
        checks.append(_check(
            "custom-command.pi_local_scope",
            "custom_pi_local_scope",
            local_ok and not_repository,
            "Classifies Pi-local one-off outside repository commands" if local_ok and not_repository else "Does not clearly keep one-off in the requested Pi prompts directory",
        ))

    return checks


def _declared_skills(frontmatter: str) -> list[str]:
    skills: list[str] = []
    scalar = re.search(r"^skill\s*:\s*['\"]?([a-zA-Z0-9_-]+)", frontmatter, re.MULTILINE)
    if scalar:
        skills.append(scalar.group(1))
    inline = re.search(r"^skills\s*:\s*\[([^\]]+)\]", frontmatter, re.MULTILINE)
    if inline:
        skills.extend(re.findall(r"[a-zA-Z0-9_-]+", inline.group(1)))
    block = re.search(r"^skills\s*:\s*\n((?:\s+-\s+[^\n]+\n?)+)", frontmatter, re.MULTILINE)
    if block:
        skills.extend(re.findall(r"^\s+-\s+['\"]?([a-zA-Z0-9_-]+)", block.group(1), re.MULTILINE))
    return list(dict.fromkeys(skills))


def _body_loads_skill(body: str, skill: str) -> bool:
    escaped = re.escape(skill)
    return bool(re.search(rf"(?:load|use|follow)[^\n]*\b{escaped}\b|\b{escaped}\b[^\n]*(?:skill|workflow)", body, re.IGNORECASE))


def _command_source(response: str, context: dict[str, Any], expected_filename: str | None) -> dict[str, Any]:
    artifact = _read_markdown_artifact(context, expected_filename)
    if artifact:
        return artifact
    return {"kind": "response", "markdown": _extract_markdown_command(response), "filename": _extract_filename(response, expected_filename), "path": None}


def _read_markdown_artifact(context: dict[str, Any], expected_filename: str | None) -> dict[str, Any] | None:
    sandbox_path = context.get("sandbox_path")
    manifest = context.get("artifact_manifest") or {}
    if not sandbox_path:
        return None
    sandbox = Path(str(sandbox_path))
    files = [entry for entry in manifest.get("files", []) if str(entry.get("path", "")).endswith(".md")]

    def rank(entry: dict[str, Any]) -> tuple[int, str]:
        path = str(entry.get("path", ""))
        name = Path(path).name
        if expected_filename and name == expected_filename:
            return (0, path)
        return (1 if entry.get("change") in {"added", "modified"} else 2, path)

    for entry in sorted(files, key=rank):
        relative = str(entry.get("path", ""))
        path = sandbox / relative
        if path.exists() and path.is_file():
            return {"kind": "artifact", "markdown": path.read_text(), "filename": Path(relative).name, "path": relative}
    return None


def _extract_markdown_command(response: str) -> str:
    blocks = _fenced_blocks(response)
    for block in blocks:
        if block["label"].lower() in {"markdown", "md"} and _extract_frontmatter(block["content"]):
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
        label = opener.group(2).strip().split()[0] if opener.group(2).strip() else ""
        close_re = re.compile(rf"^{re.escape(fence[0])}{{{len(fence)},}}\s*$")
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


def _extract_body(markdown: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", markdown.strip(), count=1, flags=re.DOTALL)


def _extract_filename(response: str, expected_filename: str | None = None) -> str | None:
    candidates = _filename_candidates(response)
    if expected_filename and expected_filename in candidates:
        return expected_filename
    return next((candidate for candidate in candidates if re.fullmatch(r"[a-zA-Z0-9_-]+\.md", candidate)), None)


def _filename_candidates(response: str) -> list[str]:
    candidates: list[str] = []
    patterns = [r"(?:canonical\s+)?(?:recommended\s+)?filename\s*:\s*`?([a-zA-Z0-9_./~-]+\.md)`?", r"(?:canonical\s+)?(?:recommended\s+)?(?:file|path)\s*:\s*`?([a-zA-Z0-9_./~-]+\.md)`?"]
    for pattern in patterns:
        candidates.extend(match.group(1) for match in re.finditer(pattern, response, re.IGNORECASE))
    for block in _fenced_blocks(response):
        text = block["content"].strip()
        if re.fullmatch(r"[a-zA-Z0-9_./~-]+\.md", text):
            candidates.append(text)
    candidates.extend(match.group(1) for match in re.finditer(r"`([a-zA-Z0-9_./~-]+\.md)`", response))
    return list(dict.fromkeys(Path(candidate).name for candidate in candidates))


def _check(check_id: str, check_type: str, passed: bool, evidence: str, details: Any = None) -> dict[str, Any]:
    return {"id": check_id, "type": check_type, "status": "passed" if passed else "failed", "passed": passed, "evidence": evidence, "details": details}
