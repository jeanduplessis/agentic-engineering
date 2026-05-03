import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.command_valid import main


class CommandValidTests(unittest.TestCase):
    @contextlib.contextmanager
    def make_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "commands").mkdir()
            yield root

    def test_valid_command_emits_compact_json_with_resolved_direct_file(self):
        with self.make_repo() as root:
            command = root / "commands" / "code-review.md"
            command.write_text("---\ndescription: Review code\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["code-review", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            output = stdout.getvalue()
            self.assertTrue(output.startswith("{"))
            self.assertNotIn("\n  ", output)
            result = json.loads(output)
            self.assertTrue(result["valid"])
            self.assertEqual(result["command"], "code-review")
            self.assertEqual(result["path"], "commands/code-review.md")
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["errors"], [])

    def test_non_kebab_command_name_fails_with_friendly_output_and_invalid_exit(self):
        with self.make_repo() as root:
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["Bad_Name", "--repo-root", str(root)], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            self.assertEqual(stderr.getvalue(), "")
            output = stdout.getvalue()
            self.assertIn("FAIL command_valid: invalid", output)
            self.assertIn("lowercase kebab-case", output)
            self.assertIn("/Bad_Name", output)

    def test_missing_command_name_is_usage_error_with_clear_friendly_output(self):
        with self.make_repo() as root:
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["--repo-root", str(root)], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 2)
            self.assertEqual(stderr.getvalue(), "")
            output = stdout.getvalue()
            self.assertIn("FAIL command_valid: usage_error", output)
            self.assertIn("Command name is required", output)

    def test_reserved_command_name_fails_before_file_resolution(self):
        with self.make_repo() as root:
            (root / "commands" / "model.md").write_text("---\ndescription: model\n---\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["model", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            self.assertEqual(stderr.getvalue(), "")
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["valid"])
            self.assertEqual(result["status"], "invalid")
            self.assertEqual(result["errors"][0]["code"], "reserved_name")
            self.assertIn("reserved", result["errors"][0]["message"])
            self.assertIsNone(result["path"])

    def test_unresolved_command_name_is_resolution_error(self):
        with self.make_repo() as root:
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["missing-command", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 2)
            self.assertEqual(stderr.getvalue(), "")
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["valid"])
            self.assertEqual(result["status"], "resolution_error")
            self.assertEqual(result["errors"][0]["code"], "not_found")
            self.assertIn("commands/missing-command.md", result["errors"][0]["message"])

    def test_python_module_cli_resolves_one_direct_command_file(self):
        with self.make_repo() as root:
            (root / "commands" / "spec-audit.md").write_text("---\ndescription: Audit spec\n---\n")

            completed = subprocess.run(
                [sys.executable, "-m", "tools.command_valid", "spec-audit", "--repo-root", str(root), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stderr, "")
            result = json.loads(completed.stdout)
            self.assertEqual(result["command"], "spec-audit")
            self.assertEqual(result["path"], "commands/spec-audit.md")

    def test_requires_scalar_frontmatter_with_non_empty_description(self):
        with self.make_repo() as root:
            (root / "commands" / "no-description.md").write_text("Body only\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["no-description", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["valid"])
            self.assertEqual(result["status"], "invalid")
            self.assertEqual(result["path"], "commands/no-description.md")
            self.assertTrue(any(error["code"] == "missing_frontmatter" for error in result["errors"]))
            self.assertTrue(any("description" in error["message"] for error in result["errors"]))

    def test_recognized_routing_frontmatter_fields_pass_static_validation(self):
        with self.make_repo() as root:
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("---\nname: review-skill\ndescription: Review skill\n---\n")
            (root / "commands" / "routed-command.md").write_text(
                "---\n"
                "description: Routed command\n"
                "argument-hint: \"<target>\"\n"
                "model: openrouter/gpt-5\n"
                "thinking: high\n"
                "skill: review-skill\n"
                "restore: false\n"
                "---\n"
                "Review $ARGUMENTS\n"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["routed-command", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertEqual(result["errors"], [])

    def test_unknown_frontmatter_field_fails_strict_validation(self):
        with self.make_repo() as root:
            (root / "commands" / "bad-field.md").write_text("---\ndescription: Bad\nagent: build\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["bad-field", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "unknown_frontmatter")
            self.assertIn("agent", result["errors"][0]["message"])

    def test_nested_or_list_frontmatter_fails_scalar_validation(self):
        with self.make_repo() as root:
            (root / "commands" / "nested-field.md").write_text("---\ndescription:\n  text: Nested\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["nested-field", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "non_scalar_frontmatter" for error in result["errors"]))

    def test_invalid_thinking_restore_body_syntax_and_placeholder_fail(self):
        with self.make_repo() as root:
            (root / "commands" / "bad-body.md").write_text(
                "---\ndescription: Bad body\nthinking: deepest\nrestore: maybe\n---\nRun !`npm test` with ${@:2}\n"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["bad-body", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(
                {error["code"] for error in result["errors"]},
                {"invalid_thinking", "invalid_restore", "unsupported_body_syntax", "unsupported_placeholder"},
            )

    def test_declared_skill_must_resolve_to_readable_local_skill(self):
        with self.make_repo() as root:
            (root / "commands" / "missing-skill.md").write_text("---\ndescription: Needs skill\nskill: missing-skill\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["missing-skill", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "missing_skill")
            self.assertIn("missing-skill", result["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
