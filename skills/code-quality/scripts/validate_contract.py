#!/usr/bin/env python3
"""Dependency-free semantic validation for code-quality packet/result contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

FOCI = {"security", "logic", "types", "data", "resources", "style", "react", "tests"}
STATUSES = {"FINDINGS", "PASS", "NOT_APPLICABLE", "BLOCKED"}
SEVERITIES = {"Blocker", "Major", "Minor", "Suggestion", "Nit"}
CATEGORIES = {
    "Correctness", "Data integrity", "Security", "Reliability",
    "Performance", "Maintainability", "Testing", "Style",
}
FILE_STATUSES = {"added", "modified", "renamed", "deleted", "untracked"}
RESULT_FIELDS = {
    "schema_version", "review_id", "focus", "status", "summary",
    "files_reviewed", "coverage_notes", "analyzer", "findings",
}
FINDING_FIELDS = {
    "id", "severity", "category", "title", "anchor", "supporting_locations",
    "evidence", "trace", "impact", "fix_direction",
}
LOCATION_FIELDS = {"path", "line", "note"}
ANALYZER_FIELDS = {"command", "status", "notes"}


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("root must be an object")
    return value


def require(obj: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(fields - obj.keys())
    if missing:
        raise ContractError(f"{label} missing fields: {', '.join(missing)}")


def reject_unknown(obj: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(obj.keys() - allowed)
    if unknown:
        raise ContractError(f"{label} has unknown fields: {', '.join(unknown)}")


def require_string(value: Any, label: str, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ContractError(f"{label} must be a{' possibly empty' if allow_empty else ' non-empty'} string")


def require_string_array(value: Any, label: str) -> None:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    for index, item in enumerate(value):
        require_string(item, f"{label}[{index}]")


def resolve_artifact(packet_dir: Path, artifact_root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else packet_dir / path).resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError as exc:
        raise ContractError(f"artifact escapes artifact_root: {value}") from exc
    if not resolved.is_file():
        raise ContractError(f"artifact missing: {resolved}")
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_packet(path: Path, check_drift: bool = True) -> dict[str, Any]:
    packet = load_json(path)
    require(packet, {
        "schema_version", "review_id", "source_kind", "artifact_root", "source_root",
        "diff_artifact", "changed_files", "instructions", "workflow_context",
    }, "packet")
    if packet["schema_version"] != 1:
        raise ContractError("packet schema_version must be 1")
    if packet["source_kind"] not in {"local", "pull_request"}:
        raise ContractError("invalid source_kind")
    packet_dir = path.resolve().parent
    artifact_root = Path(packet["artifact_root"]).resolve()
    source_root = Path(packet["source_root"]).resolve()
    if not artifact_root.is_dir() or not source_root.is_dir():
        raise ContractError("artifact_root and source_root must be directories")
    resolve_artifact(packet_dir, artifact_root, packet["diff_artifact"])
    files = packet["changed_files"]
    if not isinstance(files, list) or not files:
        raise ContractError("changed_files must be non-empty")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ContractError("changed_files entries must be objects")
        require(item, {"path", "status", "patch_artifact", "line_ranges"}, "changed file")
        rel = item["path"]
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ContractError(f"invalid changed path: {rel}")
        if rel in seen:
            raise ContractError(f"duplicate changed path: {rel}")
        seen.add(rel)
        if item["status"] not in FILE_STATUSES:
            raise ContractError(f"invalid file status: {item['status']}")
        resolve_artifact(packet_dir, artifact_root, item["patch_artifact"])
        previous = item.get("previous_artifact")
        if previous:
            resolve_artifact(packet_dir, artifact_root, previous)
        ranges = item["line_ranges"]
        if not isinstance(ranges, list) or not ranges:
            raise ContractError(f"line_ranges missing for {rel}")
        for line_range in ranges:
            if not isinstance(line_range, dict) or set(line_range) != {"start", "end"}:
                raise ContractError(f"invalid line range for {rel}")
            if not isinstance(line_range["start"], int) or not isinstance(line_range["end"], int):
                raise ContractError(f"non-integer line range for {rel}")
            if line_range["start"] < 1 or line_range["end"] < line_range["start"]:
                raise ContractError(f"invalid line range bounds for {rel}")
        expected_hash = item.get("sha256")
        current = source_root / rel
        if packet["source_kind"] == "local" and check_drift and item["status"] != "deleted":
            if not expected_hash or not current.is_file() or sha256(current) != expected_hash:
                raise ContractError(f"source drift detected: {rel}")
        if packet["source_kind"] == "pull_request" and item["status"] != "deleted" and not current.is_file():
            raise ContractError(f"head source missing: {rel}")
    for instruction in packet["instructions"]:
        resolve_artifact(packet_dir, artifact_root, instruction)
    return packet


def validate_location(location: Any, label: str) -> None:
    if not isinstance(location, dict):
        raise ContractError(f"{label} must be an object")
    require(location, {"path", "line"}, label)
    reject_unknown(location, LOCATION_FIELDS, label)
    if not isinstance(location["path"], str) or not location["path"]:
        raise ContractError(f"{label} path invalid")
    if type(location["line"]) is not int or location["line"] < 1:
        raise ContractError(f"{label} line invalid")
    if "note" in location and location["note"] is not None:
        require_string(location["note"], f"{label} note", allow_empty=True)


def validate_result(path: Path, packet_path: Path | None, focus: str | None) -> dict[str, Any]:
    result = load_json(path)
    require(result, {
        "schema_version", "review_id", "focus", "status", "summary",
        "files_reviewed", "coverage_notes", "findings",
    }, "result")
    reject_unknown(result, RESULT_FIELDS, "result")
    if result["schema_version"] != 1 or result["focus"] not in FOCI or result["status"] not in STATUSES:
        raise ContractError("invalid result schema_version, focus, or status")
    require_string(result["review_id"], "result review_id")
    require_string(result["summary"], "result summary")
    require_string_array(result["files_reviewed"], "result files_reviewed")
    require_string_array(result["coverage_notes"], "result coverage_notes")
    if focus and result["focus"] != focus:
        raise ContractError(f"result focus {result['focus']} does not match {focus}")
    findings = result["findings"]
    if not isinstance(findings, list):
        raise ContractError("findings must be an array")
    if result["status"] == "FINDINGS" and not findings:
        raise ContractError("FINDINGS status requires findings")
    if result["status"] != "FINDINGS" and findings:
        raise ContractError(f"{result['status']} status cannot contain findings")
    analyzer = result.get("analyzer")
    if analyzer is not None:
        if not isinstance(analyzer, dict):
            raise ContractError("react result requires analyzer status")
        require(analyzer, {"command", "status", "notes"}, "react analyzer")
        reject_unknown(analyzer, ANALYZER_FIELDS, "react analyzer")
        require_string(analyzer["command"], "react analyzer command")
        require_string(analyzer["notes"], "react analyzer notes", allow_empty=True)
        if analyzer["status"] not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
            raise ContractError("invalid react analyzer status")
    if result["focus"] == "react" and analyzer is None:
        raise ContractError("react result requires analyzer status")
    packet = validate_packet(packet_path) if packet_path else None
    if packet and result["review_id"] != packet["review_id"]:
        raise ContractError("result review_id does not match packet")
    ranges = {
        item["path"]: item["line_ranges"]
        for item in packet["changed_files"]
    } if packet else {}
    ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise ContractError("finding must be an object")
        require(finding, {
            "id", "severity", "category", "title", "anchor", "supporting_locations",
            "evidence", "trace", "impact", "fix_direction",
        }, "finding")
        reject_unknown(finding, FINDING_FIELDS, "finding")
        require_string(finding["id"], "finding id")
        require_string(finding["title"], "finding title")
        if finding["id"] in ids:
            raise ContractError(f"duplicate finding id: {finding['id']}")
        ids.add(finding["id"])
        if finding["severity"] not in SEVERITIES or finding["category"] not in CATEGORIES:
            raise ContractError("invalid finding severity or category")
        if finding["severity"] == "Nit" and result["focus"] != "style":
            raise ContractError("only style may emit Nit by default")
        validate_location(finding["anchor"], "anchor")
        if packet:
            anchor = finding["anchor"]
            if anchor["path"] not in ranges or not any(
                line_range["start"] <= anchor["line"] <= line_range["end"]
                for line_range in ranges[anchor["path"]]
            ):
                raise ContractError(f"anchor is not a changed line: {anchor}")
        if not isinstance(finding["supporting_locations"], list):
            raise ContractError("supporting_locations must be an array")
        for location in finding["supporting_locations"]:
            validate_location(location, "supporting location")
        for field in ("evidence", "impact", "fix_direction"):
            require_string(finding[field], f"finding {field}")
        if not isinstance(finding["trace"], list) or not finding["trace"]:
            raise ContractError("finding trace must be non-empty")
        require_string_array(finding["trace"], "finding trace")
    return result


def validate_result_errors(
    path: Path, packet_path: Path | None, focus: str | None
) -> list[str]:
    """Return all independently actionable top-level result contract errors.

    The strict validator intentionally fails fast. Response gates use this companion
    diagnostic pass so a reviewer's single retry can correct every visible shape and
    enum violation instead of discovering them one at a time.
    """
    try:
        result = load_json(path)
    except ContractError as exc:
        return [str(exc)]

    errors: list[str] = []
    required = {
        "schema_version", "review_id", "focus", "status", "summary",
        "files_reviewed", "coverage_notes", "findings",
    }
    missing = sorted(required - result.keys())
    if missing:
        errors.append(f"result missing fields: {', '.join(missing)}")
    unknown = sorted(result.keys() - RESULT_FIELDS)
    if unknown:
        errors.append(f"result has unknown fields: {', '.join(unknown)}")

    if "schema_version" in result and result["schema_version"] != 1:
        errors.append("result schema_version must be 1")
    if "focus" in result and result["focus"] not in FOCI:
        errors.append(f"invalid result focus: {result['focus']!r}")
    if focus and "focus" in result and result["focus"] in FOCI and result["focus"] != focus:
        errors.append(f"result focus {result['focus']} does not match {focus}")
    if "status" in result and result["status"] not in STATUSES:
        errors.append(
            f"invalid result status: {result['status']!r}; expected one of {', '.join(sorted(STATUSES))}"
        )

    for field in ("review_id", "summary"):
        if field in result:
            try:
                require_string(result[field], f"result {field}")
            except ContractError as exc:
                errors.append(str(exc))
    for field in ("files_reviewed", "coverage_notes"):
        if field in result:
            try:
                require_string_array(result[field], f"result {field}")
            except ContractError as exc:
                errors.append(str(exc))
    if "findings" in result and not isinstance(result["findings"], list):
        errors.append("findings must be an array")

    analyzer = result.get("analyzer")
    if result.get("focus") == "react" and analyzer is None:
        errors.append("react result requires analyzer status")
    if analyzer is not None:
        if not isinstance(analyzer, dict):
            errors.append("react analyzer must be an object")
        else:
            analyzer_required = {"command", "status", "notes"}
            analyzer_missing = sorted(analyzer_required - analyzer.keys())
            if analyzer_missing:
                errors.append(f"react analyzer missing fields: {', '.join(analyzer_missing)}")
            analyzer_unknown = sorted(analyzer.keys() - ANALYZER_FIELDS)
            if analyzer_unknown:
                errors.append(f"react analyzer has unknown fields: {', '.join(analyzer_unknown)}")
            if "command" in analyzer:
                try:
                    require_string(analyzer["command"], "react analyzer command")
                except ContractError as exc:
                    errors.append(str(exc))
            if "notes" in analyzer:
                try:
                    require_string(analyzer["notes"], "react analyzer notes", allow_empty=True)
                except ContractError as exc:
                    errors.append(str(exc))
            if "status" in analyzer and analyzer["status"] not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
                errors.append(
                    f"invalid react analyzer status: {analyzer['status']!r}; expected one of FAIL, NOT_APPLICABLE, PASS"
                )

    if errors:
        return errors
    try:
        validate_result(path, packet_path, focus)
    except ContractError as exc:
        return [str(exc)]
    return []


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        artifacts = root / "artifacts"
        source.mkdir()
        artifacts.mkdir()
        changed = source / "a.ts"
        changed.write_text("const value = false;\n")
        (artifacts / "diff.patch").write_text("+const value = false;\n")
        (artifacts / "a.patch").write_text("+const value = false;\n")
        packet = {
            "schema_version": 1, "review_id": "self-test", "source_kind": "local",
            "artifact_root": str(artifacts), "source_root": str(source),
            "diff_artifact": "diff.patch", "base": None, "head": None,
            "changed_files": [{
                "path": "a.ts", "status": "modified", "previous_path": None,
                "patch_artifact": "a.patch", "previous_artifact": None,
                "sha256": sha256(changed), "line_ranges": [{"start": 1, "end": 1}],
            }],
            "instructions": [], "workflow_context": {},
        }
        packet_path = artifacts / "packet.json"
        packet_path.write_text(json.dumps(packet))
        validate_packet(packet_path)
        result = {
            "schema_version": 1, "review_id": "self-test", "focus": "logic",
            "status": "PASS", "summary": "No logic issues.", "files_reviewed": ["a.ts"],
            "coverage_notes": [], "analyzer": None, "findings": [],
        }
        result_path = artifacts / "result.json"
        result_path.write_text(json.dumps(result))
        validate_result(result_path, packet_path, "logic")

        invalid_result = dict(result)
        invalid_result["status"] = "FINDINGS"
        invalid_result["findings"] = [{
            "id": "outside-change", "severity": "Blocker", "category": "Correctness",
            "title": "Invalid anchor", "anchor": {"path": "a.ts", "line": 2},
            "supporting_locations": [], "evidence": "Evidence", "trace": ["Trace"],
            "impact": "Impact", "fix_direction": "Fix",
        }]
        result_path.write_text(json.dumps(invalid_result))
        try:
            validate_result(result_path, packet_path, "logic")
        except ContractError:
            pass
        else:
            raise ContractError("self-test failed to reject unchanged-line anchor")

        malformed_result = dict(result)
        malformed_result["summary"] = 0
        malformed_result["extra"] = True
        result_path.write_text(json.dumps(malformed_result))
        try:
            validate_result(result_path, packet_path, "logic")
        except ContractError:
            pass
        else:
            raise ContractError("self-test failed to reject schema-invalid result")

        changed.write_text("const value = true;\n")
        try:
            validate_packet(packet_path)
        except ContractError:
            pass
        else:
            raise ContractError("self-test failed to detect local source drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["packet", "result", "self-test"])
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--focus", choices=sorted(FOCI))
    parser.add_argument("--no-drift", action="store_true")
    args = parser.parse_args()
    try:
        if args.kind == "self-test":
            self_test()
        elif args.kind == "packet":
            if not args.path:
                raise ContractError("packet path required")
            validate_packet(args.path, check_drift=not args.no_drift)
        else:
            if not args.path:
                raise ContractError("result path required")
            validate_result(args.path, args.packet, args.focus)
    except ContractError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, separators=(",", ":")))
        return 1
    print(json.dumps({"valid": True}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
