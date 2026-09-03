"""Offline setup.sh workflows with disposable source and install directories."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SETUP_SCRIPT = Path(__file__).resolve().parents[1] / "setup.sh"
PI_RESOURCES = {
    "APPEND_SYSTEM.md": "Repository policy\n",
    "commands/first.md": "First prompt\n",
    "commands/second.md": "Second prompt\n",
    "docs/guide.md": "Repository guide\n",
    "extensions/alpha/index.ts": "export default function () {}\n",
    "extensions/beta/index.js": "export default function () {}\n",
    "extensions/gamma/package.json": '{"pi": {"extensions": ["main.ts"]}}\n',
    "extensions/gamma/main.ts": "export default function () {}\n",
    "extensions/AGENTS.md": "Not an extension\n",
    "extensions/ineligible/README.md": "Not an extension\n",
    "future-resource/notes.md": "Not implicitly installed\n",
}


def tree(path):
    """Snapshot files, directories, and link targets without following links."""
    result = {}

    def visit(entry, relative):
        if entry.is_symlink():
            result[relative] = ("link", os.readlink(entry))
        elif entry.is_dir():
            result[relative] = ("directory",)
            for child in entry.iterdir():
                visit(child, str(Path(relative) / child.name))
        elif entry.exists():
            result[relative] = ("file", entry.read_bytes())

    visit(path, ".")
    return result


def linked_tree(links):
    """Expected install tree containing exactly these links and their parents."""
    result = {}
    for destination, source in links.items():
        path = Path(destination)
        result[str(path)] = ("link", str(source))
        for parent in path.parents:
            result[str(parent)] = ("directory",)
    return result


class SetupFixture:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="setup-test-")
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repository with spaces"
        self.repo.mkdir()
        shutil.copy2(SETUP_SCRIPT, self.repo / "setup.sh")
        self.home = self.root / "home"
        self.home.mkdir()
        self.pi = self.root / "pi agent"
        self.kilo = self.root / "kilo config"
        self.global_skills = self.root / "global skills"
        self.env = os.environ.copy()
        self.env.pop("BASH_ENV", None)
        self.env.pop("ENV", None)
        self.env.update(
            HOME=str(self.home),
            PI_AGENT_DIR=str(self.pi),
            KILO_CONFIG_DIR=str(self.kilo),
            GLOBAL_SKILLS_DIR=str(self.global_skills),
            LC_ALL="C",
        )
        return self

    def __exit__(self, *args):
        self.temporary.cleanup()

    def write(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def add_pi_resources(self):
        for name, content in PI_RESOURCES.items():
            self.write(self.repo / "harness/pi" / name, content)

    def run(self, *answers, args=(), expected_status=0):
        source_before = tree(self.repo)
        result = subprocess.run(
            ["/bin/bash", str(self.repo / "setup.sh"), *args],
            input="\n".join(answers) + ("\n" if answers else ""),
            text=True,
            capture_output=True,
            cwd=self.repo,
            env=self.env,
            timeout=10,
        )
        if result.returncode != expected_status:
            raise AssertionError(
                f"setup.sh exited {result.returncode}, expected {expected_status}\n"
                f"{result.stdout}\n{result.stderr}"
            )
        if tree(self.repo) != source_before:
            raise AssertionError("setup.sh modified its source checkout")
        return result

    def targets(self):
        return {
            name: tree(path)
            for name, path in (
                ("home", self.home),
                ("pi", self.pi),
                ("kilo", self.kilo),
                ("global", self.global_skills),
            )
        }


class SetupTests(unittest.TestCase):
    def assert_only_pi_links(self, fixture, links):
        self.assertEqual(tree(fixture.pi), linked_tree(links))
        self.assertEqual(tree(fixture.home), {".": ("directory",)})
        self.assertEqual(tree(fixture.kilo), {})
        self.assertEqual(tree(fixture.global_skills), {})

    def test_extension_only_preserves_policy_prompts_docs_and_existing_installs(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "prompts/second.md", "User prompt\n")
            fixture.write(fixture.pi / "settings.json", '{"extensions": ["custom"]}\n')
            (fixture.pi / "docs").symlink_to(fixture.repo / "harness/pi/docs")
            (fixture.pi / "extensions").mkdir()
            (fixture.pi / "extensions/existing").symlink_to(fixture.root / "missing-extension")
            before = fixture.targets()

            fixture.run("3", "extensions", "alpha", "y")

            expected = before["pi"].copy()
            expected["extensions/alpha"] = (
                "link", str(fixture.repo / "harness/pi/extensions/alpha")
            )
            self.assertEqual(fixture.targets(), {**before, "pi": expected})

    def test_policy_only_links_no_other_component(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.run("3", "APPEND_SYSTEM.md", "y")
            self.assert_only_pi_links(fixture, {
                "APPEND_SYSTEM.md": fixture.repo / "harness/pi/APPEND_SYSTEM.md",
            })

    def test_commands_select_a_subset_by_number_and_deduplicate_names(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.run("3", "commands", "2,second.md,2", "y")
            self.assert_only_pi_links(fixture, {
                "prompts/second.md": fixture.repo / "harness/pi/commands/second.md",
            })

    def test_mixed_components_survive_nested_item_pickers(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "harness/pi/skills/one/SKILL.md", "One\n")
            fixture.write(fixture.repo / "harness/pi/skills/two/SKILL.md", "Two\n")
            result = fixture.run(
                "3", "extensions APPEND_SYSTEM.md commands skills docs",
                "beta", "second.md", "two", "y",
            )
            links = {
                "extensions/beta": fixture.repo / "harness/pi/extensions/beta",
                "APPEND_SYSTEM.md": fixture.repo / "harness/pi/APPEND_SYSTEM.md",
                "prompts/second.md": fixture.repo / "harness/pi/commands/second.md",
                "skills/two": fixture.repo / "harness/pi/skills/two",
                "docs": fixture.repo / "harness/pi/docs",
            }
            self.assert_only_pi_links(fixture, links)
            plan = [
                line for line in result.stdout.splitlines()
                if line.startswith(f"  - {fixture.repo}/harness/pi/")
            ]
            self.assertEqual(plan, [
                f"  - {source} -> {fixture.pi / destination}"
                for destination, source in links.items()
            ])
            for line in plan:
                self.assertLess(result.stdout.index(line), result.stdout.index("Linked:"))

    def test_docs_is_one_atomic_directory_link_and_reruns_are_idempotent(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.run("3", "docs", "y")
            self.assert_only_pi_links(fixture, {"docs": fixture.repo / "harness/pi/docs"})
            before = fixture.targets()
            fixture.run("3", "docs", "y")
            self.assertEqual(fixture.targets(), before)

    def test_other_root_file_is_independently_selectable(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "harness/pi/README.md", "Resource notes\n")
            fixture.run("3", "README.md", "y")
            self.assert_only_pi_links(fixture, {
                "README.md": fixture.repo / "harness/pi/README.md",
            })

    def test_explicit_all_at_each_level_installs_only_eligible_items(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "harness/pi/skills/one/SKILL.md", "One\n")
            fixture.write(fixture.repo / "harness/pi/skills/two/SKILL.md", "Two\n")
            fixture.run("3", "all", "all", "all", "all", "y")
            source = fixture.repo / "harness/pi"
            self.assert_only_pi_links(fixture, {
                "APPEND_SYSTEM.md": source / "APPEND_SYSTEM.md",
                "prompts/first.md": source / "commands/first.md",
                "prompts/second.md": source / "commands/second.md",
                "docs": source / "docs",
                "extensions/alpha": source / "extensions/alpha",
                "extensions/beta": source / "extensions/beta",
                "extensions/gamma": source / "extensions/gamma",
                "future-resource": source / "future-resource",
                "skills/one": source / "skills/one",
                "skills/two": source / "skills/two",
            })

    def test_cancel_eof_or_decline_never_writes_any_pi_resource(self):
        workflows = (
            ("3",),
            ("3", "q"),
            ("3", "", "q"),
            ("3", "APPEND_SYSTEM.md commands", "q"),
            ("3", "APPEND_SYSTEM.md commands", "", "q"),
            ("3", "APPEND_SYSTEM.md extensions"),
            ("3", "APPEND_SYSTEM.md commands extensions", "first.md", "q"),
            ("3", "APPEND_SYSTEM.md skills", "q"),
            ("3", "APPEND_SYSTEM.md commands", "first.md", "n"),
            ("3", "APPEND_SYSTEM.md", ""),
            ("3", "APPEND_SYSTEM.md"),
        )
        for answers in workflows:
            with self.subTest(answers=answers), SetupFixture() as fixture:
                fixture.add_pi_resources()
                fixture.write(fixture.repo / "harness/pi/skills/one/SKILL.md", "One\n")
                before = fixture.targets()
                fixture.run(*answers)
                self.assertEqual(fixture.targets(), before)

    def test_declining_plan_preserves_existing_conflicts_without_backup(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "prompts/first.md", "User prompt\n")
            before = fixture.targets()
            fixture.run("3", "APPEND_SYSTEM.md commands", "first.md", "n")
            self.assertEqual(fixture.targets(), before)

    def test_conflict_refusal_preserves_selected_and_unselected_files(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "prompts/first.md", "User prompt\n")
            before = fixture.targets()
            result = fixture.run("3", "APPEND_SYSTEM.md", "y", "n", expected_status=1)
            self.assertEqual(fixture.targets(), before)
            self.assertIn(str(fixture.pi / "APPEND_SYSTEM.md"), result.stdout)

    def test_confirmed_conflict_backs_up_only_the_selected_resource(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "prompts/first.md", "User prompt\n")
            before = fixture.targets()
            result = fixture.run("3", "APPEND_SYSTEM.md", "y", "y")
            backups = list(fixture.pi.glob("APPEND_SYSTEM.md.backup.*"))
            self.assertEqual(len(backups), 1)
            self.assertIn(str(backups[0]), result.stdout)
            expected = before["pi"].copy()
            expected[backups[0].name] = expected["APPEND_SYSTEM.md"]
            expected["APPEND_SYSTEM.md"] = (
                "link", str(fixture.repo / "harness/pi/APPEND_SYSTEM.md")
            )
            self.assertEqual(fixture.targets(), {**before, "pi": expected})

    def test_existing_docs_directory_is_backed_up_as_a_whole(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "docs/local.md", "User notes\n")
            original_docs = tree(fixture.pi / "docs")
            fixture.run("3", "docs", "y", "y")
            backups = list(fixture.pi.glob("docs.backup.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(tree(backups[0]), original_docs)
            expected = linked_tree({"docs": fixture.repo / "harness/pi/docs"})
            expected[backups[0].name] = ("directory",)
            expected[f"{backups[0].name}/local.md"] = ("file", b"User notes\n")
            self.assertEqual(tree(fixture.pi), expected)

    def test_conflicting_symlink_requires_separate_confirmation(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            original = fixture.write(fixture.root / "user-policy.md", "User policy\n")
            fixture.pi.mkdir()
            (fixture.pi / "APPEND_SYSTEM.md").symlink_to(original)
            before = fixture.targets()
            result = fixture.run("3", "APPEND_SYSTEM.md", "y", "n", expected_status=1)
            self.assertEqual(fixture.targets(), before)
            self.assertIn(str(original), result.stdout)
            fixture.run("3", "APPEND_SYSTEM.md", "y", "y")
            self.assert_only_pi_links(fixture, {
                "APPEND_SYSTEM.md": fixture.repo / "harness/pi/APPEND_SYSTEM.md",
            })
            self.assertEqual(original.read_text(), "User policy\n")

    def test_missing_optional_directories_do_not_block_root_selection(self):
        with SetupFixture() as fixture:
            fixture.write(fixture.repo / "harness/pi/APPEND_SYSTEM.md", "Policy\n")
            fixture.run("3", "APPEND_SYSTEM.md", "y")
            self.assert_only_pi_links(fixture, {
                "APPEND_SYSTEM.md": fixture.repo / "harness/pi/APPEND_SYSTEM.md",
            })

    def test_empty_components_do_not_write_and_do_not_block_other_selections(self):
        for include_policy in (False, True):
            with self.subTest(include_policy=include_policy), SetupFixture() as fixture:
                fixture.write(fixture.repo / "harness/pi/extensions/AGENTS.md", "Instructions\n")
                fixture.write(fixture.repo / "harness/pi/extensions/ineligible/README.md", "Notes\n")
                (fixture.repo / "harness/pi/commands").mkdir()
                (fixture.repo / "harness/pi/skills").mkdir()
                selection = "extensions commands skills"
                if include_policy:
                    fixture.write(fixture.repo / "harness/pi/APPEND_SYSTEM.md", "Policy\n")
                    fixture.run("3", selection + " APPEND_SYSTEM.md", "y")
                    self.assert_only_pi_links(fixture, {
                        "APPEND_SYSTEM.md": fixture.repo / "harness/pi/APPEND_SYSTEM.md",
                    })
                else:
                    before = fixture.targets()
                    fixture.run("3", selection)
                    self.assertEqual(fixture.targets(), before)

    def test_missing_or_empty_pi_tree_is_a_no_op(self):
        for present in (False, True):
            with self.subTest(present=present), SetupFixture() as fixture:
                if present:
                    (fixture.repo / "harness/pi").mkdir(parents=True)
                before = fixture.targets()
                fixture.run("3")
                self.assertEqual(fixture.targets(), before)

    def test_legacy_kilo_inputs_and_resources_cannot_install(self):
        workflows = (("3", "kilo", "q"), ("3", "both", "q"),
                     ("3", "APPEND_SYSTEM.md commands", "q", "y"),
                     ("2", "kilo", "q"), ("2", "pi-kilo", "q"),
                     ("2", "2", "q"), ("2", "4", "q"), ("2", "5", "q"))
        for answers in workflows:
            with self.subTest(answers=answers), SetupFixture() as fixture:
                fixture.add_pi_resources()
                fixture.write(fixture.repo / "skills/one/SKILL.md", "One\n")
                fixture.write(fixture.repo / "harness/kilo/settings.json", "{}\n")
                fixture.write(fixture.kilo / "settings.json", "User settings\n")
                before = fixture.targets()
                fixture.run(*answers)
                self.assertEqual(fixture.targets(), before)

    def test_legacy_resources_are_ignored_by_pi_installation(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "harness/kilo/settings.json", "{}\n")
            fixture.write(fixture.kilo / "settings.json", "User settings\n")
            legacy_before = tree(fixture.kilo)
            fixture.run("3", "all", "all", "all", "y")
            self.assertEqual(tree(fixture.kilo), legacy_before)
            self.assertNotIn("settings.json", tree(fixture.pi))
            self.assertTrue((fixture.pi / "APPEND_SYSTEM.md").is_symlink())

    def test_shared_skills_still_link_only_selected_items_to_all_targets(self):
        with SetupFixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "skills/one/SKILL.md", "One\n")
            fixture.write(fixture.repo / "skills/two/SKILL.md", "Two\n")
            fixture.write(fixture.repo / "skills/ineligible/README.md", "Notes\n")
            fixture.run("2", "all", "two", "y")
            source = fixture.repo / "skills/two"
            self.assertEqual(tree(fixture.pi), linked_tree({"skills/two": source}))
            self.assertEqual(tree(fixture.kilo), {})
            self.assertEqual(tree(fixture.global_skills), linked_tree({"two": source}))
            self.assertEqual(tree(fixture.home), {".": ("directory",)})

    def test_skills_link_only_to_the_explicit_single_destination(self):
        for choice, destination in (("1", "pi"), ("3", "global")):
            with self.subTest(choice=choice), SetupFixture() as fixture:
                source = fixture.repo / "skills/one"
                fixture.write(source / "SKILL.md", "One\n")
                before = fixture.targets()
                fixture.run("2", choice, "one", "y")
                links = {"skills/one" if destination == "pi" else "one": source}
                self.assertEqual(fixture.targets(), {**before, destination: linked_tree(links)})

    def test_missing_or_empty_tool_and_skill_trees_are_no_ops(self):
        for category, answers in (("tools", ("1",)), ("skills", ("2", "pi"))):
            for present in (False, True):
                with self.subTest(category=category, present=present), SetupFixture() as fixture:
                    if present:
                        (fixture.repo / category).mkdir()
                    before = fixture.targets()
                    fixture.run(*answers)
                    self.assertEqual(fixture.targets(), before)

    def test_tools_still_install_only_selected_packages_with_cargo(self):
        with SetupFixture() as fixture:
            fixture.write(fixture.repo / "tools/one/Cargo.toml", "[package]\nname='one'\n")
            fixture.write(fixture.repo / "tools/two/Cargo.toml", "[package]\nname='two'\n")
            fake_cargo = fixture.write(
                fixture.root / "bin/cargo",
                '#!/bin/bash\nprintf "%s\\n" "$@" >> "$CARGO_CALLS"\n',
            )
            fake_cargo.chmod(0o755)
            calls = fixture.root / "cargo-calls"
            fixture.env["PATH"] = f"{fake_cargo.parent}:{fixture.env['PATH']}"
            fixture.env["CARGO_CALLS"] = str(calls)
            before = fixture.targets()
            fixture.run("1", "two", "y")
            self.assertEqual(calls.read_text().splitlines(), [
                "install", "--path", str(fixture.repo / "tools/two"), "--force",
            ])
            self.assertEqual(fixture.targets(), before)

    def test_cli_help_and_unknown_argument_never_write(self):
        with SetupFixture() as fixture:
            before = fixture.targets()
            help_result = fixture.run(args=("--help",))
            self.assertNotIn("Kilo", help_result.stdout)
            fixture.run(args=("--kilo",), expected_status=2)
            fixture.run(args=("--unknown",), expected_status=2)
            self.assertEqual(fixture.targets(), before)


if __name__ == "__main__":
    unittest.main()
