"""Check grading boundaries with fixed samples, not model-writing quality."""

import json
import unittest
from pathlib import Path

from tools.skill_eval.grading import grade_response
from tools.skill_eval.manifest import load_manifest


EVAL_DIR = Path(__file__).parent
REGRESSION_ID = "regression-workflow-readme-describes-current-behavior-with_skill"
PROTECTED_REGRESSION_ID = "regression-workflow-protect-non-prose-and-real-lists-with_skill"


def case_checks(suite_name, case_id):
    suite = load_manifest(EVAL_DIR / "manifest.json").suite(suite_name)
    return next(case.checks for case in suite.cases if case.id == case_id)


def passes_check(suite_name, case_id, check_id, response):
    checks = case_checks(suite_name, case_id)
    check = next(check for check in checks if check["id"] == check_id)
    return grade_response(response, [check])["passed"]


class HumanWritingCheckTests(unittest.TestCase):
    def test_effective_date_accepts_equivalent_formats_but_not_changed_dates(self):
        for text, expected in [
            ("As of 2026-06-10, the archive holds records.", True),
            ("As of June 10, 2026, the archive holds records.", True),
            ("As of 10 June 2026, the archive holds records.", True),
            ("As of Jun. 10th, 2026, the archive holds records.", True),
            ("As of 2026-06-11, the archive holds records.", False),
            ("As of July 10, 2026, the archive holds records.", False),
            ("As of June 10, 2025, the archive holds records.", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(passes_check("workflow", "preserve-factual-limits", "effective-date", text), expected)

    def test_lru_accepts_hyphenation_but_not_a_different_eviction_policy(self):
        for policy, expected in [
            ("least recently used", True),
            ("least-recently-used", True),
            ("least‑recently‑used", True),
            ("LRU", True),
            ("most recently used", False),
            ("MRU", False),
            ("oldest created entry", False),
        ]:
            with self.subTest(policy=policy):
                self.assertEqual(passes_check("regression", REGRESSION_ID, "eviction-policy-preserved", policy), expected)

    def test_uncertainty_applies_to_the_decade_not_just_the_exact_date(self):
        for text, expected in [
            ("The company may have been founded in the 1990s. Its exact founding date is unknown.", True),
            ("The 1990s founding period is an unverified estimate. Its exact founding date is unknown.", True),
            ("The company was probably founded in the 1990s, but its exact founding date is unknown.", True),
            ("An unverified estimate places the company's founding in the 1990s.", True),
            ("The company was founded in the 1990s. Its exact founding date is uncertain.", False),
            ("The company was founded in the 1990s, though its exact founding date is uncertain.", False),
            ("The exact founding date is uncertain, but the company was founded in the 1990s.", False),
            ("Available sources indicate that the company was founded in the 1990s, although the exact founding date is not documented.", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(passes_check("workflow", "missing-founding-date-stays-uncertain", "tentative-claim-preserved", text), expected)

    def test_evidence_gap_accepts_active_and_negative_forms(self):
        for text, expected in [
            ("Its exact founding date is not documented in the available sources.", True),
            ("The available sources do not document its exact founding date.", True),
            ("Available sources do not confirm this estimate or provide an exact founding date.", True),
            ("No exact founding date is documented in the sources available to us.", True),
            ("The sources don't provide an exact founding date.", True),
            ("The company may have been founded in the 1990s, but this is an unverified estimate.", False),
            ("The sources document the exact founding date.", False),
            ("Its exact founding date is known.", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(passes_check("workflow", "missing-founding-date-stays-uncertain", "evidence-gap-preserved", text), expected)

    def test_explicitly_exhaustive_operations_do_not_become_examples(self):
        for text, expected in [
            ("The only supported operations are read, write, and retry.", True),
            ("Supported operations are limited to read, write, and retry.", True),
            ("Supported operations include read, write, and retry.", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(passes_check("regression", PROTECTED_REGRESSION_ID, "exhaustive-scope-preserved", text), expected)

    def test_fresh_unchanged_artifact_rejects_editorial_explanations(self):
        checks = case_checks("workflow", "copy-ready-unchanged-sentence")
        sentence = "The rollback was uneventful, which is exactly how I like it."
        self.assertTrue(grade_response(sentence, checks)["passed"])
        for response in [
            sentence + "\n\nNo changes needed.",
            "Here is the revised sentence:\n\n" + sentence,
            sentence + " The original already reads well.",
        ]:
            with self.subTest(response=response):
                self.assertFalse(grade_response(response, checks)["passed"])

    def test_fresh_edit_accepts_copy_ready_prose_but_rejects_notes_and_changed_facts(self):
        checks = case_checks("workflow", "copy-ready-rotation-instructions")
        paragraph = "To rotate a token, select Rotate token in Settings. The old token remains valid for 15 minutes."
        for response in [paragraph, paragraph.replace(". The old", ".\nThe old"), paragraph + "\n\n"]:
            with self.subTest(valid_response=response):
                self.assertTrue(grade_response(response, checks)["passed"])
        for response in [
            paragraph + "\n\nChanges: shortened the opening.",
            paragraph + " Changes: shortened the opening.",
            paragraph + "\n\nThe original was wordy, so I simplified it.",
            "Here is the revised paragraph: " + paragraph,
            paragraph.replace("15 minutes", "16 minutes"),
            paragraph.replace("old token", "new token"),
        ]:
            with self.subTest(invalid_response=response):
                self.assertFalse(grade_response(response, checks)["passed"])
        self.assertTrue(passes_check(
            "workflow", "copy-ready-rotation-instructions", "no-editorial-commentary",
            "The token changes status after 15 minutes.",
        ))

    def test_recorded_editorial_failures_are_in_regression_and_artifacts_alone_pass(self):
        evidence = json.loads((EVAL_DIR / "evidence/editorial-notes.json").read_text())
        for recorded in evidence["cases"]:
            with self.subTest(case_id=recorded["regression_case_id"]):
                checks = case_checks("regression", recorded["regression_case_id"])
                grade = grade_response(recorded["response"], checks)
                self.assertFalse(grade["passed"])
                failures = {check["id"] for check in grade["checks"] if check["passed"] is False}
                self.assertTrue(set(recorded["original_failed_checks"]).issubset(failures))
                artifact = recorded["response"].split("\n\nNo change needed:", 1)[0].split("\n\nChanges:", 1)[0]
                self.assertTrue(grade_response(artifact, checks)["passed"])
                if recorded["regression_case_id"] == PROTECTED_REGRESSION_ID:
                    self.assertFalse(grade_response(artifact + "\n\nChanges: simplified the wording.", checks)["passed"])

    def test_regression_checks_reject_recorded_failure_and_accept_current_state(self):
        evidence = json.loads((EVAL_DIR / "evidence/readme-history.json").read_text())
        checks = case_checks("regression", REGRESSION_ID)
        grade = grade_response(evidence["response"], checks)
        self.assertFalse(grade["passed"])
        self.assertEqual(
            {check["id"] for check in grade["checks"] if check["passed"] is False},
            set(evidence["failed_checks"]),
        )
        current_state = "ResponseCache stores up to 200 entries and evicts the least-recently-used entry when full."
        self.assertTrue(grade_response(current_state, checks)["passed"])


if __name__ == "__main__":
    unittest.main()
