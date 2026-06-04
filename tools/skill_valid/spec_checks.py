from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
MAX_BODY_LINES = 500
ALLOWED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools", "disable-model-invocation"}


@dataclass(frozen=True)
class SpecCheck:
    id: str
    status: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status, "message": self.message}


def run_skill_spec_checks(skill_dir: Path) -> list[SpecCheck]:
    """Run deterministic shared Pi/OpenCode skill compatibility checks.

    Checks marked ``failed`` are shared loadability or repo contract violations.
    Checks marked ``warn`` are deterministic best-practice concerns that may
    reduce skill reliability but should not block live behavioral gates by
    themselves.
    """
    skill_dir = Path(skill_dir)
    skill_file = skill_dir / "SKILL.md"
    checks: list[SpecCheck] = []

    try:
        text = skill_file.read_text()
    except OSError as exc:
        return [SpecCheck("skill-md.readable", "failed", f"SKILL.md could not be read: {exc}")]

    parsed = _parse_skill_markdown(text)
    if parsed["errors"]:
        checks.extend(SpecCheck(error_id, "failed", message) for error_id, message in parsed["errors"])
        return checks

    metadata: dict[str, Any] = parsed["metadata"]
    body: str = parsed["body"]
    checks.append(SpecCheck("frontmatter.present", "passed", "SKILL.md starts with closed YAML frontmatter."))
    checks.extend(_check_frontmatter_fields(metadata))
    checks.extend(_check_name(metadata.get("name"), skill_dir.name))
    checks.extend(_check_description(metadata.get("description")))
    checks.extend(_check_optional_fields(metadata))
    checks.extend(_check_body(body, metadata.get("description")))
    checks.extend(_check_references(skill_dir, body))
    return checks


def summarize_checks(checks: list[SpecCheck]) -> tuple[str, str]:
    failed = sum(1 for check in checks if check.status == "failed")
    warned = sum(1 for check in checks if check.status == "warn")
    passed = sum(1 for check in checks if check.status == "passed")
    message = f"Skill spec checks: {passed} passed, {warned} warning(s), {failed} failed."
    if failed:
        return "failed", message
    if warned:
        return "warn", message
    return "passed", message


def _parse_skill_markdown(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {"metadata": {}, "body": "", "errors": [("frontmatter.present", "SKILL.md must start with YAML frontmatter delimiter '---'.")]}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {"metadata": {}, "body": "", "errors": [("frontmatter.present", "SKILL.md must start with YAML frontmatter delimiter '---' on its own line.")]}

    closing_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return {"metadata": {}, "body": "", "errors": [("frontmatter.closed", "SKILL.md frontmatter must be closed with '---'.")]}

    frontmatter_lines = lines[1:closing_index]
    body = "\n".join(lines[closing_index + 1 :]).strip("\n")
    metadata, parse_errors = _parse_yaml_mapping(frontmatter_lines)
    if parse_errors:
        return {"metadata": metadata, "body": body, "errors": [("frontmatter.yaml", "; ".join(parse_errors))]}
    if not isinstance(metadata, dict):
        return {"metadata": {}, "body": body, "errors": [("frontmatter.mapping", "SKILL.md frontmatter must be a YAML mapping.")]}
    return {"metadata": metadata, "body": body, "errors": []}


def _parse_yaml_mapping(lines: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Parse the small YAML subset used by skill frontmatter.

    This intentionally avoids adding a PyYAML dependency to skill_valid. It
    supports top-level mappings, quoted/unquoted scalar values, literal/folded
    blocks, simple nested mappings, and block lists, which covers repo skills and
    the Agent Skills metadata shape.
    """
    result: dict[str, Any] = {}
    errors: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if _indent(line) != 0:
            errors.append(f"unexpected indentation at frontmatter line {index + 2}")
            index += 1
            continue
        if ":" not in line:
            errors.append(f"expected key: value at frontmatter line {index + 2}")
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value_text = raw_value.strip()
        if not key:
            errors.append(f"empty key at frontmatter line {index + 2}")
            index += 1
            continue
        if key in result:
            errors.append(f"duplicate key {key!r}")
        if value_text in {"|", ">"}:
            block, index = _collect_indented_block(lines, index + 1)
            value = _block_scalar(block, folded=value_text == ">")
        elif value_text == "":
            block, index = _collect_indented_block(lines, index + 1)
            value = _parse_nested_value(block)
        else:
            value = _parse_scalar(value_text)
            index += 1
        result[key] = value
    return result, errors


def _collect_indented_block(lines: list[str], start: int) -> tuple[list[str], int]:
    block: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.strip() and _indent(line) == 0:
            break
        block.append(line)
        index += 1
    return block, index


def _parse_nested_value(lines: list[str]) -> Any:
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return None
    min_indent = min(_indent(line) for line in non_empty)
    normalized = [line[min_indent:] if len(line) >= min_indent else "" for line in lines]
    first = next(line.strip() for line in normalized if line.strip())
    if first.startswith("- "):
        return [_parse_scalar(line.strip()[2:].strip()) for line in normalized if line.strip().startswith("- ")]
    nested, _ = _parse_yaml_mapping(normalized)
    return nested


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "''", '""'}:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _block_scalar(lines: list[str], *, folded: bool) -> str:
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""
    min_indent = min(_indent(line) for line in non_empty)
    stripped = [line[min_indent:] if len(line) >= min_indent else "" for line in lines]
    if folded:
        paragraphs = "\n".join(stripped).split("\n\n")
        return "\n\n".join(" ".join(part.splitlines()).strip() for part in paragraphs).strip()
    return "\n".join(stripped).strip("\n")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _check_frontmatter_fields(metadata: dict[str, Any]) -> list[SpecCheck]:
    checks: list[SpecCheck] = []
    extra = sorted(set(metadata) - ALLOWED_FIELDS)
    if extra:
        checks.append(SpecCheck("frontmatter.allowed-fields", "failed", f"Unexpected frontmatter field(s): {', '.join(extra)}."))
    else:
        checks.append(SpecCheck("frontmatter.allowed-fields", "passed", "Frontmatter uses only shared fields or safely ignored Pi capability fields."))
    for required in ("name", "description"):
        if required in metadata:
            checks.append(SpecCheck(f"frontmatter.{required}.present", "passed", f"Required field {required!r} is present."))
        else:
            checks.append(SpecCheck(f"frontmatter.{required}.present", "failed", f"Missing required frontmatter field: {required}."))
    return checks


def _check_name(value: Any, directory_name: str) -> list[SpecCheck]:
    checks: list[SpecCheck] = []
    if not isinstance(value, str) or not value.strip():
        return [SpecCheck("name.type", "failed", "Field 'name' must be a non-empty string.")]

    name = unicodedata.normalize("NFKC", value.strip())
    checks.append(SpecCheck("name.type", "passed", "Field 'name' is a non-empty string."))
    if len(name) <= MAX_SKILL_NAME_LENGTH:
        checks.append(SpecCheck("name.length", "passed", f"Skill name length is OK ({len(name)} chars)."))
    else:
        checks.append(SpecCheck("name.length", "failed", f"Skill name exceeds {MAX_SKILL_NAME_LENGTH} characters ({len(name)} chars)."))

    format_errors = []
    if name != name.lower():
        format_errors.append("must be lowercase")
    if name.startswith("-") or name.endswith("-"):
        format_errors.append("must not start or end with a hyphen")
    if "--" in name:
        format_errors.append("must not contain consecutive hyphens")
    if not all(char.isalnum() or char == "-" for char in name):
        format_errors.append("may contain only letters, digits, and hyphens")
    if format_errors:
        checks.append(SpecCheck("name.format", "failed", "Skill name " + "; ".join(format_errors) + "."))
    else:
        checks.append(SpecCheck("name.format", "passed", "Skill name format is valid."))

    if unicodedata.normalize("NFKC", directory_name) == name:
        checks.append(SpecCheck("name.directory-match", "passed", "Directory basename matches skill name."))
    else:
        checks.append(SpecCheck("name.directory-match", "failed", f"Directory basename {directory_name!r} must match skill name {name!r}."))

    if _contains_xml_tag(name):
        checks.append(SpecCheck("name.no-xml", "failed", "Skill name must not contain XML tags."))
    else:
        checks.append(SpecCheck("name.no-xml", "passed", "Skill name contains no XML tags."))

    return checks


def _check_description(value: Any) -> list[SpecCheck]:
    checks: list[SpecCheck] = []
    if not isinstance(value, str) or not value.strip():
        return [SpecCheck("description.type", "failed", "Field 'description' must be a non-empty string.")]
    description = value.strip()
    checks.append(SpecCheck("description.type", "passed", "Field 'description' is a non-empty string."))
    if len(description) <= MAX_DESCRIPTION_LENGTH:
        checks.append(SpecCheck("description.length", "passed", f"Description length is OK ({len(description)} chars)."))
    else:
        checks.append(SpecCheck("description.length", "failed", f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters ({len(description)} chars)."))

    if _contains_xml_tag(description):
        checks.append(SpecCheck("description.no-xml", "failed", "Description must not contain XML tags."))
    else:
        checks.append(SpecCheck("description.no-xml", "passed", "Description contains no XML tags."))

    if re.search(r"\b(use when|use this skill|whenever|when the user|asks? for|mentions?|trigger)", description, re.I):
        checks.append(SpecCheck("description.trigger-context", "passed", "Description includes trigger/use context."))
    else:
        checks.append(SpecCheck("description.trigger-context", "warn", "Description should say when to use the skill, not just what it does."))

    if re.search(r"\b(I can|I'll|my job|you can use this)\b", description, re.I):
        checks.append(SpecCheck("description.third-person", "warn", "Description should be written in third person for reliable skill discovery."))
    else:
        checks.append(SpecCheck("description.third-person", "passed", "Description appears to be third person."))

    if len(description.split()) < 8:
        checks.append(SpecCheck("description.specificity", "warn", "Description is very short; include concrete capabilities and keywords."))
    else:
        checks.append(SpecCheck("description.specificity", "passed", "Description has enough detail for discovery."))
    return checks


def _check_optional_fields(metadata: dict[str, Any]) -> list[SpecCheck]:
    checks: list[SpecCheck] = []
    if "compatibility" in metadata:
        value = metadata["compatibility"]
        if not isinstance(value, str) or not value.strip():
            checks.append(SpecCheck("compatibility.type", "failed", "Field 'compatibility' must be a non-empty string when present."))
        elif len(value) > MAX_COMPATIBILITY_LENGTH:
            checks.append(SpecCheck("compatibility.length", "failed", f"Compatibility exceeds {MAX_COMPATIBILITY_LENGTH} characters ({len(value)} chars)."))
        else:
            checks.append(SpecCheck("compatibility.valid", "passed", "Compatibility field is valid."))

    if "metadata" in metadata:
        value = metadata["metadata"]
        if not isinstance(value, dict):
            checks.append(SpecCheck("metadata.mapping", "failed", "Field 'metadata' must be a mapping when present."))
        else:
            checks.append(SpecCheck("metadata.mapping", "passed", "Metadata field is a mapping."))
            if any(not isinstance(key, str) for key in value):
                checks.append(SpecCheck("metadata.keys", "failed", "Metadata keys must be strings."))
            else:
                checks.append(SpecCheck("metadata.keys", "passed", "Metadata keys are strings."))
            if any(isinstance(item, (dict, list)) for item in value.values()):
                checks.append(SpecCheck("metadata.values", "warn", "Nested metadata values may be client-specific; prefer string values for broad compatibility."))
            else:
                checks.append(SpecCheck("metadata.values", "passed", "Metadata values are scalar/string-like."))

    if "license" in metadata:
        value = metadata["license"]
        if not isinstance(value, str) or not value.strip():
            checks.append(SpecCheck("license.type", "failed", "Field 'license' must be a non-empty string when present."))
        elif len(value) > 120:
            checks.append(SpecCheck("license.short", "warn", "License field should be short; reference a bundled license file for complete terms."))
        else:
            checks.append(SpecCheck("license.valid", "passed", "License field is concise."))

    if "allowed-tools" in metadata:
        value = metadata["allowed-tools"]
        if isinstance(value, str) and value.strip():
            checks.append(SpecCheck("allowed-tools.format", "passed", "allowed-tools is a space-delimited string."))
        elif isinstance(value, list) and value:
            checks.append(SpecCheck("allowed-tools.format", "warn", "Pi documents allowed-tools as a space-delimited string; list form may not behave as intended."))
        else:
            checks.append(SpecCheck("allowed-tools.format", "failed", "allowed-tools must be a non-empty space-delimited string if present."))

    if "disable-model-invocation" in metadata:
        value = metadata["disable-model-invocation"]
        if isinstance(value, bool):
            checks.append(SpecCheck("disable-model-invocation.type", "passed", "disable-model-invocation is a boolean."))
        else:
            checks.append(SpecCheck("disable-model-invocation.type", "failed", "disable-model-invocation must be true or false when present."))
    return checks


def _check_body(body: str, description: Any) -> list[SpecCheck]:
    checks: list[SpecCheck] = []
    line_count = len(body.splitlines())
    if line_count <= MAX_BODY_LINES:
        checks.append(SpecCheck("body.line-count", "passed", f"SKILL.md body is under {MAX_BODY_LINES} lines ({line_count})."))
    else:
        checks.append(SpecCheck("body.line-count", "warn", f"SKILL.md body is over {MAX_BODY_LINES} lines ({line_count}); use progressive disclosure."))

    if isinstance(description, str) and _normalized_words(body) == _normalized_words(description):
        checks.append(SpecCheck("body.not-description-only", "warn", "Body appears to merely repeat the description."))
    else:
        checks.append(SpecCheck("body.not-description-only", "passed", "Body adds instructions beyond the description."))

    generic_patterns = ("follow best practices", "handle errors appropriately", "as needed")
    found = [pattern for pattern in generic_patterns if pattern in body.lower()]
    if found:
        checks.append(SpecCheck("body.generic-fillers", "warn", f"Body contains generic filler phrase(s): {', '.join(found)}."))
    else:
        checks.append(SpecCheck("body.generic-fillers", "passed", "Body avoids common generic filler phrases."))
    return checks


def _check_references(skill_dir: Path, body: str) -> list[SpecCheck]:
    links = _markdown_links(body)
    relative_links = [(label, target) for label, target in links if _is_relative_reference(target)]
    checks: list[SpecCheck] = []
    if not relative_links:
        checks.append(SpecCheck("references.relative-links", "passed", "No relative Markdown resource links to validate."))
        return checks

    missing: list[str] = []
    windows_paths: list[str] = []
    deep_paths: list[str] = []
    outside_paths: list[str] = []
    long_without_toc: list[str] = []
    for _label, target in relative_links:
        path_part = target.split("#", 1)[0]
        if "\\" in path_part:
            windows_paths.append(target)
        if not path_part:
            continue
        path = Path(path_part)
        resolved = (skill_dir / path).resolve(strict=False)
        outside_skill = False
        try:
            resolved.relative_to(skill_dir.resolve(strict=False))
        except ValueError:
            outside_skill = True
        if not resolved.exists():
            missing.append(target)
            continue
        if outside_skill:
            outside_paths.append(target)
            continue
        if len(path.parts) > 2:
            deep_paths.append(target)
        if resolved.suffix.lower() == ".md":
            try:
                lines = resolved.read_text().splitlines()
            except OSError:
                continue
            preview = "\n".join(lines[:40]).lower()
            if len(lines) > 100 and "contents" not in preview and "table of contents" not in preview:
                long_without_toc.append(target)

    if missing:
        checks.append(SpecCheck("references.paths-exist", "failed", "Missing relative resource link target(s): " + ", ".join(sorted(missing)) + "."))
    else:
        checks.append(SpecCheck("references.paths-exist", "passed", "Relative Markdown resource links resolve."))
    if windows_paths:
        checks.append(SpecCheck("references.forward-slashes", "warn", "Use forward slashes in resource paths: " + ", ".join(sorted(windows_paths)) + "."))
    else:
        checks.append(SpecCheck("references.forward-slashes", "passed", "Relative resource links use forward slashes."))
    if deep_paths:
        checks.append(SpecCheck("references.one-level", "warn", "Keep SKILL.md references one level deep where possible: " + ", ".join(sorted(deep_paths)) + "."))
    else:
        checks.append(SpecCheck("references.one-level", "passed", "Relative resource links are at most one level deep."))
    if outside_paths:
        checks.append(SpecCheck("references.inside-skill", "warn", "Resource links that leave the skill directory may not package portably: " + ", ".join(sorted(outside_paths)) + "."))
    else:
        checks.append(SpecCheck("references.inside-skill", "passed", "Relative resource links stay inside the skill directory."))
    if long_without_toc:
        checks.append(SpecCheck("references.long-file-toc", "warn", "Reference file(s) over 100 lines should include a table of contents: " + ", ".join(sorted(long_without_toc)) + "."))
    else:
        checks.append(SpecCheck("references.long-file-toc", "passed", "Long linked reference files include a visible TOC or none are long."))
    return checks


def _markdown_links(text: str) -> list[tuple[str, str]]:
    return [(match.group(1), match.group(2).strip()) for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text)]


def _is_relative_reference(target: str) -> bool:
    if not target or target.startswith("#"):
        return False
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return False
    return True


def _contains_xml_tag(value: str) -> bool:
    return bool(re.search(r"<\s*/?\s*[A-Za-z][^>]*>", value))


def _normalized_words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))
