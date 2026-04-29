import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills" / "llm-optimized-rewrite" / "scripts" / "smell_test.py"
SHELL_SCRIPT = ROOT / "skills" / "llm-optimized-rewrite" / "scripts" / "smell_test.sh"
COUNT_SCRIPT = ROOT / "skills" / "llm-optimized-rewrite" / "scripts" / "count_tokens.py"


def run_smell_test(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def run_llm_optimal_check(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.llm_optimal_check", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def exact_token_metrics(text: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(COUNT_SCRIPT), "--json"],
        cwd=ROOT,
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class SmellTestCliTests(unittest.TestCase):
    def test_llm_token_count_api_cli_and_legacy_wrapper_preserve_metrics(self):
        from tools.llm_token_count import count_text, format_plain

        text = "hello <|endoftext|> world\n"
        api_metrics = count_text(text)
        self.assertEqual(set(api_metrics), {"tokens", "encoding", "source", "characters"})
        self.assertEqual(api_metrics["characters"], len(text))
        self.assertEqual(format_plain(api_metrics), f"tokens={api_metrics['tokens']} encoding={api_metrics['encoding']} source={api_metrics['source']} characters={len(text)}")

        module = subprocess.run(
            [sys.executable, "-m", "tools.llm_token_count", "--json"],
            cwd=ROOT,
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )
        legacy = subprocess.run(
            [sys.executable, str(COUNT_SCRIPT), "--json"],
            cwd=ROOT,
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(module.stdout), api_metrics)
        self.assertEqual(json.loads(legacy.stdout), api_metrics)

    def test_cli_emits_json_contract_with_body_only_token_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "command.md"
            body = "# Do work\n\n```bash\necho keep fenced content\n```\n"
            target.write_text(
                "---\n"
                "description: this frontmatter should not be counted even if verbose verbose verbose\n"
                "---\n"
                + body,
                encoding="utf-8",
            )

            completed = run_smell_test(target)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stderr, "")
            report = json.loads(completed.stdout)
            module_completed = run_llm_optimal_check(target)
            self.assertEqual(module_completed.returncode, 0, module_completed.stderr)
            self.assertEqual(json.loads(module_completed.stdout), report)
            from tools.llm_optimal_check import check_path
            self.assertEqual(check_path(target), report)
            self.assertEqual(set(report), {"status", "score", "metrics", "findings"})
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["score"], 100)
            self.assertEqual(report["findings"], [])
            self.assertEqual(report["metrics"]["tokens"], exact_token_metrics(body)["tokens"])
            self.assertEqual(report["metrics"]["characters"], len(body))
            self.assertTrue(report["metrics"]["frontmatter_excluded"])
            self.assertEqual(report["metrics"]["frontmatter_lines"], 3)
            self.assertIn("echo keep fenced content", report["metrics"]["analyzed_preview"])

    def test_token_cost_findings_have_stable_fields_and_deterministic_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "smelly.md"
            long_line = "It is important to note that this is very basically maybe just guidance " + "word " * 25
            long_paragraph = " ".join(["dense"] * 130)
            target.write_text(
                "# Repeat\n"
                "# Repeat\n\n"
                "- You should review the first item before continuing.\n"
                "- You should review the second item before continuing.\n\n"
                f"{long_line}\n\n"
                f"{long_paragraph}\n",
                encoding="utf-8",
            )

            completed = run_smell_test(target)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["score"], 60)
            by_rule = {finding["rule_id"]: finding for finding in report["findings"]}
            self.assertEqual(
                set(by_rule),
                {"TC001", "TC002", "TC003", "TC004", "TC005", "TC006"},
            )
            for finding in report["findings"]:
                self.assertEqual(
                    set(finding),
                    {"rule_id", "severity", "category", "location", "evidence", "message", "suggestion"},
                )
                self.assertEqual(finding["category"], "token-cost")
                self.assertIn("line", finding["location"])
                self.assertIsInstance(finding["suggestion"], str)
                self.assertNotIn("replacement", finding)
                self.assertNotIn("offset", finding)
                self.assertNotIn("patch", finding)

    def test_reliability_findings_are_skill_aware_and_heuristic(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_target = Path(tmp) / "demo" / "SKILL.md"
            skill_target.parent.mkdir()
            wall_text = "\n".join(
                ["Always preserve constraints and verify outputs before changing files in this workflow."] * 9
            )
            overlong_step = (
                "1. When appropriate, coordinate with users before starting and keep going through every possible\n"
                "   interpretation because the model should infer whether to ask, whether to edit, whether to stop,\n"
                "   whether to validate, whether to report, and whether to continue without a crisp gate."
            )
            skill_target.write_text(
                "---\nname: demo\ndescription: demo skill\n---\n"
                "# Workflow\n\n"
                f"{overlong_step}\n\n"
                f"{wall_text}\n\n"
                "Handle arguments, files, users, etc.\n",
                encoding="utf-8",
            )

            completed = run_smell_test(skill_target)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["metrics"]["document_kind"], "skill")
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["score"], 65)
            by_rule = {finding["rule_id"]: finding for finding in report["findings"]}
            self.assertEqual(set(by_rule), {"REL001", "REL002", "REL003", "REL004"})
            self.assertEqual(by_rule["REL001"]["category"], "reliability")
            self.assertEqual(by_rule["REL002"]["severity"], "major")
            self.assertEqual(by_rule["REL003"]["severity"], "major")
            self.assertEqual(by_rule["REL004"]["severity"], "experimental")
            self.assertIn("heuristic", by_rule["REL001"]["message"].lower())

            command_dir = Path(tmp) / "commands"
            command_dir.mkdir()
            command_target = command_dir / "demo.md"
            command_target.write_text("# Demo\n\nUse $ARGUMENTS exactly.\n", encoding="utf-8")
            command_report = json.loads(run_smell_test(command_target).stdout)
            self.assertEqual(command_report["metrics"]["document_kind"], "command")

    def test_skill_documentation_presents_smell_test_as_optional_aid(self):
        skill = (ROOT / "skills" / "llm-optimized-rewrite" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/smell_test.py", skill)
        self.assertIn("optional candidate-discovery aid", skill)
        self.assertIn("does not replace semantic verification", skill)
        self.assertIn("exact token counts", skill)
        self.assertIn("user confirmation", skill)

    def test_shell_wrapper_renders_friendly_summary_and_optional_raw_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "optimized.md"
            target.write_text("# Workflow\n\n1. Read the file.\n2. Report the result.\n", encoding="utf-8")

            completed = subprocess.run(
                [str(SHELL_SCRIPT), str(target)],
                cwd=ROOT,
                env={"NO_COLOR": "1", "SMELL_TEST_RAW_JSON": "1", "SMELL_TEST_VERBOSE": "1"},
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Running smell test", completed.stderr)
            self.assertIn("Raw smell_test.py diagnostics", completed.stderr)
            self.assertIn("command: python3", completed.stderr)
            self.assertIn("exit: 0", completed.stderr)
            self.assertIn("stderr: <empty>", completed.stderr)
            self.assertIn("Smell test passed", completed.stdout)
            self.assertIn("Metrics", completed.stdout)
            self.assertIn("Findings", completed.stdout)
            self.assertIn("Raw JSON", completed.stdout)
            raw_json = next(line for line in reversed(completed.stdout.splitlines()) if line.startswith("{"))
            report = json.loads(raw_json)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["findings"], [])

    def test_programmatic_e2e_contract_statuses_and_error_exits(self):
        """Programmatic JSON contract: {status, score, metrics, findings}; success exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            optimized = root / "optimized.md"
            optimized.write_text(
                "# Workflow\n\n"
                "1. Read the target file.\n"
                "2. Preserve required behavior.\n"
                "3. Report the validation command.\n",
                encoding="utf-8",
            )
            warn = root / "warn.md"
            warn.write_text(
                "# Workflow\n\n"
                "1. Validate inputs, read the file, compare the requested behavior, preserve explicit constraints,\n"
                "   check the JSON contract, run the command, inspect results, summarize the outcome clearly,\n"
                "   record the decision, and stop before introducing unrelated cleanup work.\n",
                encoding="utf-8",
            )
            fail = root / "fail.md"
            fail.write_text(
                "# Repeat\n# Repeat\n\n"
                "It is important to note that this is very basically maybe just guidance " + "word " * 25 + "\n\n"
                + " ".join(["dense"] * 130),
                encoding="utf-8",
            )

            reports = {}
            for name, target in {"pass": optimized, "warn": warn, "fail": fail}.items():
                completed = run_smell_test(target)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                reports[name] = json.loads(completed.stdout)
                self.assertEqual(set(reports[name]), {"status", "score", "metrics", "findings"})

            self.assertEqual(reports["pass"]["status"], "pass")
            self.assertEqual(reports["pass"]["findings"], [])
            self.assertEqual(reports["warn"]["status"], "warn")
            self.assertEqual([item["rule_id"] for item in reports["warn"]["findings"]], ["REL002"])
            self.assertEqual(reports["fail"]["status"], "fail")
            self.assertLessEqual(reports["fail"]["score"], 70)

        usage = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(usage.returncode, 0)
        self.assertEqual(usage.stdout, "")
        missing = subprocess.run(
            [sys.executable, str(SCRIPT), str(ROOT / "does-not-exist.md")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(missing.stdout, "")


if __name__ == "__main__":
    unittest.main()
