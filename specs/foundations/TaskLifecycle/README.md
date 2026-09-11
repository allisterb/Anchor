# TaskLifecycle

**One sub-task, in full.** The eleven-state lifecycle from Table 2 of Allegrini, Shreekumar & Celik,
*Formalizing the Safety, Security, and Functional Properties of Agentic AI Systems*
(arXiv:2510.14133v2) — dependency waiting, dispatch, retry, fallback and cancellation — with the
paper's properties TL1–TL14 checked over it.

The paper states those properties in CTL and **never checks them**; its own conclusion defers that to
future work. This is that check, and running it turned up two things.

| file | what it is |
|---|---|
| `TaskLifecycle.tla` | the lifecycle and TL1–TL14. Twelve properties checked, all hold. |
| `TaskLifecycle_TL4Published.cfg` | TL4 *exactly as the paper publishes it*. **Expected to fail.** |
| `Bug4_UnboundedRetry.tla` | the same with the retry budget removed. TL1 fails as a lasso. |

New to TLA+? [`specs/strands/DependencyDAG/README.md`](../../strands/DependencyDAG/README.md) has a notation primer.

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config specs/foundations/TaskLifecycle/TaskLifecycle.cfg specs/foundations/TaskLifecycle/TaskLifecycle.tla
```

## The state

```tla
States ==
    { "CREATED", "READY", "AWAITING_DEPENDENCY", "DISPATCHING", "IN_PROGRESS",
      "COMPLETED", "FAILED", "RETRY_SCHEDULED", "FALLBACK_SELECTED", "ERROR", "CANCELED" }

Terminal == { "COMPLETED", "ERROR", "CANCELED" }
```

Two counters bound the loops — `retries` against `MaxRetries`, `fallbacks` against `MaxFallbacks` —
and `prev` carries the previous state, which several properties are stated over.

This is **one** sub-task in detail. [`DependencyDAG`](../../strands/DependencyDAG) is the complementary model:
several tasks in outline, because HP10 is about the relation *between* tasks rather than the states
within one. Composing the two is a separate exercise; this model would not fit in a checkable state
space if each task in a DAG carried all eleven states.

## Translating CTL to TLA+

The paper's properties are in CTL, which is a different logic from TLA+'s. The mapping:

| CTL | TLA+ | |
|---|---|---|
| `AG P` | `[]P` | always |
| `AF P` | `<>P` | eventually |
| `AX P` | `[][P]_vars` | in every next state |
| `EF P` | **no equivalent** | |

`EF` — "there exists a path on which P eventually holds" — has no TLA+ form, because TLA+ is
linear-time and has no existential path quantifier. The paper's two reachability properties (HP15,
HP16) are therefore not translated. The equivalent technique is to check `[]~P` and read TLC's
violation trace as the witness.

**TL7, TL8 and TL10 are stated over "the previous state"**, so the model carries `prev` explicitly.
That is a real cost of the paper's phrasing: history ends up in the state space, doubling it, where
properties phrased over *actions* would not have needed it.

## What checking found

### TL4 as published forbids cancelling a dispatching task

> **TL4**: A sub-task in DISPATCHING eventually reaches the IN_PROGRESS state.
> `AG(state = DISPATCHING → AF(state = IN_PROGRESS))`

Read literally, once a task is DISPATCHING it *must* reach IN_PROGRESS — so no cancellation, timeout
or shutdown may intervene. TLC finds the counterexample in two steps: `Dispatch`, `Cancel`.

That is not a constraint any real framework satisfies. Strands exposes `agent.cancel()` and a
`cancel_signal` precisely so in-flight work can be abandoned. The same objection applies to TL2.

So the spec carries **both**: `TL4_AsPublished`, checked by its own `.cfg` and expected to fail, and
a weakened `TL4` admitting `CANCELED`, which holds. The divergence from the paper is deliberate,
recorded, and *checked* — kept as a live artifact so the finding cannot rot into a stale comment.

### TL1 is a constraint on the retry policy, not a property of the lifecycle

> **TL1**: Every CREATED sub-task eventually terminates in COMPLETED, ERROR, or CANCELED.

TL14 says a RETRY_SCHEDULED task dispatches "if the retry policy permits", and **nothing in Table 2
says a retry policy must be bounded**. `Bug4_UnboundedRetry.tla` takes that at its word, and TL1
fails as a lasso:

```
FAILED → RETRY_SCHEDULED → DISPATCHING → IN_PROGRESS → FAILED → ...
```

forever. So TL1 holds only given a bound the paper leaves implicit.

That is the same shape as `Bug2_FreeRetry` in [`BoundedRetry`](../BoundedRetry): termination rests on
every pass through the loop consuming something finite. Two different models, two different papers'
worth of framing, one underlying requirement.

### One error of ours, caught the same way

The first version of this model let `FALLBACK_SELECTED` go straight to `ERROR`. **TL3 rejected it** —
the paper lists that state's successors as DISPATCHING, CANCELED or FAILED, and ERROR is not among
them.

The model was wrong and the property was right. Worth recording, because it is the case that shows
the properties are doing work in both directions rather than merely confirming what was already
believed.

## Caveats on the source

From the reference ledger, and worth knowing before building further on this paper:

- **Nothing in it is model-checked.** No tool, no evaluation, no results — the properties are
  *stated*, not *verified*. That is what this directory changes.
- **It is CTL, not TLA+**, with the `EF` gap described above.
- **The Validation Module is assumed, not specified**: "we assume the existence of a correct and
  functioning VM." `VM(EE)` in HP9 is a bare predicate — an assumption of exactly the kind the Dafny
  auditor enumerates, and the one the [`cedar`](../../policy/cedar) work makes concrete.
- It is a ~10-page workshop paper. The framework is a proposal, not a validated artifact.
