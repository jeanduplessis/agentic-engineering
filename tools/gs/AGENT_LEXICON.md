# Agent Lexicon

## Canonical Terms

| Term | Agent meaning | Use this when | Avoid |
|---|---|---|---|
| **`gs`** | The Rust CLI binary/package that prints the enhanced Git status view. | Naming the command, package, executable, docs, tasks, and user-facing CLI behavior. | `git-smart-status`, `git smart-status`, smart status CLI, custom status CLI |
| **Enhanced status view** | The read-only output produced by `gs`: one-space left buffer, repository context framed by border lines, and grouped file-change sections with per-entry stats. | Referring to the product output as a whole. | git status replacement, richer status, smart status, dashboard |
| **Read-only CLI** | A CLI that inspects repository state and never stages, unstages, discards, commits, or prompts for interactive actions. | Defining scope, safety, UX, and tests. | interactive CLI, Git workflow tool, staging tool |
| **Git library backend** | Repository data collection through Rust Git/libgit2 bindings, not subprocess calls to the installed `git` binary. | Describing implementation constraints for status/diff/branch data. | shelling out, Git CLI backend, `git status` parser |
| **Library-plus-thin-binary** | Architecture where reusable core modules implement behavior and the binary only handles CLI parsing, IO, and exits. | Structuring implementation tasks and tests. | single binary crate, workspace split, monolith |
| **Repository inspector** | Module responsibility that opens the repo and reads branch, upstream, latest commit, status, ignore-aware changes, and parent-level submodule changes. | Naming repository state collection responsibilities. | Git parser, status reader, repo scanner |
| **Change model** | Normalized domain representation of branch state, latest commit, sections, entries, symbols, paths, and stats. | Passing repository data to rendering/tests. | raw status, output rows, view model unless specifically rendering-only |
| **Diff/stat calculator** | Module responsibility that computes known `+N/-N` stats or unknown `+?/-?` stats for staged, tracked, and untracked entries. | Naming line-stat behavior. | line counter, diff parser, numstat clone |
| **Renderer** | Module responsibility that converts the change model into plain or colored terminal text. | Naming layout, color, alignment, and snapshot behavior. | printer, formatter, UI unless terminal UI is introduced |
| **Branch header** | Repository context line showing `Branch: branch ↑ahead ↓behind`, always including counts even when `0`, or `detached @ <short-sha>`. | Referring to branch context above the Latest commit line and Sections. | branch summary, status header, title line |
| **Branch commit stats** | Ahead/behind counts in the Branch header, rendered `↑N ↓N` and aligned with Entry stats. | Discussing branch ahead/behind count layout or styling. | remote counts, sync status, tracking summary |
| **Latest commit line** | Optional repository context line rendered as `Commit: <short-hash> <subject>` below the Branch header for the commit at `HEAD`; omitted for an unborn branch. | Referring to the current `HEAD` commit hash and subject in the Enhanced status view. | commit header, log line, latest change |
| **Upstream divergence** | Ahead/behind counts between the current branch and its configured upstream. | Describing `↑N ↓N` in the branch header. | remote counts, sync status, tracking summary |
| **Detached HEAD** | Repository state rendered in the branch header as `detached @ <short-sha>`. | Handling non-branch HEAD output. | detached branch, anonymous branch |
| **Border line** | Horizontal `─` line rendered above the Branch header and below the optional Latest commit line, sized to the widest rendered plain line and muted gray in colored output. | Discussing the visual frame around repository context. | divider, separator, rule unless generic |
| **Section** | One visible grouped change category: `Staged`, `Tracked`, or `Untracked`. | Discussing grouping, counts, colors, ordering, and visibility. | group, bucket, category |
| **Staged section** | Section containing index changes that are commit-ready; heading is plain, entries are green in colored output. | Referring to staged/index entries and green entry styling. | cached section, index section, staged files when meaning entries |
| **Tracked section** | Section containing unstaged worktree changes to tracked files; heading is plain, entries are tan in colored output. | Referring only to unstaged tracked-file changes and tan entry styling. | modified section, changed section, unstaged section |
| **Untracked section** | Section containing untracked, non-ignored files; heading is plain, entries are muted gray in colored output. | Referring to new untracked files and muted gray entry styling. | new files section, unknown files, unversioned section |
| **Entry** | One rendered file-change row inside a section. | Discussing status symbol, display path, stats, sorting, and section counts. | file unless the file itself is meant, row unless rendering-only |
| **Section count** | Number of entries in a section shown in the section header, e.g. `Staged (2)`. | Defining section header content. | line total, diff total, file count when entries can duplicate a partially staged path |
| **Git-letter status symbol** | One of `M`, `A`, `D`, `R`, or `?` rendered before an entry path. | Referring to compact status markers. | icons, badges, status words, glyphs |
| **Repository-root-relative path** | File path displayed and sorted relative to the repository root regardless of invocation directory. | Defining path display and sort behavior. | current-directory-relative path, absolute path, Git-relative path |
| **Display path** | The path string shown for an entry; for renames, `old/path -> new/path`. | Discussing sorting, alignment, and rendering. | filepath when rename representation matters |
| **Rename display** | The `old/path -> new/path` display path for renamed entries, sorted by destination path. | Handling renamed files in output and tests. | destination-only path, renamed badge |
| **Partially staged file** | A path with both staged index changes and unstaged tracked worktree changes. | Requiring duplicate entries across `Staged` and `Tracked` with separate stats. | mixed file, partially indexed file, combined staged file |
| **Entry stats** | Per-entry changed-line indicator rendered as known `+N/-N` or unknown `+?/-?`, with `/` separators vertically aligned across entries. | Referring to stats shown at the aligned end of each entry row. | line count, diff count, numstat unless backend-specific |
| **Stats separator** | The `/` between additions/deletions inside Entry stats; vertically aligned and muted gray in colored output. | Discussing alignment or styling of the separator in `+N/-N` or `+?/-?`. | slash unless meaning generic punctuation |
| **Known text stats** | Entry stats with concrete additions/deletions for text changes, rendered `+N/-N`. | Describing text diff output. | changed lines when deletion/addition split matters |
| **Unknown stats** | Entry stats for binary or otherwise unknown line changes, rendered `+?/-?`. | Handling binary, submodule, or non-line-oriented changes. | binary, no stats, `+0/-0` |
| **Clean repository output** | Output with the Branch header and optional Latest commit line framed by Border lines, followed by `✓ working tree clean` when no sections contain entries. | Defining no-change behavior. | no output, clean message only |
| **Left buffer** | One leading space added to every non-blank output line. | Discussing output indentation at the terminal edge. | margin unless referring to general layout |
| **Color mode** | CLI option `--color=auto|always|never`, defaulting to `auto`. | Controlling ANSI output. | theme, palette option, color flag unless discussing parsing |
| **Deterministic ANSI 256-color styling** | Fixed terminal colors: branch names, ahead counts, additions, and staged entries green (`38;5;2`); behind counts and deletions red (`38;5;1`); Latest commit line and Detached HEAD hashes plus tracked entries tan (`38;5;180`); stats separator and border line muted gray (`38;5;244`); untracked entries muted gray (`38;5;245`); labels, commit subjects, and section headings stay plain. | Defining color contract and color snapshot expectations. | truecolor, basic ANSI only, custom theme |
| **Ignored file exclusion** | Rule that ignored files never appear in normal output. | Handling `.gitignore`/ignore-rule behavior. | ignored section, show ignored, muted ignored files |
| **Submodule path-level change** | A parent-repository-visible submodule path change without inspecting inside the submodule. | Handling submodules. | recursive submodule status, submodule internals |
| **Temporary Git repository test** | Integration test that creates an isolated Git repository and asserts observable `gs` behavior. | Testing repository behavior. | mocked Git test, unit-only status test |
| **Rendered output snapshot** | Assertion over user-visible terminal text, including layout and optionally forced color. | Testing renderer contracts. | implementation snapshot, internal model snapshot |
| **End-user README** | `README.md` focused on installing, running, understanding output, colors, and errors for `gs`. | Editing top-level docs for users. | architecture spec, implementation notes, internal design doc |
| **Local Cargo install** | Installing `gs` from this checkout with `cargo install --path .`, reinstalling with `--force`, and uninstalling with `cargo uninstall gs`. | Documenting local installation and updates. | package distribution, Homebrew install unless added later |
| **PRD epic** | Closed beads epic containing the approved product requirements for `gs`; current epic ID is `gs-y9o`. | Referencing initial product scope or historical source context. | GitHub issue, active task spec |

## Agent Rules

- Use **`gs`** for the CLI name; do not introduce alternate command names unless updating this lexicon first.
- Use **Enhanced status view** for the whole product output; do not call it a dashboard or interactive tool.
- Use **Read-only CLI** only when no Git-mutating action is available or planned in scope.
- Use **Git library backend** for implementation plans; do not shell out to `git` for status or diff data.
- Use **Tracked section** only for unstaged worktree changes to tracked files; do not use it for all Git-tracked files.
- Use **Entry** for a rendered section row; use file/path only when not discussing duplicated partially staged entries.
- Use **Section count** for entry counts only; do not aggregate line totals in section headers.
- Use **Repository-root-relative path** for path display and sorting; do not vary output by current working directory.
- Render the **Left buffer** on every non-blank output line.
- Use **Display path** when rename formatting can change the path string.
- Render **Partially staged file** as two entries: one in **Staged section**, one in **Tracked section**, with separate **Entry stats**.
- Render untracked text files as **Known text stats** with all lines added: `+N/-0`.
- Render binary or non-line-oriented changes as **Unknown stats**: `+?/-?`; do not render `binary` or `+0/-0`.
- Always render **Branch commit stats** for branches, including zero counts.
- Render the **Latest commit line** below the **Branch header** using the commit's short hash and first message line as its subject; omit it for an unborn branch.
- Align **Branch commit stats** with **Entry stats** when sections are visible.
- Vertically align the **Stats separator** across visible **Entry** rows.
- Render **Rename display** as `old/path -> new/path` and sort by destination path.
- Render **Border line** values above the **Branch header** and below the optional **Latest commit line** for both sectioned output and **Clean repository output**.
- Hide empty **Section** values; use **Clean repository output** only when no sections contain entries.
- Use **Color mode** exactly as `--color=auto|always|never`, default `auto`.
- Use **Deterministic ANSI 256-color styling**; do not add theming or truecolor requirements.
- Keep **Section** headings plain in colored output; color entries only.
- Enforce **Ignored file exclusion**; do not add ignored-file output unless explicitly changing product scope.
- Treat submodules as **Submodule path-level change** only; do not inspect submodule internals.
- Keep the **End-user README** focused on **Local Cargo install**, usage, output, colors, and errors.
- Use **Temporary Git repository test** for repository behavior and **Rendered output snapshot** for layout/color behavior.
- Reference **PRD epic** `gs-y9o` when historical product scope matters.

## Relationships

- **`gs`** prints one **Enhanced status view** for the current repository.
- **Enhanced status view** contains a **Left buffer**, one **Branch header**, an optional **Latest commit line**, **Border line** values, and zero or more visible **Section** values.
- **Border line** values frame the **Branch header** and optional **Latest commit line** in both sectioned output and **Clean repository output**.
- A **Section** contains zero or more **Entry** values; empty sections are hidden.
- An **Entry** contains one **Git-letter status symbol**, one **Display path**, and one **Entry stats** value.
- **Entry stats** are either **Known text stats** or **Unknown stats** and contain one **Stats separator**.
- A **Partially staged file** produces one **Staged section** entry and one **Tracked section** entry.
- **Rename display** is a kind of **Display path**.
- **Branch commit stats** are rendered inside the **Branch header** and represent **Upstream divergence**.
- **Latest commit line** describes the commit at `HEAD` and appears below the **Branch header** when `HEAD` resolves to a commit.
- **Repository inspector**, **Change model**, **Diff/stat calculator**, and **Renderer** live behind the **Library-plus-thin-binary** architecture.
- **Temporary Git repository test** validates repository behavior; **Rendered output snapshot** validates renderer behavior.
- **End-user README** documents **Local Cargo install** and everyday `gs` usage.
- **PRD epic** `gs-y9o` is the closed parent/source for initial implementation context.

## Ambiguities

| Ambiguous term | Problem | Canonical decision |
|---|---|---|
| status | Can mean standard `git status`, internal status flags, or product output. | Use **Enhanced status view** for product output and **Git-letter status symbol** for entry markers. |
| tracked | Can mean any Git-tracked file or only unstaged tracked changes. | Use **Tracked section** only for unstaged worktree changes to tracked files. |
| file count | Partially staged files can appear twice, so file count may differ from rendered rows. | Use **Section count** for rendered entry count. |
| filepath | Renames need `old -> new`, not a single path. | Use **Display path** when rendering/sorting output rows. |
| changed lines | Can imply total changes or split additions/deletions. | Use **Entry stats**, **Known text stats**, or **Unknown stats**. |
| binary | Can describe file type, diff handling, or output string. | Use **Unknown stats** for rendered binary/unknown line changes. |
| branch summary | Could include verbose prose or labels. | Use **Branch header** with `Branch: branch ↑ahead ↓behind` format. |
| latest commit | Could mean configured upstream tip, newest repository commit, or current `HEAD`. | Use **Latest commit line** for the commit at `HEAD`. |
| commit subject | Could mean the first line, full summary paragraph, or complete commit message. | Use the first commit-message line in the **Latest commit line**. |
| clean | Could mean no output, no file changes, or no branch divergence. | Use **Clean repository output** when no sections contain entries; branch header and optional Latest commit line still render. |
| color | Could mean theme, auto-detection, or exact palette. | Use **Color mode** for CLI behavior and **Deterministic ANSI 256-color styling** for palette. |
| separator | Could mean the stats separator or the lines framing repository context. | Use **Stats separator** for `/`; use **Border line** for the horizontal lines around the Branch header and optional Latest commit line. |
| slash | Could mean punctuation, path separator, or stats separator. | Use **Stats separator** for the `/` in Entry stats; Branch commit stats use a space, not `/`. |
| submodule changes | Could include recursive child repo status or parent pointer changes. | Use **Submodule path-level change** only. |
| tests | Could mean unit, integration, snapshot, or mocked tests. | Use **Temporary Git repository test** for Git behavior and **Rendered output snapshot** for renderer output. |
