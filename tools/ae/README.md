# ae

Æ (Agentic Engineering) installer. `ae` links this checkout's skills into every coding harness on the machine, plus Pi resources and the repository's Rust tools. You pick everything from one keyboard-driven grid, review the plan, and watch it apply.

## Run

From the repository root:

```sh
./setup.sh            # builds ae with cargo, then opens the installer
./setup.sh status     # any arguments pass through to ae
```

Or install the binary once (the **Tools** tab can do this for you):

```sh
cargo install --path tools/ae --locked
ae
```

`ae` remembers the checkout it was built from. `--repo PATH` or `AE_REPO` points it at another one.

## Harnesses

`ae` reads T3 Code's settings (`~/.t3/userdata/settings.json`). Each enabled `claudeAgent` provider instance becomes its own Claude Code harness, named by its display name and rooted at its `homePath`. Without T3 Code, you get `~/.claude`, plus `CLAUDE_CONFIG_DIR` when it points somewhere else.

| Harness | Home | Skill folders it loads, own folder first |
| --- | --- | --- |
| Claude Code (each T3 instance) | `homePath` | `<home>/skills` |
| Codex | `CODEX_HOME` or `~/.codex` | `<home>/skills`, `~/.agents/skills` |
| Grok | `GROK_HOME` or `~/.grok` | `<home>/skills`, `~/.agents/skills`, `~/.claude/skills` |
| Pi | `PI_CODING_AGENT_DIR`, `PI_AGENT_DIR` or `~/.pi/agent` | `<home>/skills`, `~/.agents/skills` |
| Kilo | `KILO_CONFIG_DIR`, `$XDG_CONFIG_HOME/kilo` or `~/.config/kilo` | `<home>/skills`, `~/.agents/skills`, `~/.claude/skills` |

A harness is detected when its binary is on `PATH` or its home exists. An instance disabled in T3 Code is marked as such but still counted, because its folder is still read when that home is used directly. Naming a harness with `-H` includes it even when it wasn't detected.

### Where a link goes

You choose skill × harness pairs. `ae` then picks the folders, so that every chosen harness loads exactly one copy and no other harness picks one up. In order, it minimizes:

1. links removed
2. harnesses that would load the skill twice, counting copies Æ doesn't manage
3. things in the way that need a backup
4. folders used
5. links added

Ties go to a folder the harness calls its own, not a shared one.

Shared folders tie harnesses together. `~/.claude/skills` is both the default Claude Code home's folder and a folder Grok and Kilo read, so giving a skill to that Claude harness gives it to Grok and Kilo too. The grid shows ◐ on those cells, and you can't remove a skill from Grok alone while Claude still loads it from there. With Claude selected, Codex and Pi get their own links, because a link in `~/.agents/skills` would make Grok and Kilo load it twice.

## Claude Code output style

`prompts/OUTPUT_STYLE.md` is a Claude Code output style. `ae` links it into each selected Claude Code home as `output-styles/<slug of its name>.md`, for example `~/.claude/output-styles/agentic-engineering.md`. Its frontmatter sets `keep-coding-instructions: true`, so it adds to Claude Code's system prompt rather than replacing the coding instructions.

A linked style is available, not active. Claude Code uses it only when that home's `settings.json` has `"outputStyle": "<its name>"`, which applies to every new session from that home, T3 Code threads included. `ae` never edits `settings.json`. It reads `outputStyle` to show in `status`, the Claude tab and `doctor` whether each home selects the style, and prints the setting to add after linking. Only one output style is active per home, so selecting this one replaces any other.

## Interactive installer

`ae` with no arguments, in a terminal. There are four tabs: **Skills** (a skills × harnesses grid), **Pi** (resources linked into the Pi agent dir), **Tools** (`cargo install --path`) and **Claude** (Claude Code resources × Claude Code homes). Toggling things only queues changes. Nothing on disk changes until you press enter, review the plan and confirm.

| Key | Action |
| --- | --- |
| `↑↓←→` or `hjkl` | move |
| `space` | toggle the highlighted cell, Pi item or tool |
| `a` / `A` | toggle the whole row / column |
| `/` | filter skills by name or description |
| `tab`, `1` `2` `3` `4` | switch tabs |
| `p` | queue removal of stale and redundant links |
| `r` / `R` | reset this row / every pending change |
| `enter` | review the plan; `space` there approves or skips each conflict |
| `ctrl-c` | while applying: stop after the current step |
| `?` / `q` | help / quit (asks first if changes are pending) |

Grid glyphs: ● loads this checkout's copy, + will be added, − will be removed, ◐ comes along via a shared folder, ◆ a different copy that Æ doesn't manage, ! something is in the way.

The grid shows what's installed right now. Unticking a cell removes only Æ's own links. Applying shows per-step progress, with a live progress bar for cargo builds and a summary at the end. When a run changes something, `ae` reminds you to restart the affected harnesses.

## Commands

```text
ae                         interactive installer (status when not a terminal)
ae status                  harnesses, versions, the skills matrix, Pi items, tools, problems
ae doctor [--no-probe]     check links; ask Grok, Kilo and Codex which skills they load
ae add    [-s ..] [-H ..] [-p ..] [-t ..] [--replace] [-n] [-y]
ae remove [-s ..] [-H ..] [-p ..] [-n] [-y]
ae prune  [-n] [-y]        remove stale links and links another folder already covers
ae completions <shell>     bash, zsh, fish, elvish, powershell
```

```sh
ae add -s council-review -H all             # one skill, every detected harness
ae add -s premortem,wat -H claude-personal,codex
ae remove -s premortem -H codex
ae add -p APPEND_SYSTEM.md -p extensions/prompt-stash
ae add -p extensions/all -n                 # preview every Pi extension
ae add -c output-style                      # every Claude Code home
ae remove -c output-style -H claude-personal
ae add -t gs,gw                             # build and install tools
ae prune -n
```

- `-s` takes skill names or `all`. `-H` takes a harness id from `ae status` (e.g. `claude-work`, `codex`), its label (`CW`), its kind (`claude`, matching every Claude instance) or `all`.
- `-c` takes `output-style` or `all`. Without `-H` it changes every detected Claude Code home; with `-H` it changes the Claude Code homes named there.
- `-p` takes `APPEND_SYSTEM.md`, `docs`, `subagents`, `commands/<file>`, `extensions/<name>`, `skills/<name>`, `<group>/all` or `all`. The `subagents` component runs `harness/pi/subagents/install.py`, which merges only `subagents.modelScope` and links `agents/reviewer.md`.
- Unknown names fail with a "did you mean" suggestion. Every change prints the plan and asks first, and conflicts are a separate question. `-n` stops after the plan. `-y` skips both questions; conflicts are then skipped unless `--replace` is given.
- `--json` works with `status`, `doctor`, and `add`, `remove` and `prune` when given with `-n` or `-y`.

Exit codes: `0` success, nothing to do, or cancelled. `1` a step failed, a conflict was skipped, or `doctor` found a warning or a harness that loads something different. `2` usage error.

## Safety contract

- The only things `ae` creates or removes are symlinks that point into this checkout. A link it removes must still point into the checkout at that moment, or it's left alone.
- Anything else in the way is a conflict. It's replaced only after you approve it. Files and directories are first moved to `<name>.backup.<UTC timestamp>`. A foreign symlink is removed, and the plan shows where it pointed.
- Every step checks the filesystem again just before it acts, so a plan can't act on anything that changed after you reviewed it.
- Reruns are idempotent. Unrelated files, settings and other people's skills are never touched, and nothing is copied, so no secrets move.
- cargo output goes to `$TMPDIR/ae-logs/<tool>-<timestamp>.log`.

## Environment

| Variable | Effect |
| --- | --- |
| `AE_REPO` | checkout to install from |
| `AE_NO_PROBE` | skip harness version and `doctor` probes |
| `NO_COLOR` | plain output; `COLORTERM=truecolor` enables the full palette |
| `CODEX_HOME`, `GROK_HOME`, `PI_CODING_AGENT_DIR`, `PI_AGENT_DIR`, `KILO_CONFIG_DIR`, `XDG_CONFIG_HOME`, `CLAUDE_CONFIG_DIR`, `CARGO_HOME` | harness and tool locations, as above |
