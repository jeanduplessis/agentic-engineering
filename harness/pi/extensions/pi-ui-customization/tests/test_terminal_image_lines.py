import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "pi-ui-customization" / "terminal-image-lines.ts"


class TerminalImageLineTests(unittest.TestCase):
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

    def test_detects_kitty_and_iterm2_graphics_sequences(self):
        script = textwrap.dedent(
            f"""
            import {{ isTerminalImageLine }} from {json.dumps(HELPER.as_uri())};
            const kitty = "\\x1b_Ga=T,f=100,q=2,C=1,c=60,r=25,i=1486589253,m=1;iVBORw0KGgo\\x1b\\\\";
            const iterm = "\\x1b]1337;File=inline=1;size=12:iVBORw0KGgo=\\x07";
            console.log(JSON.stringify({{
                kitty: isTerminalImageLine(kitty),
                iterm: isTerminalImageLine(iterm),
                cursorPrefixed: isTerminalImageLine("\\x1b[24A" + kitty),
                title: isTerminalImageLine("read /tmp/photo.jpg:1-1"),
                empty: isTerminalImageLine(""),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "kitty": True,
                "iterm": True,
                "cursorPrefixed": True,
                "title": False,
                "empty": False,
            },
        )

    def test_map_non_image_lines_leaves_graphics_sequences_untouched(self):
        script = textwrap.dedent(
            f"""
            import {{ mapNonImageLines }} from {json.dumps(HELPER.as_uri())};
            const title = "read /tmp/photo.jpg:1-1";
            const kitty = "\\x1b_Ga=T,f=100,q=2,C=1,c=60,r=25,i=1486589253,m=1;iVBORw0KGgo\\x1b\\\\";
            const mapped = mapNonImageLines([title, kitty, ""], (line) => `mutated:${{line}}`);
            console.log(JSON.stringify({{
                mapped,
                kittyUnchanged: mapped[1] === kitty,
                startsWithKitty: mapped[1].startsWith("\\x1b_G"),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "mapped": ["mutated:read /tmp/photo.jpg:1-1", "\x1b_Ga=T,f=100,q=2,C=1,c=60,r=25,i=1486589253,m=1;iVBORw0KGgo\x1b\\", ""],
                "kittyUnchanged": True,
                "startsWithKitty": True,
            },
        )
