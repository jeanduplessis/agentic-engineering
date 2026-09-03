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
            (root / "harness" / "pi" / "commands").mkdir(parents=True)
            yield root

    def test_valid_command_emits_compact_json_with_resolved_direct_file(self):
        with self.make_repo() as root:
            command = root / "harness" / "pi" / "commands" / "code-review.md"
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
            self.assertEqual(result["path"], "harness/pi/commands/code-review.md")
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
            (root / "harness" / "pi" / "commands" / "model.md").write_text("---\ndescription: model\n---\n")
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
            self.assertIn("harness/pi/commands/missing-command.md", result["errors"][0]["message"])

    def test_python_module_cli_resolves_one_direct_command_file(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "spec-audit.md").write_text("---\ndescription: Audit spec\n---\n")

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
            self.assertEqual(result["path"], "harness/pi/commands/spec-audit.md")

    def test_requires_scalar_frontmatter_with_non_empty_description(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "no-description.md").write_text("Body only\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["no-description", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["valid"])
            self.assertEqual(result["status"], "invalid")
            self.assertEqual(result["path"], "harness/pi/commands/no-description.md")
            self.assertTrue(any(error["code"] == "missing_frontmatter" for error in result["errors"]))
            self.assertTrue(any("description" in error["message"] for error in result["errors"]))

    def test_recognized_shared_union_frontmatter_fields_pass_static_validation(self):
        with self.make_repo() as root:
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("---\nname: review-skill\ndescription: Review skill\n---\n")
            (root / "skills" / "test-skill").mkdir(parents=True)
            (root / "skills" / "test-skill" / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test skill\n---\n")
            (root / "harness" / "pi" / "commands" / "routed-command.md").write_text(
                "---\n"
                "description: Routed command\n"
                "argument-hint: \"<target>\"\n"
                "model: openrouter/gpt-5\n"
                "thinking: high\n"
                 "skill: review-skill\n"
                 "skills:\n"
                 "  - test-skill\n"
                 "restore: false\n"
                 "agent: build\n"
                 "subtask: true\n"
                 "---\n"
                 "## Required skills\n\n- `review-skill`\n- `test-skill`\n\nReview $ARGUMENTS and $1\n"

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
            (root / "harness" / "pi" / "commands" / "bad-field.md").write_text("---\ndescription: Bad\nunsupported-field: value\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["bad-field", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "unknown_frontmatter")
            self.assertIn("unsupported-field", result["errors"][0]["message"])

    def test_scalar_skills_field_fails_validation(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "scalar-skills.md").write_text("---\ndescription: Bad\nskills: review-skill\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["scalar-skills", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "non_scalar_frontmatter" and "skills" in error["message"] for error in result["errors"]))

    def test_skills_list_items_must_resolve_to_readable_local_skills(self):
        with self.make_repo() as root:
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("---\nname: review-skill\ndescription: Review skill\n---\n")
            (root / "harness" / "pi" / "commands" / "multi-skill.md").write_text(
                 "---\ndescription: Multi\nskills:\n  - review-skill\n  - missing-skill\n---\n## Required skills\n\n- `review-skill`\n- `missing-skill`\n\nBody\n"

            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["multi-skill", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "missing_skill")
            self.assertIn("missing-skill", result["errors"][0]["message"])

    def test_nested_or_list_frontmatter_fails_scalar_validation(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "nested-field.md").write_text("---\ndescription:\n  text: Nested\n---\nBody\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["nested-field", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "non_scalar_frontmatter" for error in result["errors"]))

    def test_invalid_thinking_restore_subtask_opencode_interpolation_and_placeholders_fail(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "bad-body.md").write_text(
                "---\ndescription: Bad body\nthinking: deepest\nrestore: maybe\nsubtask: maybe\n---\nRun !`npm test` with @src/app.ts, $@, and ${@:2}\n"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["bad-body", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(
                {error["code"] for error in result["errors"]},
                {"invalid_thinking", "invalid_restore", "invalid_subtask", "unsupported_body_syntax", "unsupported_placeholder"},
            )

    def test_duplicate_frontmatter_and_skill_declarations_fail(self):
        with self.make_repo() as root:
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("# Review\n")
            (root / "harness" / "pi" / "commands" / "duplicates.md").write_text(
                "---\n"
                "description: First\n"
                "description: Second\n"
                "skill: review-skill\n"
                "skills:\n"
                "  - review-skill\n"
                "---\n"
                "## Required skills\n\n- `review-skill`\n"
            )
            stdout = io.StringIO()

            code = main(["duplicates", "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "duplicate_frontmatter" for error in result["errors"]))
            self.assertTrue(any(error["code"] == "duplicate_skill" for error in result["errors"]))

    def test_required_skills_section_must_preserve_declared_order(self):
        with self.make_repo() as root:
            for name in ("first-skill", "second-skill"):
                (root / "skills" / name).mkdir(parents=True)
                (root / "skills" / name / "SKILL.md").write_text(f"# {name}\n")
            (root / "harness" / "pi" / "commands" / "wrong-order.md").write_text(
                "---\ndescription: Wrong order\nskills:\n  - first-skill\n  - second-skill\n---\n"
                "## Required skills\n\n- `second-skill`\n- `first-skill`\n"
            )
            stdout = io.StringIO()

            code = main(["wrong-order", "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "missing_required_skills_section" for error in result["errors"]))

    def test_declared_skill_name_must_be_lowercase_kebab_case(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "bad-skill-name.md").write_text(
                "---\ndescription: Bad skill name\nskill: Bad_Skill\n---\n## Required skills\n\n- `Bad_Skill`\n"
            )
            stdout = io.StringIO()

            code = main(["bad-skill-name", "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertTrue(any(error["code"] == "invalid_skill" for error in result["errors"]))

    def test_package_suffix_is_not_treated_as_opencode_file_interpolation(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "package-suffix.md").write_text(
                "---\ndescription: Package suffix\n---\nRun `npx -y react-doctor@latest . --verbose`.\n"
            )
            stdout = io.StringIO()

            code = main(["package-suffix", "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())

            self.assertEqual(code, 0)
            self.assertTrue(json.loads(stdout.getvalue())["valid"])

    def test_bare_opencode_file_interpolation_is_rejected(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "bare-file.md").write_text("---\ndescription: Bare file\n---\nRead @README.md\n")
            stdout = io.StringIO()

            code = main(["bare-file", "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())

            self.assertEqual(code, 1)
            self.assertTrue(any(error["code"] == "unsupported_body_syntax" for error in json.loads(stdout.getvalue())["errors"]))

    def test_skill_declaration_requires_matching_explicit_required_skills_section(self):
        with self.make_repo() as root:
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("# Review\n")
            (root / "harness" / "pi" / "commands" / "missing-section.md").write_text(
                "---\ndescription: Needs skill\nskill: review-skill\n---\nBody\n"
            )
            (root / "harness" / "pi" / "commands" / "mismatched-section.md").write_text(
                "---\ndescription: Needs skill\nskill: review-skill\n---\n## Required skills\n\n- `other-skill`\n"
            )

            for command_name in ("missing-section", "mismatched-section"):
                with self.subTest(command_name=command_name):
                    stdout = io.StringIO()
                    code = main([command_name, "--repo-root", str(root), "--json"], stdout=stdout, stderr=io.StringIO())
                    result = json.loads(stdout.getvalue())
                    self.assertEqual(code, 1)
                    self.assertTrue(any(error["code"] == "missing_required_skills_section" for error in result["errors"]))

    def test_declared_skill_must_resolve_to_readable_local_skill(self):
        with self.make_repo() as root:
            (root / "harness" / "pi" / "commands" / "missing-skill.md").write_text(
                "---\ndescription: Needs skill\nskill: missing-skill\n---\n## Required skills\n\n- `missing-skill`\n"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main(["missing-skill", "--repo-root", str(root), "--json"], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "missing_skill")
            self.assertIn("missing-skill", result["errors"][0]["message"])


class CanonicalCommandInventoryTests(unittest.TestCase):
    EXPECTED_COMMANDS = sorted(
        {
            "code-review",
            "epic-orchestrate",
            "flesh-out",
            "idea-challenger",
            "optimize-for-llm",
            "pr-analyze",
            "pr-audit",
            "pr-create-update",
            "pr-review-analyze",
            "session-retro",
            "skill-validate",
            "spec-audit",
            "spec-gen",
            "spec-reverse-gen",
            "to-epic",
            "to-issues",
            "wat",
        }
    )

    def test_every_pi_command_passes_validation(self):
        repo_root = Path(__file__).resolve().parents[4]
        commands_dir = repo_root / "harness" / "pi" / "commands"
        command_names = sorted(path.stem for path in commands_dir.glob("*.md"))

        self.assertEqual(command_names, self.EXPECTED_COMMANDS)
        results = {}
        for command_name in command_names:
            stdout = io.StringIO()
            code = main([command_name, "--repo-root", str(repo_root), "--json"], stdout=stdout, stderr=io.StringIO())
            results[command_name] = {"code": code, "result": json.loads(stdout.getvalue())}

        self.assertTrue(all(entry["code"] == 0 for entry in results.values()), results)
        self.assertTrue(all(entry["result"]["valid"] is True for entry in results.values()), results)
        self.assertTrue(all(entry["result"]["path"] == f"harness/pi/commands/{name}.md" for name, entry in results.items()), results)

    def test_repo_tracks_one_pi_command_tree_with_discovery_metadata(self):
        repo_root = Path(__file__).resolve().parents[4]
        package = json.loads((repo_root / "package.json").read_text())

        self.assertEqual(package["pi"]["prompts"], ["harness/pi/commands/*.md"])
        self.assertFalse((repo_root / "commands").exists(), "Pi commands must remain under harness/pi/commands")
        for adapter_tree in (
            repo_root / ".pi" / "prompts",
            repo_root / ".opencode" / "commands",
            repo_root / ".kilo" / "command",
            repo_root / ".kilo" / "commands",
        ):
            self.assertFalse(adapter_tree.exists(), f"Generated or copied command tree must not be tracked: {adapter_tree}")


if __name__ == "__main__":
    unittest.main()
