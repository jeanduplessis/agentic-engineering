# Initial spike results

Follow-up: [the performance spike](PERFORMANCE.md) isolates repeated filesystem checks and compares supported tuning options. The measurements below remain the original baseline.

Measured 2026-08-29 on macOS arm64, Node 24.14.1, Pi 0.84.4, and a standalone Entire Graph build at `008edab933b93162d84272781e19f06a5dc8ec11` (`spike-008edab933b9`). The repository's committed base was `b9dacc4c6df54e2bc8e02bf95819209a1cc7bd8e`; working-tree queries also included the uncommitted spike implementation and tests.

The installed Entire CLI remained at 0.9.0. No plugin installation, global extension activation, source commits, or model-backed evaluation was performed.

## Method

`tests/spike.mjs` loaded this extension through Pi's actual loader and invoked the registered tools. It used four small TypeScript fixture files in a disposable Git repository, then queried this repository. All queries used profile `full`; search requested five ranked results and a 12,000-byte upstream context budget. Each sample below is one invocation, not a latency percentile or a statistically powered benchmark.

The three repository queries and expected symbols were declared before the first run. No prompt tuning was needed to obtain these results. This checks retrieval and integration, not whether a model chooses the tool correctly or finishes coding tasks more reliably.

## Results

All **10 real-tool checks passed**.

| Check | Result | Elapsed |
| --- | --- | ---: |
| Fixture: find invoice-total calculation including tax | `calculateInvoiceTotal` ranked first | 338 ms |
| Fixture: callers of invoice-total calculation | Both known callers found, including cross-file import | 122 ms |
| Fixture: ambiguous symbol | Two definitions returned; disambiguation required | 122 ms |
| Fixture: newly added, uncommitted function | New function found immediately | 319 ms |
| Find where selected Pi extensions are linked | `install_pi_extensions`, rank 1 | 35.18 s |
| Find token/cost aggregation across session entries | `collectSessionTotals`, rank 2; `usageCost` ranked first | 34.49 s |
| Find dedicated-model compaction with fallback | `registerCompactionModel`, rank 1 | 35.35 s |
| Repository: callers of `usageCost` | Known caller `collectSessionTotals` included | 13.38 s |
| Repeated committed-HEAD search | Same ranked locations; second call hit the cache | 3.32 s first, 0.87 s repeated |
| Working-tree search after HEAD cache was populated | Cache bypassed, as required | 34.54 s |

The `install_pi_extensions` result above predates the setup refactor. Current setup selects and links extensions within `install_pi_harness`; the runnable spike fixtures now target that function. The table remains the original measurement record.

The repository search responses were 15.0–16.9 KiB as returned to Pi; none of these cases needed the adapter's overflow file. These are byte measurements, not token-cost measurements.

## Performance investigation

The live checkout reported `W_GITDIR_SWEEP_BUDGET`: upstream's scan for Git-directory pointers reached its 20,000-directory/entry or path-traversal allowance under ignored/collapsed roots. The warning says some structurally Git-like directories were excluded without a discovered pointer; their source is absent. Zero parser failures does not erase that warning.

A separate repeat of the token/cost query compared the live checkout with an export of tracked HEAD source into a new, empty Git repository:

| View | Total | Preselection | Index | Query | Candidate files scanned |
| --- | ---: | ---: | ---: | ---: | ---: |
| Live checkout | 34.05 s | 10.65 s | 12.79 s | 10.60 s | 367 |
| Tracked-source export | 3.01 s | 0.33 s | 2.36 s | 0.31 s | 361 |

The top five locations were the same, and the export had no sweep-budget warning. This points toward checkout traversal/metadata overhead as a substantial contributor. It does **not** isolate one cause: the export also omitted ignored dependencies, Git history, and the uncommitted spike files. No security checks or traversal limits were disabled to obtain the faster result.

## Verification and limits

- **13 offline tests passed:** argv/environment handling, error paths, explicit-HEAD provenance, output/line limits, diagnostic preservation, private overflow files, terminal-control escaping, timeout/cancellation, POSIX descendant termination, and real Pi extension loading.
- Strict TypeScript checking passed against the installed Pi/TypeBox declarations using TypeScript 5.9.3. The repository's 99 Python tests also passed.
- Final registered-tool checks with the pinned binary passed for working-tree search, caller lookup, rejection of an unborn repository's HEAD fallback, and a real committed-HEAD query. Windows process handling and interactive TUI behavior were not exercised.
- No end-to-end agent adoption, coding-success rate, model-token savings, broad language coverage, or large-monorepo performance claims follow from this sample.
- Raw local reports from this run are in the ignored `.firecrawl/entire-graph-spike-results.json` and `.firecrawl/entire-graph-spike-timings.json`. The table above is the durable summary, not a claim that those local files ship with the repository.

## Recommendation

Keep the extension opt-in. The CLI adapter works and the initial retrieval results are useful, but roughly 35 seconds per working-tree search is too expensive to make it a default replacement for ordinary exploration in this checkout. Explicit HEAD queries look more practical for committed-code review, provided the user accepts that uncommitted edits are excluded.

The next investigation should target upstream working-tree traversal cost, without relaxing its security boundary. A small, separately approved model-backed comparison would then be needed to establish whether the tools improve actual Pi coding work.
