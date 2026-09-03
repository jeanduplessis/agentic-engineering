# Performance spike

## Finding

The largest cost is repeated filesystem safety checks, not Pi tool overhead or code parsing. Supported upstream settings reduced median working-tree search latency from **31.09 s to 5.80 s** while keeping profile `full`, or **4.46 s** with profile `fast`. Impact lookup dropped from **12.16 s to 3.78 s** (`full`) or **2.10 s** (`fast`).

This makes a bounded, explicitly lower-coverage mode plausible. It does **not** establish reliably subsecond working-tree queries, and no runtime defaults were changed in this spike.

## Measurements

Measured 2026-08-29 on macOS arm64, Node 24.14.1, Go 1.26.5, and the unmodified standalone graph binary at `008edab933b93162d84272781e19f06a5dc8ec11` (`spike-008edab933b9`). The committed repository base was `b9dacc4c6df54e2bc8e02bf95819209a1cc7bd8e`; its working tree included the extension and benchmark files. Pi 0.84.4 was used for the offline loader check.

Each timing variant ran three times, serially in round-robin order, with isolated temporary graph caches. These are min/median/max observations, **not p95 estimates or guarantees**. OS filesystem caches were not flushed. Every working-tree call reported a cache miss, including repetitions. HEAD's first call was graph-cache-cold; the next two reused its cache.

### Search

Query: `calculate total token usage and cost across session entries`. Five requested hits, 12,000-byte upstream context budget, same CLI adapter and output limits as the tools.

| Profile / view | Sweep budget | Min | Median | Max |
| --- | ---: | ---: | ---: | ---: |
| Working tree, full | Upstream default: 20,000 | 30.58 s | 31.09 s | 31.83 s |
| Working tree, fast | 20,000 | 29.32 s | 29.68 s | 30.98 s |
| Working tree, full | 1,024 | 8.80 s | 8.99 s | 9.01 s |
| Working tree, full | 256 | 6.68 s | 6.86 s | 6.86 s |
| Working tree, full | 64 | 5.65 s | 5.80 s | 6.12 s |
| Working tree, fast | 64 | 4.39 s | 4.46 s | 4.49 s |

HEAD/full took **2.84 s cold**, then **0.72 s and 0.69 s cached**. It excludes uncommitted edits and is not a substitute for the working-tree rows.

`fast` alone barely helped: it changes analysis depth, not the expensive directory checks. Reducing output size or prewarming a HEAD index would not remove those working-tree checks either.

### Impact

Symbol: `usageCost`, scoped to `harness/pi/extensions/custom-footer/index.ts`, depth 2, section limit 8.

| Profile | Sweep budget | Min | Median | Max |
| --- | ---: | ---: | ---: | ---: |
| Full | 20,000 | 12.03 s | 12.16 s | 12.18 s |
| Full | 64 | 3.75 s | 3.78 s | 3.82 s |
| Fast | 64 | 2.07 s | 2.10 s | 2.15 s |

The observed caller locations were stable across repetitions and matched between these variants. This is one symbol, not a general relation-recall benchmark.

## Where the time goes

A separate instrumented build added timers and a Go CPU profile, without changing query logic. It was used for diagnosis only; the tables above use the unmodified binary.

One full-profile search opened the source listing three times: preselection, graph construction, and query content reading. The measured listing times were **10.05, 10.09, and 10.56 seconds**, about **30.70 seconds** of a **33.29-second** profiled run.

The CPU profile attributed:

- 86.8% of sampled CPU to working-tree source listing.
- 80.6% to `gitDirExcluder.observeListedPaths`, including discovery and conservative promotion of Git-shaped directories.
- 77.6% to `openat` calls, reached largely through rooted path resolution. These percentages overlap; they must not be added.

This checkout had about 391 MiB of ignored `openai-images/node_modules`. Upstream still inspects ignored trees because a hidden `.git` pointer can name a credential-bearing directory elsewhere in the visible tree. Repository-owned ignore rules cannot safely disable that inspection.

With a budget of 64, the three source listings fell to **1.18, 1.16, and 1.18 seconds**. The pointer sweeps themselves took about **6 ms each**, but the separate whole-tree preflight still took **0.67–0.69 seconds per listing**. Parsing and relation resolution remained as well. That explains the remaining multi-second floor and why a small sweep budget alone is not a universal latency bound.

## Safety, freshness, and retrieval

`ENTIRE_GRAPH_SWEEP_DIR_BUDGET=64` is an existing upstream setting, not a patch. It caps sweep directory admissions, inspected entries, and associated path-traversal work; it is not a 64-source-file indexing limit.

On exhaustion, upstream records hidden evidence and excludes observed directories that could contain Git metadata even if it did not discover a pointer naming them. This is **conservative exclusion**, not permission to skip safety checks and read everything. `W_GITDIR_SWEEP_BUDGET` remains visible. Zero or negative values remove the budget; they are not a way to disable the sweep or make it fast.

The trade-off is real: a fixture with legitimate source in a headless Git-shaped directory was found with the default budget but omitted with 64. The lower budget can therefore reduce coverage even when it protects confidentiality. Do not label its output complete or silently enable it as an equivalent setting.

Observed checks:

- All full-profile budget variants retained the baseline's ranked locations, 372 scanned-file count, and 169 indexed-file count in the repeated query. Matching counts is not proof that every graph record is identical.
- Both budget-64 profiles found the three expected repository functions at ranks **1, 2, and 1**, and included the known `collectSessionTotals` caller.
- `fast` changed lower-ranked results and uses shallower relation analysis; these small checks do not establish full-profile equivalence.
- Both profiles observed same-size edits with restored mtimes, untracked additions, renames, deletions, and changed ignore rules. Cross-file caller checks passed.
- Hidden-pointer fixtures excluded a synthetic credential canary and reported the sweep-budget warning while retaining ordinary source. No real credentials were used.
- **37 benchmark assertions passed** across the latency, impact, quality, and fixture phases. The extension's **13 offline tests** and **127 targeted upstream tests** covering sweep/Git-directory/cache/preflight behavior also passed.

No model-backed coding comparison, Windows/Linux performance run, concurrent-mutation stress test, or broader repository sample was performed. Large ignored trees still affect preflight cost. The current 60-second adapter timeout is unchanged.

## Recommendation

1. **Short term:** offer an explicit interactive mode, rather than changing defaults silently. The measured candidate is budget 64 with `fast` search; keep `full` impact when relation depth matters. Always expose the selected profile and conservative-coverage warnings. This spike has not added that mode to the tool schema.
2. **Bound the wait separately:** an interactive mode should have a short deadline, around five seconds as an initial target. On timeout, report that no graph answer was obtained and use ordinary `rg`/`read` exploration. Do not return a partial graph as complete, switch to HEAD silently, or disguise a lexical result as graph evidence. Meeting a deadline can mean an explicit fallback, not always a graph answer.
3. **For genuinely faster full analysis:** optimize upstream rooted-path probes and investigate a reusable per-request source view, preserving containment and read-time policy checks. The three repeated listings are the next measured target. Sharing them safely requires upstream design and security review; a blind memoized listing is not an established fix.
4. **For subsecond repeated working-tree queries:** evaluate an upstream incremental analyzer with raw-content fingerprints, policy-aware invalidation, bounded state, and fresh admissibility checks. A Pi response cache, watcher-only invalidation, `git status` cleanliness test, or TTL is not sufficient. [ADR 0004](https://github.com/entireio/entire-graph/blob/008edab933b93162d84272781e19f06a5dc8ec11/docs/adr/0004-working-tree-cache-security-boundary.md) explains why current working-tree caching is disabled.

The thin Pi adapter should remain a client of those capabilities, not grow its own competing code index.

## Reproduce

The runner does not upgrade the installed CLI, install dependencies, activate the extension globally, or edit this repository. Use the reviewed standalone binary:

```sh
OUT=$(mktemp -d)
PI_ENTIRE_GRAPH_BIN=/absolute/path/to/entire-graph \
  node harness/pi/extensions/entire-graph/tests/performance.mjs all 3 > "$OUT/results.json"
```

Phases can run separately: `latency`, `impact`, `quality`, or `fixtures`. The repetition argument applies only to timing phases. Allow several minutes for the default-budget variants. The runner invokes the adapter directly and substitutes the supported CLI profile flag in its test-only subprocess boundary; `fast` is **not yet a native tool parameter**. It preserves subprocess cancellation and output bounds, cleans up fixtures and caches, and exits nonzero on failed expectations.

To try just the lower budget with the current native tools, retaining profile `full` and accepting conservative exclusions:

```sh
ENTIRE_GRAPH_SWEEP_DIR_BUDGET=64 \
PI_ENTIRE_GRAPH_BIN=/absolute/path/to/entire-graph \
  pi -e ./harness/pi/extensions/entire-graph/index.ts
```

For CPU/stage profiling, `tests/performance-profile.patch` adds instrumentation to the pinned upstream source. Its upstream context is covered by the [third-party license notice](THIRD_PARTY_NOTICES.md). Apply it only to a disposable export of that exact commit, not an installed binary or this repository:

```sh
# From this repository; UPSTREAM points to an existing local Entire Graph clone.
EXT="$PWD/harness/pi/extensions/entire-graph"
WORK=$(mktemp -d)
mkdir "$WORK/source"
git -C "$UPSTREAM" archive 008edab933b93162d84272781e19f06a5dc8ec11 | tar -xf - -C "$WORK/source"
(
  cd "$WORK/source"
  git apply --check "$EXT/tests/performance-profile.patch"
  git apply "$EXT/tests/performance-profile.patch"
  GOPROXY=off GOSUMDB=off go build -mod=readonly \
    -ldflags '-X main.version=spike-008edab933b9' -o "$WORK/graph-profile" ./cmd/entire-graph
)
GRAPH_SPIKE_TIMING=1 GRAPH_SPIKE_CPU_PROFILE="$WORK/cpu.out" \
ENTIRE_PLUGIN_DATA_DIR="$WORK/cache" \
  "$WORK/graph-profile" search --repo "$PWD" --profile full \
  --query 'calculate total token usage and cost across session entries' \
  --format json --top-k 5 --max-context-bytes 12000 \
  > "$WORK/result.json" 2> "$WORK/stages.log"
go tool pprof -top -cum "$WORK/graph-profile" "$WORK/cpu.out"
```

The offline build needs its Go modules already cached; it deliberately fails rather than downloading them. The profiling environment variables are for the instrumented binary only. Unset `ENTIRE_GRAPH_SWEEP_DIR_BUDGET` for the default-budget profile, or set it explicitly to compare budgets. Results and profiles may contain source paths or snippets; keep them private. The instrumentation does not change the analyzer's safety or cache policy.

Local raw reports for this run are in ignored `.firecrawl/entire-graph-performance-{latency,impact,quality,fixtures}.json`. They are not shipped with the repository; this document is the durable measurement summary.
