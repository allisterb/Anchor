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
- **Strands readiness is per-edge and OR by default, and the first model of it was wrong.** See
  below — the correction is in, and it turns HP10 from a tautology into a real obligation.

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

## Conditional edges

### The readiness rule was wrong, and is now fixed

`Graph._is_node_ready_with_conditions` returns `True` on the **first** incoming edge whose source is
in the completed batch and whose condition passes. `GraphNode.dependencies` — which the translator
used to emit as an AND-set — is used only to find entry points and gather node inputs, and never
gates execution. The SDK docs state it outright: *"In Python, the default behavior is OR semantics —
a target node fires when any incoming edge's source completes."*

Modelling it as AND described a stricter orchestrator than the one that runs, which is the unsound
direction. `DependencyDAG.tla` now takes the OR rule, and `Workflow.tla` emits four definitions
instead of two:

| | |
|---|---|
| `Tasks` | the nodes |
| `Edges` | `<<from, to>>` pairs. The parent set HP10 quantifies over is *derived* from this, so the two cannot disagree |
| `EdgeCond(from, to, st)` | each edge's traversal condition. State is a parameter because `Workflow` is EXTENDed by the module declaring `VARIABLE state` |
| `EdgeSupport(from, to)` | the tasks a condition reads, so `EdgeDead` can tell a false condition that may yet flip from one that cannot |

**HP10 is no longer a tautology.** Under the old AND gate it restated `Unblock` and could not fail.
Under OR it is a real obligation that holds only if every join carries a condition strong enough to
enforce it. The checked-in `Workflow.tla` guards its join and verifies; `graph_to_tla.py` builds two
unguarded graphs from the live SDK — the docs' own four-node example and an `A→B, B→C, A→C` skew —
and both violate HP10 with the counterexample the SDK's own execution order predicts.

**Failure propagation narrowed with it.** A failed parent no longer strands its children on its own,
because another edge may still admit them. Only a task with no surviving edge is an orphan.

### Known gap: re-execution

Strands admits a node once per satisfied incoming edge, so on the skew shape `execution_order`
contains C **twice**. `COMPLETED` is terminal in `DependencyDAG.tla`, so the second run is outside
the model. Same OR rule, second symptom; it needs its own spec. Note the interleaving varies between
runs (the batch is concurrent) — the repeat does not, so assert on the repeat.

### Next: the condition vocabulary

Design settled with the project owner. Annotations, but bound to the **condition object** rather
than to a source comment: a comment binds by line adjacency, is invisible to the runtime, and needs
a parser to read — which is the thing being avoided.

Three tiers, all reported in the generator's output:

0. **Anchor combinators** (`all_complete`, `any_complete`, `none_failed`). A real Python condition
   that carries its own TLA+ meaning. Meaning is construction, not assertion; reviewed and
   differentially tested once rather than per workflow. Covers `all_dependencies_complete`, which is
   what the docs tell every user to write.
1. **`@anchor.condition_schema`** on a condition *factory*. It leaves the Python untouched and
   stamps `__anchor__` on each closure the factory produces, capturing the per-call-site arguments —
   necessary because the docs pattern is a factory, so the arguments, not the function, are what
   differ per edge. The predicate is a user assumption: emit it into the generated module, count it,
   pin the count, exactly as `AuditAsync` treats `{:extern}`.
2. **Unannotated** → nondeterministic edge. Sound, weak, counted.

`to_tla` currently **refuses** a graph with an untranslated condition rather than emitting `TRUE`.
`TRUE` would model an edge that always fires and so hide a condition that never fires and strands
its target; nondeterminism is the honest translation and it needs tier 2.

Two constraints to keep: the predicate must stay inside the spec's vocabulary (`status`, `Edges`,
`Tasks`), and a condition reading `state.results[...]` text or the `invocation_state` dict that
`EdgeConditionWithContext` passes gets `nondet`, never a fudged predicate.

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
