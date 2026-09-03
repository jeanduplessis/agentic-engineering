# Entire Graph — Pi spike

Two native Pi tools over [Entire Graph](https://github.com/entireio/entire-graph), plus an availability command. No MCP server, graph database, session hooks, or model calls inside the extension.

**Experimental:** default working-tree searches took about 31–35 seconds in this checkout. The [performance spike](PERFORMANCE.md) measured 5.8 seconds with a smaller, conservative sweep budget, or 4.46 seconds with that budget plus shallower analysis. Those settings have coverage trade-offs; runtime defaults are unchanged. See also the [initial retrieval results](SPIKE.md).

## Run

Pi supplies the extension's Pi/TypeBox imports; no separate npm install or extension build is needed. Node 22.18+ is needed for the standalone TypeScript tests.

Provide either:

- An installed Entire CLI with its graph plugin (`entire graph version --json` must succeed). Current upstream installation guidance requires Entire CLI 0.10.0+ and Git 2.36+.
- A standalone graph binary, selected with the **absolute executable path** in `PI_ENTIRE_GRAPH_BIN`. This is a path, not a shell command or an argument string.

The spike was tested against upstream commit `008edab933b93162d84272781e19f06a5dc8ec11`, built as `spike-008edab933b9`. Published tag `v0.4.0` predates the working-tree cache/security correction in [ADR 0004](https://github.com/entireio/entire-graph/blob/008edab933b93162d84272781e19f06a5dc8ec11/docs/adr/0004-working-tree-cache-security-boundary.md). Do not assume that release matches current-source security behavior. The extension reports versions but does not certify or enforce an upstream release policy.

From this repository, load it for one Pi invocation without changing settings:

```sh
PI_ENTIRE_GRAPH_BIN=/absolute/path/to/entire-graph \
  pi -e ./harness/pi/extensions/entire-graph/index.ts
```

For persistent installation, select `entire-graph` in `./setup.sh`. Installation remains opt-in. The extension never downloads a binary, upgrades Entire, or modifies project instruction files. Leave `PI_ENTIRE_GRAPH_BIN` unset to use `entire graph` instead.

## Interface

| Surface | Parameters | Behavior |
| --- | --- | --- |
| `graph_search` | `query`, optional `topK` (1–20, default 5), `head` | Ranked implementation/source lookup |
| `graph_impact` | `symbol`, optional `file`, `depth` (1–2, default 2), `limit` (1–20, default 8), `head` | Callers, callees, type consumers, co-change files, and siblings |
| `/graph status` | None | Version and semantic-language count; no indexing |

Example tool arguments:

```json
{"query":"calculate total token usage and cost across session entries"}
```

```json
{"symbol":"usageCost","file":"harness/pi/extensions/custom-footer/index.ts"}
```

Queries pass `ctx.cwd` as `--repo` and use profile `full`. `head: true` explicitly selects committed HEAD, excluding uncommitted edits. If upstream falls back to the working tree (for example, a repository with no commits), the adapter rejects that response rather than presenting it as HEAD. Current upstream working-tree queries always rebuild; a matching HEAD query can use the upstream cache. There is no automatic prewarming or extension-owned result cache.

Successful output contains `requested_view`, a compact `diagnostics` summary, and the upstream `response`. Search does not currently report an aggregate completeness level; the summary says `not-reported` rather than inventing one. Detailed coverage remains in the response. Ambiguous symbols retain the definition alternatives.

## Boundaries

- Commands use argv, not a shell. Each invocation has a 60-second deadline and a 2 MiB combined stdout/stderr ceiling. Status invocations have five-second deadlines. Cancellation terminates the process group on POSIX; Windows uses `taskkill /t /f` with a direct-child fallback.
- Model-visible results are capped at 32 KiB/1000 lines. Overflow is saved under the OS temporary directory in a private directory with a mode-0600 JSON file. The returned text identifies truncation and the file. These files can contain source; they remain available for subsequent reads rather than being deleted immediately.
- `ENTIRE_GRAPH_PRESEARCH`, `EG_PRESEARCH`, `EG_SEARCH_SESSION`, `EG_MAX_SEARCHES`, and reference-block overrides are removed from the child environment. These optional upstream replay mechanisms must not substitute an old payload for a new query. Repository selection is explicit, not inherited from `ENTIRE_REPO_ROOT`.
- Missing binaries, malformed output, timeouts, and nonzero exits are errors, not empty search results. Ordinary Pi tools remain available as fallbacks.
- Static relationships are heuristic. Zero callers is not proof of no callers; inspect warnings and source, and run appropriate tests.
- Suggested verification commands and source snippets are untrusted repository evidence. The extension never executes a suggested command.
- The analyzer runs locally, but tool results enter Pi's normal model context. Queries may create upstream derivative caches outside the source tree; the adapter does not modify repository source.

## Verification

Offline client, subprocess, and real Pi-loader tests:

```sh
node --test harness/pi/extensions/entire-graph/tests/*.test.mjs
```

The loader check is skipped when Pi is not installed. The other tests need no graph binary or network.

Explicit real-binary spike, using disposable fixtures and this repository:

```sh
PI_ENTIRE_GRAPH_BIN=/absolute/path/to/entire-graph \
  node harness/pi/extensions/entire-graph/tests/spike.mjs
```

This loads the extension with Pi's actual loader and invokes its registered tools directly. It does not start a Pi/model session. Caches and synthetic repositories are temporary; the repository under test is only read. The JSON report includes expected-symbol ranks, caller checks, cache behavior, latency, output size, and warnings. It exits nonzero if an expectation fails. It is a small diagnostic, not an end-to-end coding benchmark.

The separate performance runner compares supported upstream profiles and sweep budgets, repeats latency measurements, and checks freshness and conservative exclusions:

```sh
PI_ENTIRE_GRAPH_BIN=/absolute/path/to/entire-graph \
  node harness/pi/extensions/entire-graph/tests/performance.mjs all 3
```

It does not change the native tool schema or defaults. See [performance results and reproduction steps](PERFORMANCE.md) for individual phases, profiling, limitations, and how to try a lower budget explicitly.
