#!/usr/bin/env python3
"""Install only the owned reviewer link and model scope into a supplied Pi dir."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile


SOURCE = Path(__file__).resolve().parent


class InvalidInstall(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInstall("Duplicate JSON keys are not supported.")
        result[key] = value
    return result


def invalid_constant(_value):
    raise InvalidInstall("Non-finite JSON numbers are not supported.")


def finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise InvalidInstall("Non-finite JSON numbers are not supported.")
    return value


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=unique_object,
                           parse_constant=invalid_constant, parse_float=finite_float)
    except (ValueError, UnicodeError):
        raise InvalidInstall(f"Invalid JSON object: {path}") from None
    if not isinstance(value, dict):
        raise InvalidInstall(f"Expected a JSON object: {path}")
    return value


def validate_directory(path):
    if path.is_symlink():
        raise InvalidInstall(f"Refusing symlinked install directory: {path}")
    if path.exists() and not path.is_dir():
        raise InvalidInstall(f"Expected an install directory: {path}")


def plan(agent_dir):
    # Validate both inputs and destination types before creating even a directory.
    overlay = read_json(SOURCE / "settings-overlay.json")
    expected = {"subagents": {"modelScope": {
        "enforce": True, "strict": True, "allow": ["inherit"],
    }}}
    if json.dumps(overlay, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise InvalidInstall("The settings overlay must contain only the strict inherit scope.")
    reviewer_source = SOURCE / "reviewer.md"
    if not reviewer_source.is_file():
        raise InvalidInstall(f"Missing reviewer source: {reviewer_source}")
    validate_directory(agent_dir)
    validate_directory(agent_dir / "agents")
    settings = agent_dir / "settings.json"
    reviewer = agent_dir / "agents/reviewer.md"
    if settings.is_symlink():
        raise InvalidInstall(f"Refusing symlinked settings: {settings}")
    if settings.exists() and not settings.is_file():
        raise InvalidInstall(f"Expected a regular settings file: {settings}")
    if reviewer.exists() and not reviewer.is_symlink() and not reviewer.is_file():
        raise InvalidInstall(f"Expected a reviewer file or symlink: {reviewer}")
    current = read_json(settings) if settings.exists() else {}
    subagents = current.get("subagents", {})
    if not isinstance(subagents, dict):
        raise InvalidInstall("settings.json subagents must be an object; refusing to replace it.")
    scope = overlay["subagents"]["modelScope"]
    settings_changed = (json.dumps(subagents.get("modelScope"), sort_keys=True)
                        != json.dumps(scope, sort_keys=True))
    merged = {**current, "subagents": {**subagents, "modelScope": scope}}
    reviewer_changed = not (reviewer.is_symlink()
                            and os.readlink(reviewer) == str(reviewer_source))
    return settings, merged, settings_changed, reviewer, reviewer_source, reviewer_changed


def private_file(path, kind):
    """Reserve a unique sibling with mode 0600; never reuse a backup name."""
    fd, name = tempfile.mkstemp(prefix=f"{path.name}.{kind}.", dir=path.parent)
    return fd, Path(name)


def write_settings(settings, merged):
    if settings.exists():
        fd, backup = private_file(settings, "backup")
        with os.fdopen(fd, "wb") as stream:
            stream.write(settings.read_bytes())
        print(f"Backed up settings: {backup}")
    fd, temporary = private_file(settings, "pending")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(merged, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, settings)
    finally:
        temporary.unlink(missing_ok=True)


def link_reviewer(reviewer, source):
    # A private sibling directory holds the new link until the final rename.
    with tempfile.TemporaryDirectory(prefix=".reviewer-link.", dir=reviewer.parent) as directory:
        temporary = Path(directory) / "reviewer.md"
        temporary.symlink_to(source)
        backup = None
        if reviewer.exists() or reviewer.is_symlink():
            fd, backup = private_file(reviewer, "backup")
            os.close(fd)
            os.replace(reviewer, backup)  # Preserve a conflicting symlink, not its referent.
            print(f"Backed up reviewer: {backup}")
        try:
            os.replace(temporary, reviewer)
        except OSError:
            if backup is not None:
                os.replace(backup, reviewer)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-dir", required=True, type=Path,
                        help="explicit Pi agent directory; no implicit home target")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true",
                        help="read-only plan: exit 0 if installed, 1 if changes needed, 2 if invalid")
    action.add_argument("--apply", action="store_true",
                        help="authorize the merge/link and backups shown by --check")
    args = parser.parse_args()
    agent_dir = args.agent_dir.expanduser().absolute()
    try:
        settings, merged, settings_changed, reviewer, source, reviewer_changed = plan(agent_dir)
        print(f"LINK {source} -> {reviewer}"
              f" ({'create or back up existing' if reviewer_changed else 'unchanged'})")
        print('MERGE subagents.modelScope = {"enforce":true,"strict":true,"allow":["inherit"]}'
              f" -> {settings} ({'update; back up existing' if settings_changed else 'unchanged'})")
        if args.check:
            return int(settings_changed or reviewer_changed)
        if settings_changed:
            agent_dir.mkdir(parents=True, exist_ok=True)
            write_settings(settings, merged)
        if reviewer_changed:
            reviewer.parent.mkdir(parents=True, exist_ok=True)
            link_reviewer(reviewer, source)
        print("Subagent policy installed." if settings_changed or reviewer_changed
              else "Subagent policy already installed.")
        return 0
    except InvalidInstall as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except OSError as error:
        # Paths and OS error names are useful; settings contents are never printed.
        print(f"ERROR: filesystem operation failed ({error.strerror}); inspect {agent_dir}"
              " and any reported backups before retrying.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
