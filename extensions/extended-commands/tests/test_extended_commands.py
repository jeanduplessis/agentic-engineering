import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
EXTENSION = REPO_ROOT / "extensions" / "extended-commands" / "index.ts"


class ExtendedCommandsTests(unittest.TestCase):
    def run_node(self, script: str) -> str:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_argument_substitution_preserves_raw_arguments_and_simple_positions(self):
        body = "Raw=$ARGUMENTS\nAll=$@\nOne=$1\nTwo=$2\nMissing=$3"
        script = textwrap.dedent(
            f"""
            import {{ substituteArguments }} from {json.dumps(EXTENSION.as_uri())};
            const body = {json.dumps(body)};
            const rendered = substituteArguments(body, "alpha \\\"two words\\\"");
            console.log(JSON.stringify(rendered));
            """
        )

        rendered = json.loads(self.run_node(script))

        self.assertEqual(rendered, "Raw=alpha \"two words\"\nAll=alpha two words\nOne=alpha\nTwo=two words\nMissing=")

    def test_discovery_loads_only_direct_markdown_commands_with_runtime_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha-command.md").write_text(
                "---\ndescription: Alpha command\nunknown: value\n---\nRun $1\n!`legacy`\n@legacy/file.txt\n"
            )
            (root / "notes.txt").write_text("ignore")
            (root / "nested").mkdir()
            (root / "nested" / "beta-command.md").write_text("ignore")
            script = textwrap.dedent(
                f"""
                import {{ discoverCommands }} from {json.dumps(EXTENSION.as_uri())};
                const commands = discoverCommands({json.dumps(str(root))});
                console.log(JSON.stringify(commands));
                """
            )

            commands = json.loads(self.run_node(script))

            self.assertEqual([command["name"] for command in commands], ["alpha-command"])
            self.assertEqual(commands[0]["description"], "Alpha command")
            self.assertEqual(commands[0]["body"], "Run $1\n!`legacy`\n@legacy/file.txt\n")
            self.assertTrue(any("Unknown frontmatter field" in warning for warning in commands[0]["warnings"]))
            self.assertTrue(any("shell expansion" in warning for warning in commands[0]["warnings"]))
            self.assertTrue(any("file expansion" in warning for warning in commands[0]["warnings"]))

    def test_registered_plain_command_sends_rendered_body_without_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plain-command.md").write_text(
                "---\ndescription: Plain command\n---\nUse $1 and $ARGUMENTS. Keep !`legacy` literal.\n"
            )
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const sent = [];
                const notifications = [];
                const pi = {{
                  registerCommand(name, options) {{ registered.push({{ name, options }}); }},
                  sendUserMessage(message, options) {{ sent.push({{ message, options: options ?? null }}); }},
                }};
                registerExtendedCommands(pi, {json.dumps(str(root))});
                await registered[0].options.handler('alpha beta', {{
                  isIdle() {{ return true; }},
                  ui: {{ notify(message, level) {{ notifications.push({{ message, level }}); }} }},
                }});
                console.log(JSON.stringify({{
                  registered: registered.map((entry) => ({{ name: entry.name, description: entry.options.description }})),
                  sent,
                  notifications,
                  hasSetModel: Object.prototype.hasOwnProperty.call(pi, 'setModel'),
                  hasSetThinking: Object.prototype.hasOwnProperty.call(pi, 'setThinkingLevel'),
                }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["registered"], [{"name": "plain-command", "description": "Plain command"}])
            self.assertEqual(result["sent"], [{"message": "Use alpha and alpha beta. Keep !`legacy` literal.\n", "options": None}])
            self.assertEqual(result["notifications"][0]["level"], "warning")
            self.assertIn("shell expansion", result["notifications"][0]["message"])
            self.assertFalse(result["hasSetModel"])
            self.assertFalse(result["hasSetThinking"])

    def test_model_resolution_supports_exact_and_unique_bare_ids_only(self):
        script = textwrap.dedent(
            f"""
            import {{ resolveDeclaredModel }} from {json.dumps(EXTENSION.as_uri())};
            const models = [
              {{ provider: 'anthropic', id: 'claude-sonnet' }},
              {{ provider: 'openrouter', id: 'claude-sonnet' }},
              {{ provider: 'google', id: 'gemini-pro' }},
            ];
            const registry = {{
              find(provider, id) {{ return models.find((model) => model.provider === provider && model.id === id); }},
              getAll() {{ return models; }},
            }};
            console.log(JSON.stringify({{
              exact: resolveDeclaredModel('anthropic/claude-sonnet', registry),
              bare: resolveDeclaredModel('gemini-pro', registry),
              ambiguous: resolveDeclaredModel('claude-sonnet', registry),
              missing: resolveDeclaredModel('missing-model', registry),
            }}));
            """
        )

        result = json.loads(self.run_node(script))

        self.assertEqual(result["exact"]["model"], {"provider": "anthropic", "id": "claude-sonnet"})
        self.assertIsNone(result["exact"].get("error"))
        self.assertEqual(result["bare"]["model"], {"provider": "google", "id": "gemini-pro"})
        self.assertIn("ambiguous", result["ambiguous"]["error"])
        self.assertIn("not available", result["missing"]["error"])

    def test_routed_command_sets_model_and_thinking_then_restores_by_default_after_agent_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "routed-command.md").write_text(
                "---\ndescription: Routed\nmodel: anthropic/claude-sonnet\nthinking: high\n---\nDo $1\n"
            )
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const handlers = {{}};
                const sent = [];
                const modelCalls = [];
                const thinkingCalls = [];
                const current = {{ provider: 'google', id: 'gemini-pro' }};
                const target = {{ provider: 'anthropic', id: 'claude-sonnet' }};
                const pi = {{
                  registerCommand(name, options) {{ registered.push({{ name, options }}); }},
                  on(event, handler) {{ handlers[event] = handler; }},
                  sendUserMessage(message, options) {{ sent.push({{ message, options: options ?? null }}); }},
                  async setModel(model) {{ modelCalls.push(model); return true; }},
                  getThinkingLevel() {{ return 'low'; }},
                  setThinkingLevel(level) {{ thinkingCalls.push(level); }},
                }};
                registerExtendedCommands(pi, {json.dumps(str(root))});
                await registered[0].options.handler('work', {{
                  model: current,
                  modelRegistry: {{ find(provider, id) {{ return provider === target.provider && id === target.id ? target : undefined; }}, getAll() {{ return [current, target]; }} }},
                  isIdle() {{ return true; }},
                  ui: {{ notify() {{}} }},
                }});
                await handlers.agent_end?.({{}}, {{}});
                console.log(JSON.stringify({{ sent, modelCalls, thinkingCalls }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["sent"], [{"message": "Do work\n", "options": None}])
            self.assertEqual(result["modelCalls"], [{"provider": "anthropic", "id": "claude-sonnet"}, {"provider": "google", "id": "gemini-pro"}])
            self.assertEqual(result["thinkingCalls"], ["high", "low"])

    def test_restore_false_keeps_model_and_thinking_sticky(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sticky-command.md").write_text(
                "---\ndescription: Sticky\nmodel: anthropic/claude-sonnet\nthinking: medium\nrestore: false\n---\nStick\n"
            )
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const handlers = {{}};
                const modelCalls = [];
                const thinkingCalls = [];
                const target = {{ provider: 'anthropic', id: 'claude-sonnet' }};
                const pi = {{
                  registerCommand(name, options) {{ registered.push({{ name, options }}); }},
                  on(event, handler) {{ handlers[event] = handler; }},
                  sendUserMessage() {{}},
                  async setModel(model) {{ modelCalls.push(model); return true; }},
                  getThinkingLevel() {{ return 'low'; }},
                  setThinkingLevel(level) {{ thinkingCalls.push(level); }},
                }};
                registerExtendedCommands(pi, {json.dumps(str(root))});
                await registered[0].options.handler('', {{
                  model: {{ provider: 'google', id: 'gemini-pro' }},
                  modelRegistry: {{ find(provider, id) {{ return provider === target.provider && id === target.id ? target : undefined; }}, getAll() {{ return [target]; }} }},
                  isIdle() {{ return true; }},
                  ui: {{ notify() {{}} }},
                }});
                await handlers.agent_end?.({{}}, {{}});
                console.log(JSON.stringify({{ modelCalls, thinkingCalls }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["modelCalls"], [{"provider": "anthropic", "id": "claude-sonnet"}])
            self.assertEqual(result["thinkingCalls"], ["medium"])

    def test_unavailable_declared_model_reports_error_and_does_not_send_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "missing-model.md").write_text("---\ndescription: Missing\nmodel: missing\n---\nBody\n")
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const notifications = [];
                const sent = [];
                const pi = {{ registerCommand(name, options) {{ registered.push({{ name, options }}); }}, on() {{}}, sendUserMessage(message) {{ sent.push(message); }} }};
                registerExtendedCommands(pi, {json.dumps(str(root))});
                await registered[0].options.handler('', {{
                  modelRegistry: {{ find() {{ return undefined; }}, getAll() {{ return []; }} }},
                  isIdle() {{ return true; }},
                  ui: {{ notify(message, level) {{ notifications.push({{ message, level }}); }} }},
                }});
                console.log(JSON.stringify({{ notifications, sent }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["sent"], [])
            self.assertEqual(result["notifications"][0]["level"], "error")
            self.assertIn("not available", result["notifications"][0]["message"])

    def test_declared_skill_is_injected_as_visible_custom_message_before_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "commands").mkdir()
            (root / "skills" / "review-skill").mkdir(parents=True)
            (root / "skills" / "review-skill" / "SKILL.md").write_text("# Review Skill\nUse carefully.\n")
            (root / "commands" / "skill-command.md").write_text(
                "---\ndescription: Skill command\nskill: review-skill\n---\nPrompt $1\n"
            )
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const customMessages = [];
                const userMessages = [];
                const pi = {{
                  registerCommand(name, options) {{ registered.push({{ name, options }}); }},
                  on() {{}},
                  sendMessage(message, options) {{ customMessages.push({{ message, options: options ?? null }}); }},
                  sendUserMessage(message, options) {{ userMessages.push({{ message, options: options ?? null }}); }},
                }};
                registerExtendedCommands(pi, {json.dumps(str(root / 'commands'))});
                await registered[0].options.handler('target', {{
                  cwd: {json.dumps(str(root))},
                  isIdle() {{ return true; }},
                  ui: {{ notify() {{}} }},
                }});
                console.log(JSON.stringify({{ customMessages, userMessages }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["customMessages"][0]["message"]["customType"], "extended-command-skill")
            self.assertTrue(result["customMessages"][0]["message"]["display"])
            self.assertIn("# Review Skill", result["customMessages"][0]["message"]["content"])
            self.assertEqual(result["userMessages"], [{"message": "Prompt target\n", "options": None}])

    def test_missing_declared_skill_reports_error_before_prompt_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "missing-skill.md").write_text("---\ndescription: Missing skill\nskill: nope\n---\nBody\n")
            script = textwrap.dedent(
                f"""
                import {{ registerExtendedCommands }} from {json.dumps(EXTENSION.as_uri())};
                const registered = [];
                const notifications = [];
                const sent = [];
                const pi = {{ registerCommand(name, options) {{ registered.push({{ name, options }}); }}, on() {{}}, sendMessage() {{}}, sendUserMessage(message) {{ sent.push(message); }} }};
                registerExtendedCommands(pi, {json.dumps(str(root))});
                await registered[0].options.handler('', {{ cwd: {json.dumps(str(root))}, isIdle() {{ return true; }}, ui: {{ notify(message, level) {{ notifications.push({{ message, level }}); }} }} }});
                console.log(JSON.stringify({{ notifications, sent }}));
                """
            )

            result = json.loads(self.run_node(script))

            self.assertEqual(result["sent"], [])
            self.assertEqual(result["notifications"][0]["level"], "error")
            self.assertIn("skill", result["notifications"][0]["message"])

    def test_documentation_covers_validator_runtime_migration_and_out_of_scope(self):
        extension_readme = (REPO_ROOT / "extensions" / "extended-commands" / "README.md").read_text()
        command_valid_readme = (REPO_ROOT / "tools" / "command_valid" / "README.md").read_text()
        root_readme = (REPO_ROOT / "README.md").read_text()

        combined = "\n".join([extension_readme, command_valid_readme, root_readme])

        self.assertIn("command_valid", combined)
        self.assertIn("runtime", combined.lower())
        self.assertIn("strict", combined.lower())
        self.assertIn("OpenCode", combined)
        self.assertIn("project-local", combined)
        self.assertIn("multiple skills", combined)
        self.assertIn("subagents", combined)


if __name__ == "__main__":
    unittest.main()
