from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gate_result.py"
SPEC = importlib.util.spec_from_file_location("gate_result", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class GateResultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.artifacts = self.root / "artifacts"
        self.source.mkdir()
        self.artifacts.mkdir()
        changed = self.source / "a.ts"
        changed.write_text("const value = false;\n")
        (self.artifacts / "diff.patch").write_text("+const value = false;\n")
        (self.artifacts / "a.patch").write_text("+const value = false;\n")
        packet = {
            "schema_version": 1,
            "review_id": "review-1",
            "source_kind": "local",
            "artifact_root": str(self.artifacts),
            "source_root": str(self.source),
            "diff_artifact": "diff.patch",
            "changed_files": [
                {
                    "path": "a.ts",
                    "status": "modified",
                    "patch_artifact": "a.patch",
                    "sha256": hashlib.sha256(changed.read_bytes()).hexdigest(),
                    "line_ranges": [{"start": 1, "end": 1}],
                }
            ],
            "instructions": [],
            "workflow_context": {},
        }
        self.packet = self.artifacts / "packet.json"
        self.packet.write_text(json.dumps(packet))
        self.state = self.artifacts / "gate-logic.json"
        self.output = self.artifacts / "result-logic.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_raw(self, content: bytes) -> Path:
        path = self.root / "response.txt"
        path.write_bytes(content)
        return path

    def valid_result(self, **updates: object) -> bytes:
        value = {
            "schema_version": 1,
            "review_id": "review-1",
            "focus": "logic",
            "status": "PASS",
            "summary": "No findings.",
            "files_reviewed": ["a.ts"],
            "coverage_notes": [],
            "findings": [],
        }
        value.update(updates)
        return (json.dumps(value, indent=2) + "\n").encode()

    def invoke(self, raw: bytes, focus: str = "logic") -> dict[str, object]:
        return GATE.gate_result(
            packet_path=self.packet,
            focus=focus,
            raw_path=self.write_raw(raw),
            state_path=self.artifacts / f"gate-{focus}.json",
            output_path=self.artifacts / f"result-{focus}.json",
        )

    def test_accepts_and_preserves_valid_response_bytes(self) -> None:
        raw = self.valid_result()
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "accepted")
        self.assertEqual(self.output.read_bytes(), raw)
        self.assertEqual((self.artifacts / "raw-logic-attempt-1.txt").read_bytes(), raw)

    def test_accepts_markdown_wrapped_json(self) -> None:
        raw = b"```json\n" + self.valid_result().strip() + b"\n```\n"
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "accepted")
        self.assertTrue(outcome["normalized"])
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("```", self.output.read_text())

    def test_rejects_invalid_category_without_repairing_it(self) -> None:
        finding = {
            "id": "x",
            "severity": "Major",
            "category": "Data lifecycle",
            "title": "Bad category",
            "anchor": {"path": "a.ts", "line": 1},
            "supporting_locations": [],
            "evidence": "Evidence",
            "trace": ["Trace"],
            "impact": "Impact",
            "fix_direction": "Fix",
        }
        raw = self.valid_result(status="FINDINGS", findings=[finding])
        self.assertEqual(self.invoke(raw)["status"], "retry_required")
        self.assertFalse(self.output.exists())
        self.assertIn(b"Data lifecycle", (self.artifacts / "raw-logic-attempt-1.txt").read_bytes())

    def test_rejects_schema_invalid_types_and_unknown_fields(self) -> None:
        raw = self.valid_result(summary=0, extra=True)
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "retry_required")
        self.assertIn("unknown fields", str(outcome["error"]))
        self.assertIn("summary", str(outcome["error"]))

    def test_logic_retry_reports_missing_status_and_unknown_verdict_together(self) -> None:
        raw = json.dumps(
            {
                "schema_version": 1,
                "review_id": "review-1",
                "focus": "logic",
                "verdict": "pass",
                "summary": "No findings.",
                "findings": [],
            }
        ).encode()
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "retry_required")
        self.assertIn("missing fields: status", str(outcome["error"]))
        self.assertIn("unknown fields: verdict", str(outcome["error"]))
        self.assertEqual(self.invoke(self.valid_result())["status"], "accepted")

    def test_react_retry_reports_all_native_analyzer_shape_errors(self) -> None:
        raw = json.dumps(
            {
                "schema_version": 1,
                "review_id": "review-1",
                "focus": "react",
                "status": "passed",
                "findings": [],
                "analyzer": {
                    "name": "react-doctor",
                    "command": "npx -y react-doctor@latest . --verbose --diff",
                    "status": "completed",
                    "score": 84,
                    "issues_reported": 7,
                    "note": "No changed-scope issues.",
                },
            }
        ).encode()
        outcome = self.invoke(raw, "react")
        error = str(outcome["error"])
        self.assertEqual(outcome["status"], "retry_required")
        self.assertIn("missing fields: summary", error)
        self.assertIn("invalid result status: 'passed'", error)
        self.assertIn("react analyzer missing fields: notes", error)
        self.assertIn("react analyzer has unknown fields: issues_reported, name, note, score", error)
        self.assertIn("invalid react analyzer status: 'completed'", error)

        retry = self.valid_result(
            focus="react",
            analyzer={
                "command": "npx -y react-doctor@latest . --verbose --diff",
                "status": "PASS",
                "notes": "No changed-scope issues.",
            },
        )
        self.assertEqual(self.invoke(retry, "react")["status"], "accepted")

    def test_accepts_abbreviated_lowercase_status_response(self) -> None:
        raw = json.dumps(
            {"status": "pass", "findings": [], "summary": "No findings."}
        ).encode()
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "accepted")
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["review_id"], "review-1")

    def test_generates_summary_for_pass_without_findings(self) -> None:
        raw = json.dumps({"status": "pass", "findings": []}).encode()
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "accepted")
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["summary"], "No findings reported.")
        self.assertIn("generated summary from status", outcome["normalizations"])

    def test_generates_summary_for_valid_findings(self) -> None:
        finding = {
            "id": "x",
            "severity": "Major",
            "category": "Correctness",
            "title": "Broken behavior",
            "anchor": {"path": "a.ts", "line": 1},
            "supporting_locations": [],
            "evidence": "Evidence",
            "trace": ["Trace"],
            "impact": "Impact",
            "fix_direction": "Fix",
        }
        raw = json.dumps({"findings": [finding]}).encode()
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "accepted")
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["status"], "FINDINGS")
        self.assertEqual(result["summary"], "Reviewer reported 1 finding.")

    def test_generates_analyzer_for_non_applicable_react_focus(self) -> None:
        raw = json.dumps(
            {
                "focus": "react",
                "status": "not_applicable",
                "findings": [],
                "summary": "No React files changed.",
            }
        ).encode()
        outcome = self.invoke(raw, "react")
        self.assertEqual(outcome["status"], "accepted")
        output = self.artifacts / "result-react.json"
        result = GATE.VALIDATOR.validate_result(output, self.packet, "react")
        self.assertEqual(result["analyzer"]["status"], "NOT_APPLICABLE")
        self.assertEqual(result["analyzer"]["command"], "not run")

    def test_rejects_conflicting_focus_after_normalization(self) -> None:
        raw = self.valid_result(focus="style", status="pass")
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "retry_required")
        self.assertIn("does not match", str(outcome["error"]))

    def test_canonicalizes_finding_enums_and_fills_supporting_locations(self) -> None:
        finding = {
            "id": "x",
            "severity": "major",
            "category": "correctness",
            "title": "Broken behavior",
            "anchor": {"path": "a.ts", "line": 1},
            "evidence": "Evidence",
            "trace": ["Trace"],
            "impact": "Impact",
            "fix_direction": "Fix",
        }
        outcome = self.invoke(self.valid_result(status="findings", findings=[finding]))
        self.assertEqual(outcome["status"], "accepted")
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["findings"][0]["severity"], "Major")
        self.assertEqual(result["findings"][0]["category"], "Correctness")
        self.assertEqual(result["findings"][0]["supporting_locations"], [])

    def test_retries_then_blocks_response_without_json(self) -> None:
        raw = b"No structured result was returned."
        self.assertEqual(self.invoke(raw)["status"], "retry_required")
        self.assertEqual(self.invoke(raw)["status"], "blocked")
        result = GATE.VALIDATOR.validate_result(self.output, self.packet, "logic")
        self.assertEqual(result["status"], "BLOCKED")

    def test_resumes_when_raw_attempt_was_preserved_before_state_update(self) -> None:
        raw = b"not json"
        preserved = self.artifacts / "raw-logic-attempt-1.txt"
        preserved.write_bytes(raw)
        outcome = self.invoke(raw)
        self.assertEqual(outcome["status"], "retry_required")
        self.assertEqual(preserved.read_bytes(), raw)

    def test_rejects_conflicting_interrupted_attempt(self) -> None:
        (self.artifacts / "raw-logic-attempt-1.txt").write_bytes(b"first")
        with self.assertRaisesRegex(RuntimeError, "different content"):
            self.invoke(b"second")

    def test_rejects_wrong_identity_and_accepts_valid_retry(self) -> None:
        self.assertEqual(
            self.invoke(self.valid_result(review_id="wrong"))["status"], "retry_required"
        )
        retry = self.valid_result()
        self.assertEqual(self.invoke(retry)["status"], "accepted")
        self.assertEqual(self.output.read_bytes(), retry)

    def test_react_blocked_result_has_valid_analyzer(self) -> None:
        raw = b"not json"
        self.assertEqual(self.invoke(raw, "react")["status"], "retry_required")
        self.assertEqual(self.invoke(raw, "react")["status"], "blocked")
        output = self.artifacts / "result-react.json"
        result = GATE.VALIDATOR.validate_result(output, self.packet, "react")
        self.assertEqual(result["analyzer"]["status"], "NOT_APPLICABLE")

    def test_never_overwrites_finalized_result(self) -> None:
        original = b"existing"
        self.output.write_bytes(original)
        with self.assertRaisesRegex(RuntimeError, "already finalized"):
            self.invoke(self.valid_result())
        self.assertEqual(self.output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
