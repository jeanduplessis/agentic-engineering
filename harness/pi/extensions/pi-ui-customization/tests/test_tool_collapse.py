import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "pi-ui-customization" / "tool-collapse.ts"


class ToolCollapseTests(unittest.TestCase):
    def run_node(self, script: str) -> object:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_unexpanded_blocks_are_collapsed_and_clickable(self):
        script = textwrap.dedent(
            f"""
            import {{ decideToolCollapse }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                collapsed: decideToolCollapse({{ expanded: false }}),
                expanded: decideToolCollapse({{ expanded: true }}),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "collapsed": {"clickable": True, "compact": True},
                "expanded": {"clickable": True, "compact": False},
            },
        )
