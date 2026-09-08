"""Exercise the subagent installer CLI only against disposable directories."""

import json
import os
import subprocess
import sys
import unittest

from test_setup import SetupFixture, tree


SCOPE = {"enforce": True, "strict": True, "allow": ["inherit"]}


def run_installer(fixture, *args, status=0):
    source_before = tree(fixture.repo)
    result = subprocess.run(
        [sys.executable, str(fixture.repo / "harness/pi/subagents/install.py"), *args],
        capture_output=True, text=True, env=fixture.env, cwd=fixture.repo, timeout=10,
    )
    if result.returncode != status:
        raise AssertionError(f"Expected {status}, got {result.returncode}: {result.stdout}\n{result.stderr}")
    if tree(fixture.repo) != source_before:
        raise AssertionError("Installer modified its source checkout")
    return result


class SubagentInstallTests(unittest.TestCase):
    def test_check_is_read_only_apply_is_idempotent_and_only_installs_two_resources(self):
        with SetupFixture() as fixture:
            fixture.add_subagents()
            before = fixture.targets()
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--check", status=1)
            self.assertEqual(fixture.targets(), before)
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
            settings = fixture.pi / "settings.json"
            self.assertEqual(json.loads(settings.read_text()), {"subagents": {"modelScope": SCOPE}})
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            self.assertEqual(set(tree(fixture.pi)), {".", "settings.json", "agents", "agents/reviewer.md"})
            installed = fixture.targets()
            stat_before = settings.stat()
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--check")
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
            self.assertEqual(fixture.targets(), installed)
            self.assertEqual(settings.stat().st_mtime_ns, stat_before.st_mtime_ns)
            self.assertEqual(settings.stat().st_ino, stat_before.st_ino)

    def test_merge_preserves_unrelated_nested_values_and_backs_up_original_bytes(self):
        with SetupFixture() as fixture:
            fixture.add_subagents()
            original = {"private": "do-not-display", "theme": "custom", "packages": ["package"],
                        "subagents": {"agentOverrides": {"worker": {"model": "kept-pin"}},
                                      "agentOverridesByProvider": {"provider": {"reviewer": {"tools": "read"}}},
                                      "defaultModel": "kept-default", "globalConcurrencyLimit": 11,
                                      "timeoutMs": 999999, "modelScope": {
                                          "enforce": False, "allow": ["*"],
                                          "agents": {"reviewer": {"enforce": False}}}}}
            raw = json.dumps(original, separators=(",", ":")) + "\n"
            settings = fixture.write(fixture.pi / "settings.json", raw)
            original["subagents"]["modelScope"] = SCOPE
            result = run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
            self.assertEqual(json.loads(settings.read_text()), original)
            self.assertNotIn("do-not-display", result.stdout + result.stderr)
            self.assertNotIn("kept-pin", result.stdout + result.stderr)
            backups = list(fixture.pi.glob("settings.json.backup.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), raw)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            # Another authorized policy change must not overwrite the first backup.
            settings.write_text('{"subagents":{"modelScope":{"allow":["*"]}}}')
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
            self.assertEqual(len(list(fixture.pi.glob("settings.json.backup.*"))), 2)
            self.assertEqual(backups[0].read_text(), raw)

    def test_scope_requires_boolean_enforcement_not_truthy_numbers(self):
        with SetupFixture() as fixture:
            fixture.add_subagents()
            fixture.write(fixture.pi / "settings.json",
                          '{"subagents":{"modelScope":{"enforce":1,"strict":1,"allow":["inherit"]}}}')
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--check", status=1)
            run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
            scope = json.loads((fixture.pi / "settings.json").read_text())["subagents"]["modelScope"]
            self.assertIs(scope["enforce"], True)
            self.assertIs(scope["strict"], True)

    def test_invalid_settings_refused_without_any_mutation_or_content_disclosure(self):
        invalid = ('{"private":"secret-value",', '[]', 'null', '{"subagents":null}',
                   '{"subagents":[]}', '{"private":1,"private":2}',
                   '{"private":NaN}', '{"private":Infinity}', '{"private":1e999}')
        for raw in invalid:
            with self.subTest(raw=raw), SetupFixture() as fixture:
                fixture.add_subagents()
                fixture.write(fixture.pi / "settings.json", raw)
                fixture.write(fixture.pi / "agents/reviewer.md", "Keep this reviewer\n")
                before = fixture.targets()
                for mode in ("--check", "--apply"):
                    result = run_installer(fixture, "--agent-dir", str(fixture.pi), mode, status=2)
                    self.assertEqual(fixture.targets(), before)
                    self.assertNotIn("secret-value", result.stdout + result.stderr)

    def test_invalid_overlay_refused_before_target_directory_creation(self):
        for raw in ('{', '{"subagents":{"modelScope":{"enforce":true,"strict":true,"allow":["*"]}}}'):
            with self.subTest(raw=raw), SetupFixture() as fixture:
                fixture.add_subagents()
                fixture.write(fixture.repo / "harness/pi/subagents/settings-overlay.json", raw)
                before = fixture.targets()
                run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply", status=2)
                self.assertEqual(fixture.targets(), before)

    def test_symlinked_settings_refused_even_when_dangling_or_policy_matches(self):
        for present in (False, True):
            with self.subTest(present=present), SetupFixture() as fixture:
                fixture.add_subagents()
                target = fixture.root / "external-settings.json"
                if present:
                    target.write_text(json.dumps({"subagents": {"modelScope": SCOPE}}))
                fixture.pi.mkdir()
                (fixture.pi / "settings.json").symlink_to(target)
                before = tree(fixture.root)
                run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply", status=2)
                self.assertEqual(tree(fixture.root), before)

    def test_conflicting_reviewer_file_or_link_is_backed_up_without_touching_referent(self):
        for kind in ("file", "link", "dangling-link"):
            with self.subTest(kind=kind), SetupFixture() as fixture:
                fixture.add_subagents()
                reviewer = fixture.pi / "agents/reviewer.md"
                reviewer.parent.mkdir(parents=True)
                target = fixture.root / "user-reviewer.md"
                if kind == "file":
                    reviewer.write_text("Keep original reviewer\n")
                else:
                    if kind == "link":
                        target.write_text("Keep external reviewer\n")
                    reviewer.symlink_to(target)
                original = tree(reviewer)
                referent_before = tree(target)
                run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
                backups = list(reviewer.parent.glob("reviewer.md.backup.*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(tree(backups[0]), original)
                self.assertEqual(tree(target), referent_before)
                self.assertEqual(os.readlink(reviewer), str(fixture.repo / "harness/pi/subagents/reviewer.md"))
                installed = fixture.targets()
                run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply")
                self.assertEqual(fixture.targets(), installed)

    def test_unsafe_destination_types_refused_without_changes(self):
        for kind in ("agent-link", "agents-link", "settings-directory", "reviewer-directory", "agent-file"):
            with self.subTest(kind=kind), SetupFixture() as fixture:
                fixture.add_subagents()
                external = fixture.root / "external"
                external.mkdir()
                if kind == "agent-link":
                    fixture.pi.symlink_to(external, target_is_directory=True)
                elif kind == "agent-file":
                    fixture.pi.write_text("Not a directory")
                else:
                    fixture.pi.mkdir()
                    if kind == "agents-link":
                        (fixture.pi / "agents").symlink_to(external, target_is_directory=True)
                    elif kind == "settings-directory":
                        (fixture.pi / "settings.json").mkdir()
                    else:
                        (fixture.pi / "agents/reviewer.md").mkdir(parents=True)
                before = tree(fixture.root)
                run_installer(fixture, "--agent-dir", str(fixture.pi), "--apply", status=2)
                self.assertEqual(tree(fixture.root), before)

    def test_cli_requires_explicit_target_and_action(self):
        with SetupFixture() as fixture:
            fixture.add_subagents()
            before = fixture.targets()
            for args in ((), ("--apply",), ("--agent-dir", str(fixture.pi)),
                         ("--agent-dir", str(fixture.pi), "--check", "--apply")):
                run_installer(fixture, *args, status=2)
                self.assertEqual(fixture.targets(), before)


if __name__ == "__main__":
    unittest.main()
