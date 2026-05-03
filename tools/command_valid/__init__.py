from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

VALID_EXIT = 0
INVALID_EXIT = 1
USAGE_OR_RESOLUTION_EXIT = 2

COMMAND_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER_FIELDS = frozenset({"description", "argument-hint", "model", "thinking", "skill", "restore"})
VALID_THINKING_LEVELS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh"})
VALID_RESTORE_VALUES = frozenset({"true", "false"})
RESERVED_COMMAND_NAMES = frozenset(
    {
        "clear",
        "clone",
        "compact",
        "exit",
        "fork",
        "help",
        "login",
        "model",
        "new",
        "quit",
        "reload",
        "resume",
        "settings",
        "tree",
    }
)


@dataclass(frozen=True)
class CommandValidationOptions:
    command_name: str | None
    repo_root: Path | str = Path.cwd()
    commands_dir: Path | str | None = None


@dataclass(frozen=True)
class CommandValidationResult:
    valid: bool
    status: str
    command: str | None
    path: str | None
    errors: list[dict[str, str]]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "status": self.status,
            "command": self.command,
            "path": self.path,
            "errors": self.errors,
        }


def validate_command(options: CommandValidationOptions) -> tuple[int, CommandValidationResult]:
    repo_root = Path(options.repo_root).expanduser().resolve()
    commands_dir = _resolve_commands_dir(repo_root, options.commands_dir)
    command_name = options.command_name

    if command_name is None or command_name == "":
        return _usage_result(command_name, "Command name is required.")
    if not COMMAND_NAME_RE.fullmatch(command_name):
        return _invalid_result(command_name, "Command name must be lowercase kebab-case: letters, numbers, and single hyphens only.")
    if command_name in RESERVED_COMMAND_NAMES:
        return _invalid_result(command_name, f"Command name is reserved by Pi: {command_name}", code="reserved_name")

    command_path = commands_dir / f"{command_name}.md"
    if not command_path.exists() or not command_path.is_file():
        return _resolution_result(command_name, f"Command file not found: {_display_path(command_path, repo_root)}")
    try:
        path_display = _display_path(command_path.resolve(), repo_root)
    except OSError:
        path_display = _display_path(command_path, repo_root)
    try:
        text = command_path.read_text()
    except OSError as exc:
        return _resolution_result(command_name, f"Command file is not readable: {path_display}: {exc}")

    errors = _validate_markdown_contract(text, command_name, repo_root)
    if errors:
        return INVALID_EXIT, CommandValidationResult(False, "invalid", command_name, path_display, errors)
    return VALID_EXIT, CommandValidationResult(True, "passed", command_name, path_display, [])


def _resolve_commands_dir(repo_root: Path, commands_dir: Path | str | None) -> Path:
    if commands_dir is None:
        return repo_root / "commands"
    path = Path(commands_dir).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve(strict=False)


def _usage_result(command_name: str | None, message: str) -> tuple[int, CommandValidationResult]:
    return USAGE_OR_RESOLUTION_EXIT, CommandValidationResult(False, "usage_error", command_name, None, [_error("usage", message)])


def _invalid_result(command_name: str, message: str, *, code: str = "invalid_name") -> tuple[int, CommandValidationResult]:
    return INVALID_EXIT, CommandValidationResult(False, "invalid", command_name, None, [_error(code, message)])


def _resolution_result(command_name: str, message: str) -> tuple[int, CommandValidationResult]:
    return USAGE_OR_RESOLUTION_EXIT, CommandValidationResult(False, "resolution_error", command_name, None, [_error("not_found", message)])


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _validate_markdown_contract(text: str, command_name: str, repo_root: Path) -> list[dict[str, str]]:
    parsed, body, parse_errors = _parse_frontmatter(text, command_name)
    errors = list(parse_errors)
    description = parsed.get("description") if parsed else None
    if description is None or description.strip() == "":
        errors.append(_error("missing_description", "Command frontmatter must include a non-empty scalar description."))
    for key in parsed:
        if key not in ALLOWED_FRONTMATTER_FIELDS:
            errors.append(_error("unknown_frontmatter", f"Unsupported frontmatter field for Pi extended commands: {key}"))
    thinking = parsed.get("thinking")
    if thinking and thinking not in VALID_THINKING_LEVELS:
        errors.append(_error("invalid_thinking", f"Invalid thinking value {thinking!r}; expected one of: {', '.join(sorted(VALID_THINKING_LEVELS))}."))
    restore = parsed.get("restore")
    if restore and restore not in VALID_RESTORE_VALUES:
        errors.append(_error("invalid_restore", "Invalid restore value; expected true or false."))
    skill = parsed.get("skill")
    if skill and not _local_skill_exists(repo_root, skill):
        errors.append(_error("missing_skill", f"Declared skill does not resolve to a readable local skill: {skill}"))
    if re.search(r"!`[^`]*`", body):
        errors.append(_error("unsupported_body_syntax", "Unsupported legacy shell expansion syntax is not valid in clean Pi commands."))
    if re.search(r"(?<!\\)@(?:[A-Za-z0-9_./~-]+)", body):
        errors.append(_error("unsupported_body_syntax", "Unsupported legacy file expansion syntax is not valid in clean Pi commands."))
    if re.search(r"\$\{@:[^}]+\}", body):
        errors.append(_error("unsupported_placeholder", "Unsupported placeholder slicing syntax is not valid in clean Pi commands."))
    return errors


def _parse_frontmatter(text: str, command_name: str) -> tuple[dict[str, str], str, list[dict[str, str]]]:
    if not text.startswith("---\n"):
        return {}, text, [_error("missing_frontmatter", "Command file must start with scalar YAML frontmatter delimited by ---.")]
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text, [_error("malformed_frontmatter", "Command frontmatter must close with ---." )]
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\r\n")
    values: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*)", stripped)
        if not match:
            errors.append(_error("malformed_frontmatter", f"Malformed frontmatter line in /{command_name}: {stripped}"))
            continue
        key, value = match.group(1), match.group(2).strip()
        if value == "":
            errors.append(_error("non_scalar_frontmatter", f"Frontmatter field must be a non-empty scalar: {key}"))
        values[key] = _unquote_scalar(value)
    return values, body, errors


def _unquote_scalar(value: str) -> str:
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def _local_skill_exists(repo_root: Path, skill_name: str) -> bool:
    candidates = [
        repo_root / "skills" / skill_name / "SKILL.md",
        repo_root / ".agents" / "skills" / skill_name / "SKILL.md",
        repo_root / ".pi" / "skills" / skill_name / "SKILL.md",
        Path.home() / ".agents" / "skills" / skill_name / "SKILL.md",
        Path.home() / ".pi" / "agent" / "skills" / skill_name / "SKILL.md",
    ]
    return any(path.is_file() for path in candidates)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def format_friendly(result: CommandValidationResult) -> str:
    if result.valid:
        return f"PASS command_valid: /{result.command} -> {result.path}\n"
    lines = [f"FAIL command_valid: {result.status}"]
    if result.command:
        lines.append(f"Command: /{result.command}")
    for error in result.errors:
        lines.append(f"- {error['message']}")
    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(description="Validate one Pi extended command name.", add_help=True)
    parser.add_argument("command_name", nargs="?", help="Command name without leading slash or .md suffix")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root; defaults to current directory")
    parser.add_argument("--commands-dir", type=Path, help="Command library directory; defaults to <repo-root>/commands")
    parser.add_argument("--json", action="store_true", help="Emit compact machine-readable JSON")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else USAGE_OR_RESOLUTION_EXIT

    code, result = validate_command(
        CommandValidationOptions(
            command_name=args.command_name,
            repo_root=args.repo_root,
            commands_dir=args.commands_dir,
        )
    )
    if args.json:
        stdout.write(json.dumps(result.as_dict(), separators=(",", ":"), sort_keys=True) + "\n")
    else:
        stdout.write(format_friendly(result))
    stdout.flush()
    return code


__all__ = [
    "ALLOWED_FRONTMATTER_FIELDS",
    "COMMAND_NAME_RE",
    "RESERVED_COMMAND_NAMES",
    "VALID_RESTORE_VALUES",
    "VALID_THINKING_LEVELS",
    "CommandValidationOptions",
    "CommandValidationResult",
    "INVALID_EXIT",
    "USAGE_OR_RESOLUTION_EXIT",
    "VALID_EXIT",
    "format_friendly",
    "main",
    "validate_command",
]
