# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are personalized for how I work.

My skills, harness resources and tools for agentic engineering. I run agents through T3 Code on Claude Code (work and personal configs), OpenAI Codex and Grok Build, with Pi and Kilo as secondary harnesses.

## Setup

```sh
./setup.sh
```

This builds [`ae`](tools/ae/README.md), the Æ installer, with cargo (install Rust from [rustup.rs](https://rustup.rs) first) and opens it. `ae` finds T3 Code and every harness on the machine. It shows a grid of skills × harnesses, a Pi tab and a Tools tab. You tick what you want, review the plan, and watch it apply. Arguments pass through: `./setup.sh status`, `./setup.sh add -s wat -H all`, `./setup.sh doctor`.

- The grid shows what's installed now. Nothing is queued until you choose it, and nothing changes before you confirm the plan.
- `ae` only creates or removes symlinks into this checkout, so edits here take effect without reinstalling. Anything else in the way is backed up, and only after you approve it.
- Each harness loads one copy of each skill you pick for it. `ae` places links around the folders harnesses share: `~/.claude/skills` is read by Claude Code, Grok and Kilo, and `~/.agents/skills` by Codex, Grok, Pi and Kilo. See [where a link goes](tools/ae/README.md#where-a-link-goes).
- `ae doctor` asks Grok, Kilo and Codex which skills they actually load and reports any mismatch. `ae prune` removes stale links, such as ones left behind by a renamed skill.

## Skills

Skills live in `skills/<name>/SKILL.md` and use the [Agent Skills](https://agentskills.io) format, so every supported harness can load them. Some are meant to run only when you invoke them by name (`/pr-audit`, `$pr-audit` or `/skill:pr-audit`, depending on the harness). They set `disable-model-invocation: true`, which harnesses that support it honor. Those are `pr-analyze`, `pr-audit`, `pr-review-analyze`, `session-retro`, `spec-audit`, `spec-gen`, `spec-reverse-gen` and `wat`. All of them used to be Pi prompt templates.

- [`/wat [focus]`](skills/wat/SKILL.md) rewrites the last assistant response as a plain-language takeaway with up to three short bullets, without continuing the task.
- [`council-review`](skills/council-review/SKILL.md) and other skills tagged **T3** in `ae` need T3 Code.
- The writing skill is [`user-facing-writing`](skills/user-facing-writing/SKILL.md). Version 4.0.0 renames `human-writing` without changing its scope: durable human-facing prose, not ordinary chat or agent-facing instructions. Install it with `ae`, then run `ae prune` to remove stale `human-writing` links.

[`skills/AGENTS.md`](skills/AGENTS.md) covers authoring and evals.

## Tools

The **Tools** tab, or `ae add -t <name>`, builds a tool with `cargo install --path` and shows build progress. You can also install by hand with `cargo install --path tools/<name> --locked`.

- [`ae`](tools/ae/README.md) is the installer itself. Installing it puts `ae` on your `PATH`.
- [`genie`](tools/genie/README.md) installs `g`, a one-shot natural-language wrapper around installed, authenticated Pi. Check `type -a g` for command/alias collisions first. Explicit requests execute immediately with your existing Pi permissions; this is not a sandbox. TTY stderr shows live activity and completed tool calls; `--quiet` hides activity only. Genie requires Pi JSON mode and prints only final assistant text after the child exits, while preserving diagnostics and using bounded cancellation cleanup. See the package README for dependencies, quoting, ignored stdin, output/status semantics, and platform/cleanup limits; zero exit does not prove task success.
- [`ghh`](tools/ghh/README.md) manages GitHub pull requests, [`gs`](tools/gs/README.md) is an enhanced Git status view, and [`gw`](tools/gw/README.md) manages Git worktrees.

## Pi resources

Pi has resources the other harnesses don't use. They're on the **Pi** tab, or available with `ae add -p <item>`, and are linked into `~/.pi/agent` (or `$PI_CODING_AGENT_DIR` / `$PI_AGENT_DIR`).

Pi's root-agent policy lives in [`harness/pi/APPEND_SYSTEM.md`](harness/pi/APPEND_SYSTEM.md). Edit this repository source, not the installed link. Selecting it links it to `APPEND_SYSTEM.md` in the Pi agent directory. The policy owns orchestration decisions; the installed `pi-subagents` skill owns invocation details.

The opt-in [`subagents` component](harness/pi/subagents/README.md) owns an execution-capable, no-source-edit reviewer and strict same-parent-model policy for native children. Setup links only `reviewer.md` into the existing `agents/` directory and merges `subagents.modelScope` into `settings.json`, with backups for changed existing targets. It preserves other settings and agents and refuses symlinked settings. The standalone `--check`/`--apply` helper requires an explicit agent directory and Python 3.8+. Project overrides and external runners need separate effective-policy checks; exceptions require user approval. No package or skill installation is included.

Pi prompt templates live in `harness/pi/commands/*.md`: the thin `flesh-out`, `idea-challenger`, `optimize-for-llm` and `skill-validate` wrappers. Each selected template is linked into `prompts/`. Root `package.json` exposes them through `pi.prompts`; edit those files directly.

Pi extensions live in `harness/pi/extensions/`. This checkout is their source of truth. Each selected extension is linked into `extensions/<name>`; none are linked automatically.

- The [`kilo-pi-provider`](harness/pi/extensions/kilo-pi-provider/README.md) extension provides Kilo AI gateway access inside Pi, including the balance display in `custom-footer`. This is a model provider inside Pi, separate from the standalone Kilo harness.
- An extension with npm dependencies (for example `openai-images`) needs `npm install` inside its directory in this checkout. `node_modules/` and extension-written runtime state are untracked.
- The repository-owned [`compaction-model`](harness/pi/extensions/compaction-model/README.md) extension routes Pi's native compaction through a dedicated model. Select it, then configure `compactionModel` in Pi's settings; no third-party extension package is needed.
- The [`prompt-stash`](harness/pi/extensions/prompt-stash/README.md) extension uses **Cmd+Shift+S** to set aside a draft and restore it after the next interactive chat submission. Your terminal must forward the Command shortcut. Drafts stay in memory and are discarded on reload, session changes, or exit.
- The [`code-search`](harness/pi/extensions/code-search/README.md) extension adds a `code_search` tool backed by jg (jevgrep) semantic search. It also sends one non-blocking nudge per prompt toward using it before `rg`/`grep`/`find`. It requires `jg` and `jg login`, and it sends the query and selected source snippets to the hosted Jevgrep service. Subagents get it only when their tool allowlists include it; see its README.
- The experimental [`entire-graph`](harness/pi/extensions/entire-graph/README.md) extension exposes local graph search and change-impact tools. It requires an external graph binary and remains opt-in; see its [spike results](harness/pi/extensions/entire-graph/SPIKE.md) for the measured working-tree latency.

You can also use this repository as a local Pi package, instead of linking:

```sh
pi install /absolute/path/to/this-repository
pi -e /absolute/path/to/this-repository   # one run, without changing settings
```

Pi commands are flat. Recursive command directories, project-local command ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution remain outside the `extended-commands` extension's V1 scope.

## Resource layout

- `skills/` contains skills for every harness.
- `harness/pi/APPEND_SYSTEM.md` contains Pi's root-agent policy.
- `harness/pi/commands/` contains Pi prompt templates.
- `harness/pi/docs/` contains Pi plans and runbooks. It is not a Pi package resource.
- `harness/pi/extensions/` contains Pi extensions.
- `harness/pi/subagents/` contains the owned reviewer, minimal settings overlay, installer, and review evaluation fixture. It installs as one component.
- `prompts/` contains system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is a repository-owned prompt resource. `prompts/OUTPUT_STYLE.md` is a Claude Code output style; link it with `ae add -c output-style`, then set `"outputStyle": "Agentic Engineering"` in each Claude Code home's `settings.json`.
- `skill-factory/` contains skill authoring, validation, and evaluation resources.
- `tools/ae/`, `tools/genie/` (binary `g`), `tools/ghh/`, `tools/gs/`, and `tools/gw/` are independent tool packages.
- `tests/` contains offline tests for `setup.sh` and `ae`.
