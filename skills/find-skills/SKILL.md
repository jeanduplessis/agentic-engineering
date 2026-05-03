---
name: find-skills
description: Helps Pi users discover and install Pi packages that add skills, prompt templates, extensions, or themes. Use when the user asks "how do I do X", "find a skill/package for X", "is there a package that can...", wants capability discovery, or wants to install/update/remove Pi resources.
---

# Find Skills

Find and install Pi packages. Pi packages can expose skills, prompt templates, extensions, and themes through package conventions or `package.json` `pi` metadata.

## When to use

Use this skill when the user:

- Asks how to add a capability to Pi.
- Asks to find a skill, prompt template, extension, theme, or package.
- Asks whether Pi can do a specialized task through an installable resource.
- Wants npm, git, or local-path installation guidance.
- Wants to list, update, or remove installed Pi packages.

## Pi package sources

Pi installs packages from:

- npm: `pi install npm:@scope/package@1.2.3`, `pi install npm:package`
- git: `pi install git:github.com/user/repo@v1`, `pi install git:git@github.com:user/repo`
- HTTPS/SSH URLs: `pi install https://github.com/user/repo`, `pi install ssh://git@github.com/user/repo`
- local path: `pi install /absolute/path/to/package`, `pi install ./relative/path/to/package`
- one-run trial: `pi -e npm:package`, `pi -e git:github.com/user/repo`, `pi -e ./local-package`

By default, install/remove writes global settings. Use `-l` for project settings.

## Discovery workflow

1. Clarify the desired capability, target resource type, and whether global or project install is preferred.
2. Search Pi package sources:
   - Browse the Pi package gallery: `https://pi.dev/packages`.
   - Search npm for the `pi-package` keyword plus domain terms.
   - Search trusted git sources or local package directories when the user names an owner/repo/path.
3. Inspect candidate source before recommending. Pi packages run with full system access.
4. Verify the package exposes the needed resources in `package.json` `pi` fields or conventional directories:
   - `skills/`
   - `prompts/`
   - `extensions/`
   - `themes/`
5. Prefer pinned versions/refs for reproducible installs when recommending third-party packages.
6. Present the best options with source, exposed resources, security notes, and exact Pi commands.

## Install/manage commands

```bash
pi install npm:@scope/package@1.2.3
pi install git:github.com/user/repo@v1
pi install https://github.com/user/repo
pi install /absolute/path/to/package
pi install ./relative/path/to/package

pi list
pi update
pi update --extensions
pi update --self
pi update npm:@scope/package
pi remove npm:@scope/package
```

Use project settings when the package should be shared with a repo/team:

```bash
pi install -l npm:@scope/package
pi remove -l npm:@scope/package
```

## Recommendation format

For each candidate, report:

1. Package source: npm, git, URL, or local path.
2. What it provides: skills, prompts, extensions, themes.
3. Why it matches the user's capability need.
4. Security/maintenance signal: source reputation, freshness, visible code, and whether extensions execute code.
5. Exact install or trial command.

Example:

```text
Candidate: npm:@example/pi-review-tools
Provides: skills and prompt templates for PR review workflows.
Why: matches your request for review automation in Pi.
Security: review source first; package extensions/skills can run or request powerful actions.
Try once: pi -e npm:@example/pi-review-tools
Install globally: pi install npm:@example/pi-review-tools
Install for this project: pi install -l npm:@example/pi-review-tools
```

## If no package is found

If no relevant Pi package exists:

1. Say no suitable Pi package was found.
2. Offer to help with the task directly.
3. Offer to create a local Pi skill or package if the workflow is recurring.
4. For local creation, prefer this repo's package layout: `skills/`, `commands/` exposed via `pi.prompts`, and `prompts/APPEND_SYSTEM.md` for system append text.

## Legacy note

Older ecosystems may use separate skill CLIs or galleries. Treat those as non-default migration sources. For Pi, prefer `pi install`, Pi packages, the Pi package gallery, npm `pi-package` discovery, git sources, and local paths.
