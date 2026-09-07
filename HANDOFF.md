# Handoff

State of the work as of 2026-09-07. Living document — update it rather than adding dated copies.

## Where things stand

**Milestone 1 (toolchains work) is done.** Both verifiers run in-process where possible, and the
build fetches and hash-verifies everything they need on Windows and Linux.

**Milestone 2 (verify a real workflow) is well under way.** The base idea is demonstrated end to
end: a verified Dafny workflow translated to Python and executed against a real module across an
`{:extern}` boundary, plus TLA+ models of the multi-agent cases Dafny structurally cannot reach.

30 tests, all green. `./build.sh -t` or `./build.ps1 -Test`.

## Layout

| | |
|---|---|
| `src/Anchor.Verifiers.Dafny` | parse, resolve, verify, **audit**, **translate to Python** — all in-process |
| `src/Anchor.Verifiers.TLAPlus` | SANY in-process via IKVM; TLC out-of-process via `TLCProcess` |
| `specs/` | one directory per subject, each pairing a spec that verifies with variants carrying one deliberate mistake |
| `tests/strands/` | informal Python against the real SDK: the differential test, the graph translator, the budget experiment |
| `requirements/` | Python deps, pinned and hash-locked, installed by hand |

## What is actually established

- **Dafny → Python runs.** `BoundedRetryExtern.dfy` verifies, translates, and executes against
  `anchor_model.py`. Dafny emits the `import` itself, contrary to what its reference manual says.
- **`DafnyProgram.AuditAsync` enumerates the trust boundary** — every point a proof rests on an
  assumption. For the extern workflow it reports exactly two, both on `Attempt`, and a test pins
  the count so it cannot silently grow.
- **TLA+ earns its place only on the multi-agent cases.** On `BoundedRetry` the two tools agree and
  Dafny alone would have caught both bugs. `SharedBudget` is where they part: a check-then-reserve
  race that no loop invariant can express.
- **The Cedar model is differential-tested against the real engine** — 60 requests, exhaustive over
  the domain, and a mutation of `Decide` is caught.
- **A Strands `Graph` translates mechanically to TLA+.** `GraphBuilder` is a construction API, so
  the graph *is* the workflow; walking it is translation rather than paraphrase.

## Findings worth not re-deriving

**On the toolchain**

- TLC cannot run in-process under IKVM. Every run builds an `FPSet`, which extends
  `UnicastRemoteObject`, and IKVM's RMI export check rejects `FPSetRMI.put` for declaring
  `IOException` rather than `RemoteException` — legal on a real JVM. No flag avoids it.
- `DafnyOptions` defaults `Printer` to `NullPrinter`; only the CLI replaces it. Without
  `DafnyConsolePrinter` verification outcomes come back correct but with no text.
- Dafny 4.11.0's "Z3 not found" path NREs when options are built in-process, because it reports on
  `DafnyProject.StartingToken` and only the CLI populates that.
- z3 must be pinned **per platform**; solver-builds ships a different binary per OS.

**On the SDK**

- `result.metrics.accumulated_usage` is the running total across an agent's invocations, not the
  cost of the last call. The per-call figure is `metrics.agent_invocations[-1].usage`. Charging the
  former compounds silently.
- Cedar's `resource` is hardcoded to `Resource::"agent"` on every request. Resource-scoped policies
  are unreachable through that handler, and tool-chain escalation is therefore outside what Cedar
  can see there.
- The Cedar rate limiter is safe only because `before_tool_call` is synchronous — there is not one
  `await` in the file — while tool execution is concurrent by default. Add any await and the limit
  silently admits more calls. Nothing documents or enforces this.

**On the paper (arXiv:2510.14133)**

Three of four checked properties turned something up. TL1 holds only given a retry bound it leaves
implicit; TL4 as published forbids cancelling a dispatching task; HP10 is not independent of TL1,
because satisfying it creates an obligation to cancel orphaned subgraphs that Table 1 never states.
TL3 was correct and caught a modelling error of ours.

## Next: conditional edges

`GraphEdge` carries an optional `condition` that decides traversal at runtime. `graph_to_tla.py`
translates topology only and ignores it, which is the main gap in the translation story.

Two approaches, and the project owner has an idea to discuss before picking:

1. **Model conditions as nondeterminism** — an edge may or may not be taken. Sound, requires no
   translation of predicates, and proves properties that hold whatever the condition decides. Weaker
   but cheap and unfalsifiable-by-mistranslation.
2. **Translate the predicate** — stronger, and the same trap as the Cedar condition language: a
   hand-written translator that can silently disagree. Would need the same differential treatment,
   which is affordable now that agents run in milliseconds against a scripted model.

## House rules that have earned their keep

- **Never commit automatically.** Prompt instead.
- **Never install packages automatically.** Python deps go through
  `requirements.in` → `uv pip compile --generate-hashes` → `install.cmd`.
- **Write scripts to files rather than piping quoted strings through shells.** Bash → PowerShell →
  WSL → bash is three escaping layers and it has mangled things repeatedly. Check line endings
  before running, and audit every destructive verb.
- **Mutate the fixture to prove a test is sensitive.** Every "this must fail" test here has been
  checked by breaking the thing it guards and confirming it notices.
- **Do not assert on a specific counterexample.** TLC reports whichever it reaches first; two
  assertions here were flaky until they described the shape instead of an instance.

## Uncommitted at handoff

```
 M specs/DependencyDAG/Bug5_NoFailurePropagation.tla   split the DAG out into Workflow.tla
 M specs/DependencyDAG/DependencyDAG.tla               now EXTENDS Workflow
 M tests/strands/README.md                             documents the graph translator
?? specs/DependencyDAG/Workflow.tla                    the hand-written example DAG
?? tests/strands/graph_to_tla.py                       Strands Graph -> TLA+
```
