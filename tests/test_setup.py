"""Offline setup.sh/ae workflows with disposable source and install directories."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO / "setup.sh"
AE_MANIFEST = REPO / "tools/ae/Cargo.toml"
AE_BIN = REPO / "tools/ae/target/debug/ae"
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
    "future-resource/notes.md": "Whole-directory resource\n",
}
T3_SETTINGS = {
    "providerInstances": {
        "claudeAgent": {"driver": "claudeAgent", "displayName": "Claude Work", "config": {}},
        "claudeAgent_claude_personal": {
            "driver": "claudeAgent",
            "displayName": "Claude Personal",
            "enabled": True,
            "config": {"homePath": "~/.claude_personal"},
        },
        "grok": {"driver": "grok", "displayName": "Grok", "enabled": True},
    }
}
HARNESS_HOMES = {
    "claude-work": ".claude",
    "claude-personal": ".claude_personal",
    "codex": ".codex",
    "grok": ".grok",
    "kilo": ".config/kilo",
}


def setUpModule():
    if shutil.which("cargo") is None:
        raise RuntimeError("these tests build tools/ae and need cargo on PATH")
    subprocess.run(
        ["cargo", "build", "--locked", "--quiet", "--manifest-path", str(AE_MANIFEST)],
        check=True,
        timeout=900,
    )


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


def links(path):
    """Every symlink under `path`, as {relative path: target}."""
    return {k: v[1] for k, v in tree(path).items() if v[0] == "link"}


class Fixture:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="setup-test-")
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repository with spaces"
        self.repo.mkdir()
        shutil.copy2(SETUP_SCRIPT, self.repo / "setup.sh")
        self.home = self.root / "home"
        self.home.mkdir()
        self.pi = self.root / "pi agent"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "PI_AGENT_DIR": str(self.pi),
            "AE_BIN": str(AE_BIN),
            "AE_NO_PROBE": "1",
            "LC_ALL": "C",
            "TMPDIR": str(self.root / "tmp"),
        }
        (self.root / "tmp").mkdir()
        return self

    def __exit__(self, *args):
        self.temporary.cleanup()

    def write(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def skill(self, name, description="A test skill."):
        return self.write(
            self.repo / "skills" / name / "SKILL.md",
            f"---\nname: {name}\ndescription: {description}\n---\nBody\n",
        ).parent

    def t3(self):
        self.write(self.home / ".t3/userdata/settings.json", json.dumps(T3_SETTINGS))

    def detect(self, *ids):
        """Create harness homes so ae detects them."""
        for harness in ids:
            if harness == "pi":
                self.pi.mkdir(parents=True, exist_ok=True)
            else:
                (self.home / HARNESS_HOMES[harness]).mkdir(parents=True, exist_ok=True)

    def add_pi_resources(self):
        for name, content in PI_RESOURCES.items():
            self.write(self.repo / "harness/pi" / name, content)

    def add_subagents(self):
        shutil.copytree(REPO / "harness/pi/subagents", self.repo / "harness/pi/subagents")

    def run(self, *answers, args=(), expected_status=0, env=None):
        source_before = tree(self.repo)
        result = subprocess.run(
            ["/bin/bash", str(self.repo / "setup.sh"), *args],
            input="\n".join(answers) + ("\n" if answers else ""),
            text=True,
            capture_output=True,
            cwd=self.repo,
            env={**self.env, **(env or {})},
            timeout=60,
        )
        if result.returncode != expected_status:
            raise AssertionError(
                f"setup.sh {' '.join(args)} exited {result.returncode}, expected {expected_status}\n"
                f"{result.stdout}\n{result.stderr}"
            )
        if tree(self.repo) != source_before:
            raise AssertionError("setup.sh modified its source checkout")
        return result

    def status(self):
        return json.loads(self.run(args=("status", "--json")).stdout)

    def targets(self):
        return {"home": tree(self.home), "pi": tree(self.pi)}


# test_subagents_install.py shares this fixture.
SetupFixture = Fixture


class CommandLineTests(unittest.TestCase):
    def test_help_unknown_arguments_and_bare_runs_never_write(self):
        with Fixture() as fixture:
            fixture.skill("one")
            fixture.add_pi_resources()
            before = fixture.targets()
            help_text = fixture.run(args=("--help",)).stdout
            self.assertIn("ae add -s council-review -H all", help_text)
            fixture.run(args=("--kilo",), expected_status=2)
            fixture.run(args=("--unknown",), expected_status=2)
            bare = fixture.run("q", "all", "y")
            self.assertIn("Run ae in a terminal", bare.stdout)
            self.assertEqual(fixture.targets(), before)

    def test_bootstrap_without_cargo_explains_how_to_get_it(self):
        with Fixture() as fixture:
            result = fixture.run(env={"AE_BIN": ""}, expected_status=1)
            self.assertIn("rustup.rs", result.stderr)

    def test_unknown_names_are_rejected_with_suggestions(self):
        with Fixture() as fixture:
            fixture.skill("premortem")
            fixture.detect("codex")
            result = fixture.run(args=("add", "-s", "premortm", "-H", "codex", "-y"), expected_status=2)
            self.assertIn("Did you mean `premortem`?", result.stderr)
            result = fixture.run(args=("add", "-s", "premortem", "-H", "codx", "-y"), expected_status=2)
            self.assertIn("Did you mean `codex`?", result.stderr)
            fixture.run(args=("add", "-s", "premortem", "-y"), expected_status=2)
            fixture.run(args=("add", "-H", "codex", "-y"), expected_status=2)
            fixture.run(args=("add", "-y"), expected_status=2)
            fixture.run(args=("add", "-s", "premortem", "-H", "codex", "--json"), expected_status=2)
            self.assertEqual(links(fixture.home), {})


class DetectionTests(unittest.TestCase):
    def test_t3_names_claude_homes_and_status_reports_shared_folders(self):
        with Fixture() as fixture:
            fixture.t3()
            fixture.skill("one")
            fixture.detect("claude-work", "claude-personal", "codex", "grok", "pi", "kilo")
            status = fixture.status()
            harnesses = {h["id"]: h for h in status["harnesses"]}
            self.assertEqual(list(harnesses), ["claude-work", "claude-personal", "codex", "grok", "pi", "kilo"])
            self.assertEqual(harnesses["claude-personal"]["name"], "Claude Personal")
            self.assertEqual(harnesses["claude-personal"]["home"], str(fixture.home / ".claude_personal"))
            self.assertEqual(harnesses["pi"]["home"], str(fixture.pi))
            readers = {loc["path"]: loc["readers"] for loc in status["locations"]}
            self.assertEqual(readers[str(fixture.home / ".agents/skills")], ["codex", "grok", "pi", "kilo"])
            self.assertEqual(readers[str(fixture.home / ".claude/skills")], ["claude-work", "grok", "kilo"])
            self.assertEqual(readers[str(fixture.home / ".claude_personal/skills")], ["claude-personal"])

    def test_environment_overrides_move_harness_homes(self):
        with Fixture() as fixture:
            codex = fixture.root / "codex home"
            codex.mkdir()
            status = json.loads(
                fixture.run(args=("status", "--json"), env={"CODEX_HOME": str(codex)}).stdout
            )
            harnesses = {h["id"]: h for h in status["harnesses"]}
            self.assertEqual(harnesses["codex"]["home"], str(codex))
            self.assertTrue(harnesses["codex"]["detected"])
            self.assertFalse(harnesses["grok"]["detected"])


class SkillTests(unittest.TestCase):
    def test_one_harness_gets_one_link_and_reruns_do_nothing(self):
        with Fixture() as fixture:
            fixture.t3()
            source = fixture.skill("one")
            fixture.skill("two")
            fixture.detect("claude-personal", "codex")
            fixture.run(args=("add", "-s", "one", "-H", "claude-personal", "-y"))
            self.assertEqual(links(fixture.home), {".claude_personal/skills/one": str(source)})
            before = fixture.targets()
            again = fixture.run(args=("add", "-s", "one", "-H", "claude-personal", "-y"))
            self.assertIn("Nothing to do", again.stdout)
            self.assertEqual(fixture.targets(), before)

    def test_every_harness_loads_each_skill_exactly_once(self):
        with Fixture() as fixture:
            fixture.t3()
            one, two = fixture.skill("one"), fixture.skill("two")
            fixture.detect("claude-work", "claude-personal", "codex", "grok", "pi", "kilo")
            result = fixture.run(args=("add", "-s", "all", "-H", "all", "-y"))
            self.assertIn("Done", result.stdout)
            expected = {}
            for name, source in (("one", one), ("two", two)):
                expected[f".claude/skills/{name}"] = str(source)
                expected[f".claude_personal/skills/{name}"] = str(source)
                expected[f".codex/skills/{name}"] = str(source)
            self.assertEqual(links(fixture.home), expected)
            self.assertEqual(links(fixture.pi), {"skills/one": str(one), "skills/two": str(two)})
            everyone = ["claude-work", "claude-personal", "codex", "grok", "pi", "kilo"]
            for skill in fixture.status()["skills"]:
                self.assertEqual(skill["loaded_by"], everyone)

    def test_harnesses_that_share_a_folder_get_one_shared_link(self):
        with Fixture() as fixture:
            fixture.t3()
            source = fixture.skill("one")
            fixture.detect("claude-work", "codex", "grok", "pi", "kilo")
            fixture.run(args=("add", "-s", "one", "-H", "codex,grok,pi,kilo", "-y"))
            self.assertEqual(links(fixture.home), {".agents/skills/one": str(source)})
            self.assertEqual(links(fixture.pi), {})

    def test_claude_work_brings_grok_and_kilo_which_cannot_be_removed_alone(self):
        with Fixture() as fixture:
            fixture.t3()
            source = fixture.skill("one")
            fixture.detect("claude-work", "grok", "kilo")
            fixture.run(args=("add", "-s", "one", "-H", "claude-work", "-y"))
            self.assertEqual(links(fixture.home), {".claude/skills/one": str(source)})
            loaded = fixture.status()["skills"][0]["loaded_by"]
            self.assertEqual(loaded, ["claude-work", "grok", "kilo"])
            before = fixture.targets()
            result = fixture.run(args=("remove", "-s", "one", "-H", "grok", "-y"), expected_status=2)
            self.assertIn("Claude Work", result.stderr)
            self.assertEqual(fixture.targets(), before)

    def test_removing_one_reader_of_a_shared_link_keeps_the_others(self):
        with Fixture() as fixture:
            source = fixture.skill("one")
            fixture.detect("codex", "pi", "kilo")
            fixture.run(args=("add", "-s", "one", "-H", "all", "-y"))
            self.assertEqual(links(fixture.home), {".agents/skills/one": str(source)})
            fixture.run(args=("remove", "-s", "one", "-H", "codex", "-y"))
            self.assertEqual(links(fixture.home), {".config/kilo/skills/one": str(source)})
            self.assertEqual(links(fixture.pi), {"skills/one": str(source)})
            self.assertEqual(fixture.status()["skills"][0]["loaded_by"], ["pi", "kilo"])

    def test_declining_eof_and_dry_run_never_write(self):
        for answers, args in (
            (("n",), ()),
            ((), ()),
            (("",), ()),
            (("y",), ("--dry-run",)),
        ):
            with self.subTest(answers=answers, args=args), Fixture() as fixture:
                fixture.skill("one")
                fixture.detect("codex")
                before = fixture.targets()
                result = fixture.run(*answers, args=("add", "-s", "one", "-H", "codex", *args))
                self.assertIn("link", result.stdout)
                self.assertEqual(fixture.targets(), before)

    def test_undetected_harness_is_linked_only_when_named_explicitly(self):
        with Fixture() as fixture:
            source = fixture.skill("one")
            result = fixture.run(args=("add", "-s", "one", "-H", "grok", "-y"))
            self.assertIn("was not found", result.stderr)
            self.assertEqual(links(fixture.home), {".grok/skills/one": str(source)})


class ConflictTests(unittest.TestCase):
    def test_conflicting_directory_is_skipped_unless_approved_then_backed_up(self):
        with Fixture() as fixture:
            fixture.t3()
            source = fixture.skill("one")
            fixture.detect("claude-personal")
            fixture.write(fixture.home / ".claude_personal/skills/one/SKILL.md", "User copy\n")
            before = fixture.targets()
            fixture.run(args=("add", "-s", "one", "-H", "claude-personal", "-y"), expected_status=1)
            self.assertEqual(fixture.targets(), before)
            fixture.run("n", args=("add", "-s", "one", "-H", "claude-personal"), expected_status=1)
            self.assertEqual(fixture.targets(), before)
            result = fixture.run("y", "y", args=("add", "-s", "one", "-H", "claude-personal"))
            backups = list((fixture.home / ".claude_personal/skills").glob("one.backup.*"))
            self.assertEqual(len(backups), 1)
            self.assertIn(backups[0].name, result.stdout)
            self.assertEqual((backups[0] / "SKILL.md").read_text(), "User copy\n")
            self.assertEqual(links(fixture.home), {".claude_personal/skills/one": str(source)})

    def test_conflicting_symlink_is_replaced_without_touching_its_target(self):
        with Fixture() as fixture:
            source = fixture.skill("one")
            fixture.detect("codex")
            original = fixture.write(fixture.root / "user-skill/SKILL.md", "User skill\n").parent
            (fixture.home / ".codex/skills").mkdir(parents=True)
            (fixture.home / ".codex/skills/one").symlink_to(original)
            fixture.run(args=("add", "-s", "one", "-H", "codex", "--replace", "-y"))
            self.assertEqual(links(fixture.home), {".codex/skills/one": str(source)})
            self.assertEqual((original / "SKILL.md").read_text(), "User skill\n")


class PiTests(unittest.TestCase):
    def assert_pi_links(self, fixture, expected):
        source = fixture.repo / "harness/pi"
        self.assertEqual(links(fixture.pi), {dest: str(source / src) for dest, src in expected.items()})

    def test_extension_only_preserves_policy_prompts_docs_and_existing_installs(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "prompts/second.md", "User prompt\n")
            fixture.write(fixture.pi / "settings.json", '{"extensions": ["custom"]}\n')
            (fixture.pi / "extensions").mkdir()
            (fixture.pi / "extensions/existing").symlink_to(fixture.root / "missing-extension")
            before = fixture.targets()
            fixture.run(args=("add", "-p", "extensions/alpha", "-y"))
            expected = before["pi"].copy()
            expected["extensions/alpha"] = ("link", str(fixture.repo / "harness/pi/extensions/alpha"))
            self.assertEqual(fixture.targets(), {**before, "pi": expected})

    def test_subagents_is_atomic_previewed_and_preserves_other_settings(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.add_subagents()
            settings = {"extensions": ["custom"], "provider": "existing",
                        "subagents": {"defaultModel": "existing-model",
                                      "modelScope": {"allow": ["*"], "enforce": False}}}
            original = json.dumps(settings) + "\n"
            fixture.write(fixture.pi / "settings.json", original)
            fixture.write(fixture.pi / "agents/custom.md", "User agent\n")
            result = fixture.run("y", args=("add", "-p", "subagents"))
            confirmation = result.stdout.index(" [y/N]")
            self.assertLess(result.stdout.index("LINK "), confirmation)
            self.assertLess(result.stdout.index("MERGE subagents.modelScope"), confirmation)
            settings["subagents"]["modelScope"] = {"enforce": True, "strict": True, "allow": ["inherit"]}
            self.assertEqual(json.loads((fixture.pi / "settings.json").read_text()), settings)
            backups = list(fixture.pi.glob("settings.json.backup.*"))
            self.assertEqual([b.read_text() for b in backups], [original])
            self.assertEqual((fixture.pi / "agents/custom.md").read_text(), "User agent\n")
            self.assertEqual(os.readlink(fixture.pi / "agents/reviewer.md"),
                             str(fixture.repo / "harness/pi/subagents/reviewer.md"))
            installed = fixture.targets()
            again = fixture.run(args=("add", "-p", "subagents", "-y"))
            self.assertIn("Nothing to do", again.stdout)
            self.assertEqual(fixture.targets(), installed)

    def test_subagent_decline_and_preflight_failure_change_nothing(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.add_subagents()
            fixture.write(fixture.pi / "settings.json", '{"subagents": {}}\n')
            before = fixture.targets()
            fixture.run("n", args=("add", "-p", "subagents"))
            self.assertEqual(fixture.targets(), before)
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.add_subagents()
            fixture.write(fixture.pi / "settings.json", "malformed private settings")
            before = fixture.targets()
            result = fixture.run(args=("add", "-p", "APPEND_SYSTEM.md,subagents", "-y"), expected_status=1)
            self.assertEqual(fixture.targets(), before)
            self.assertNotIn("malformed private settings", result.stdout + result.stderr)
            fixture.run(args=("remove", "-p", "subagents", "-y"), expected_status=2)

    def test_items_groups_and_all_select_only_eligible_resources(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.repo / "harness/pi/skills/one/SKILL.md", "One\n")
            fixture.run(args=("add", "-p", "commands/second.md,commands/second.md", "-y"))
            self.assert_pi_links(fixture, {"prompts/second.md": "commands/second.md"})
            fixture.run(args=("add", "-p", "commands/all", "-p", "docs", "-y"))
            self.assert_pi_links(fixture, {
                "prompts/first.md": "commands/first.md",
                "prompts/second.md": "commands/second.md",
                "docs": "docs",
            })
            fixture.run(args=("add", "-p", "all", "-y"))
            self.assert_pi_links(fixture, {
                "APPEND_SYSTEM.md": "APPEND_SYSTEM.md",
                "prompts/first.md": "commands/first.md",
                "prompts/second.md": "commands/second.md",
                "docs": "docs",
                "extensions/alpha": "extensions/alpha",
                "extensions/beta": "extensions/beta",
                "extensions/gamma": "extensions/gamma",
                "future-resource": "future-resource",
                "skills/one": "skills/one",
            })
            fixture.run(args=("add", "-p", "commands", "-y"), expected_status=2)

    def test_existing_policy_and_docs_are_backed_up_whole_only_after_approval(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.write(fixture.pi / "docs/local.md", "User notes\n")
            before = fixture.targets()
            result = fixture.run("n", args=("add", "-p", "APPEND_SYSTEM.md,docs"), expected_status=1)
            self.assertIn(str(fixture.pi / "APPEND_SYSTEM.md"), result.stdout)
            self.assertEqual(fixture.targets(), before)
            fixture.run(args=("add", "-p", "APPEND_SYSTEM.md,docs", "--replace", "-y"))
            self.assert_pi_links(fixture, {"APPEND_SYSTEM.md": "APPEND_SYSTEM.md", "docs": "docs"})
            [policy_backup] = fixture.pi.glob("APPEND_SYSTEM.md.backup.*")
            [docs_backup] = fixture.pi.glob("docs.backup.*")
            self.assertEqual(policy_backup.read_text(), "User policy\n")
            self.assertEqual((docs_backup / "local.md").read_text(), "User notes\n")

    def test_remove_unlinks_only_links_into_this_checkout(self):
        with Fixture() as fixture:
            fixture.add_pi_resources()
            fixture.write(fixture.pi / "APPEND_SYSTEM.md", "User policy\n")
            fixture.run(args=("add", "-p", "docs,commands/first.md", "-y"))
            fixture.run(args=("remove", "-p", "docs,APPEND_SYSTEM.md", "-y"))
            self.assert_pi_links(fixture, {"prompts/first.md": "commands/first.md"})
            self.assertEqual((fixture.pi / "APPEND_SYSTEM.md").read_text(), "User policy\n")

    def test_missing_or_empty_pi_tree_is_reported_not_an_error(self):
        for present in (False, True):
            with self.subTest(present=present), Fixture() as fixture:
                if present:
                    (fixture.repo / "harness/pi").mkdir(parents=True)
                before = fixture.targets()
                fixture.run(args=("status",))
                fixture.run(args=("add", "-p", "all", "-y"))
                self.assertEqual(fixture.targets(), before)


class ClaudeTests(unittest.TestCase):
    STYLE = "---\nname: Agentic Engineering\ndescription: Test style.\nkeep-coding-instructions: true\n---\nBe terse.\n"
    DEST = "output-styles/agentic-engineering.md"

    def add_style(self, fixture):
        return fixture.write(fixture.repo / "prompts/OUTPUT_STYLE.md", self.STYLE)

    def test_output_style_links_into_every_claude_home_and_never_edits_settings(self):
        with Fixture() as fixture:
            fixture.t3()
            source = self.add_style(fixture)
            fixture.detect("claude-work", "claude-personal", "codex")
            settings = fixture.write(fixture.home / ".claude/settings.json", '{"outputStyle": "Concise"}\n')
            result = fixture.run(args=("add", "-c", "output-style", "-y"))
            self.assertEqual(links(fixture.home), {
                f".claude/{self.DEST}": str(source),
                f".claude_personal/{self.DEST}": str(source),
            })
            self.assertIn('set "outputStyle": "Agentic Engineering" in ~/.claude/settings.json', result.stdout)
            self.assertEqual(settings.read_text(), '{"outputStyle": "Concise"}\n')
            doctor = fixture.run(args=("doctor", "--no-probe"))
            self.assertIn("Claude Work has the Agentic Engineering output style", doctor.stdout)
            fixture.write(settings, '{"outputStyle": "Agentic Engineering"}\n')
            homes = {h["harness"]: h for h in fixture.status()["claude"][0]["homes"]}
            self.assertEqual((homes["claude-work"]["active"], homes["claude-personal"]["active"]), (True, False))
            self.assertIn("Nothing to do", fixture.run(args=("add", "-c", "all", "-y")).stdout)
            fixture.run(args=("remove", "-c", "output-style", "-H", "claude-personal", "-y"))
            self.assertEqual(links(fixture.home), {f".claude/{self.DEST}": str(source)})

    def test_existing_style_file_is_backed_up_only_after_approval(self):
        with Fixture() as fixture:
            source = self.add_style(fixture)
            fixture.detect("claude-work")
            fixture.write(fixture.home / ".claude" / self.DEST, "User style\n")
            before = fixture.targets()
            fixture.run(args=("add", "-c", "output-style", "-y"), expected_status=1)
            self.assertEqual(fixture.targets(), before)
            fixture.run("y", "y", args=("add", "-c", "output-style"))
            backups = list((fixture.home / ".claude/output-styles").glob("agentic-engineering.md.backup.*"))
            self.assertEqual([b.read_text() for b in backups], ["User style\n"])
            self.assertEqual(links(fixture.home), {f".claude/{self.DEST}": str(source)})

    def test_non_claude_harnesses_and_unknown_items_are_usage_errors(self):
        with Fixture() as fixture:
            self.add_style(fixture)
            fixture.detect("claude-work", "codex")
            fixture.run(args=("add", "-c", "output-style", "-H", "codex", "-y"), expected_status=2)
            result = fixture.run(args=("add", "-c", "output-styles", "-y"), expected_status=2)
            self.assertIn("Did you mean `output-style`?", result.stderr)
            self.assertEqual(links(fixture.home), {})


class PruneTests(unittest.TestCase):
    def test_prune_removes_stale_and_redundant_links_only(self):
        with Fixture() as fixture:
            source = fixture.skill("one")
            fixture.detect("codex", "pi")
            shared = fixture.home / ".agents/skills"
            shared.mkdir(parents=True)
            (shared / "one").symlink_to(source)
            (fixture.pi / "skills").mkdir(parents=True)
            (fixture.pi / "skills/one").symlink_to(source)
            (shared / "renamed").symlink_to(fixture.repo / "skills/old-name")
            (shared / "user").symlink_to(fixture.root / "elsewhere")
            status = fixture.run(args=("status",)).stdout
            self.assertIn("is redundant", status)
            self.assertIn("no longer exists", status)
            preview = fixture.run(args=("prune", "-n"))
            self.assertIn("renamed", preview.stdout)
            fixture.run(args=("prune", "-y"))
            self.assertEqual(links(fixture.home), {
                ".agents/skills/one": str(source),
                ".agents/skills/user": str(fixture.root / "elsewhere"),
            })
            self.assertEqual(links(fixture.pi), {})
            self.assertEqual(fixture.status()["skills"][0]["loaded_by"], ["codex", "pi"])

    def test_prune_removes_pi_prompt_links_for_commands_that_became_skills(self):
        with Fixture() as fixture:
            fixture.detect("pi")
            prompts = fixture.pi / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "wat.md").symlink_to(fixture.repo / "harness/pi/commands/wat.md")
            (prompts / "mine.md").write_text("user prompt\n")
            fixture.run(args=("prune", "-y"))
            self.assertFalse(os.path.lexists(prompts / "wat.md"))
            self.assertEqual((prompts / "mine.md").read_text(), "user prompt\n")


class ToolTests(unittest.TestCase):
    def test_tools_install_only_selected_packages_with_cargo(self):
        with Fixture() as fixture:
            fixture.write(fixture.repo / "tools/one/Cargo.toml", "[package]\nname='one'\nversion='1.0.0'\n")
            fixture.write(fixture.repo / "tools/two/Cargo.toml", "[package]\nname='two'\nversion='2.0.0'\n")
            fixture.write(fixture.repo / "tools/two/Cargo.lock", "[[package]]\nname='two'\n")
            calls = fixture.root / "cargo-calls"
            cargo = fixture.write(fixture.bin / "cargo", '#!/bin/bash\nprintf "%s\\n" "$@" >> "$CARGO_CALLS"\n')
            cargo.chmod(0o755)
            before = fixture.targets()
            fixture.run(args=("add", "-t", "two", "-y"), env={"CARGO_CALLS": str(calls)})
            self.assertEqual(calls.read_text().splitlines(), [
                "install", "--path", str(fixture.repo / "tools/two"), "--force", "--locked",
            ])
            self.assertEqual(fixture.targets(), before)
            fixture.run(args=("add", "-t", "three", "-y"), expected_status=2, env={"CARGO_CALLS": str(calls)})

    def test_failed_build_is_reported_with_a_log(self):
        with Fixture() as fixture:
            fixture.write(fixture.repo / "tools/one/Cargo.toml", "[package]\nname='one'\n")
            cargo = fixture.write(fixture.bin / "cargo", '#!/bin/bash\necho "error: could not compile" >&2\nexit 101\n')
            cargo.chmod(0o755)
            result = fixture.run(args=("add", "-t", "one", "-y"), expected_status=1)
            self.assertIn("could not compile", result.stdout)
            self.assertIn("log:", result.stdout)


if __name__ == "__main__":
    unittest.main()
