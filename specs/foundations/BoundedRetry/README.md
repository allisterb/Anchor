# BoundedRetry

**One agent, one budget.** An agent retries a task against a language model that may never produce
an acceptable answer. Two things must be true no matter what the model does: it never spends more
than the budget, and it always stops.

This is the only subject modelled **both** ways — in TLA+ *and* in Dafny — so the two tools can be
compared on the same problem. It is also the only one that crosses into real Python.

| file | what it is |
|---|---|
| `BoundedRetry.tla` | the TLA+ model. Verifies. |
| `Bug1_Overshoot.tla` | a wrong affordability check. Violates `BudgetSafe` — a **safety** failure. |
| `Bug2_FreeRetry.tla` | an uncharged retry path. Violates `EventuallyTerminates` — a **liveness** failure. |
| `BoundedRetry.dfy` | the same state machine, executable. Verifies. |
| `BoundedRetryFreeRetry.dfy` | the same uncharged retry. Fails its `decreases` clause. |
| `BoundedRetryExtern.dfy` | the model bound to real Python across `{:extern}`. Verifies, translates, runs. |
| `anchor_model.py` | the Python behind that boundary. |

New to TLA+? [`specs/DependencyDAG/README.md`](../DependencyDAG/README.md) has a notation primer.

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config specs/BoundedRetry/BoundedRetry.cfg specs/BoundedRetry/BoundedRetry.tla
```

## The model is deliberately not specified

The language model appears **only as nondeterminism**:

```tla
Costs == 1..MaxCost

Settle(c) ==
    /\ phase = "inflight"
    /\ spent' = spent + c
    /\ reserved' = 0
    /\ phase' \in {"ready", "done"}          \* success or not — nothing decides
```

An attempt costs anything in `1..MaxCost`, and returns success or failure by arbitrary choice. Every
property must hold across all of them, including an adversarial model that never once succeeds and
charges the maximum every time.

That follows from a practical fact: LLM nondeterminism is a hardware-level reality, not something a
prompt fixes. You cannot verify the model, so you verify the **harness** under a model permitted to
behave as badly as it likes.

## The two decisions that carry the proof

**Affordability is checked against the worst case.**

```tla
CanAfford == spent + MaxCost <= Budget
```

Not the expected cost — the real cost is unknown until the attempt returns. Committing on an average
leaves a window in which a call is out that cannot be paid for.

**The cost is reserved before the call, not charged after it.**

```tla
Attempt ==
    /\ phase = "ready"
    /\ CanAfford
    /\ phase' = "inflight"
    /\ reserved' = MaxCost      \* reserve first
    /\ UNCHANGED spent
```

`BudgetSafe` counts `spent + reserved`, which is what makes it hold *across* the in-flight window.
This is not an artifact of the model: the SDK confirms it. Usage arrives on the result, after the
call returns, so an implementation that wanted to check the real cost before paying it could not.

## The properties

| | |
|---|---|
| `BudgetSafe` | `spent + reserved <= Budget`. Never overspend, including mid-flight. |
| `EventuallyTerminates` | `<>(phase \in Terminal)`. The task always ends. |
| `TerminalIsFinal` | nothing changes once it has ended. |

`EventuallyTerminates` is the more interesting one. The task ends *whatever the model does*, because
an unhelpful model still exhausts the budget and reaches `abandoned`.

That holds **only because every attempt costs at least 1** — hence `ASSUME MaxCost > 0` and
`Costs == 1..MaxCost`. Any free path breaks it.

## Why one safety bug and one liveness bug

This is the argument for model checking rather than a constraint checker, and it is worth being
concrete.

`Bug1_Overshoot` is a **safety** failure: a finite path to a bad state. Any invariant checker finds
it.

`Bug2_FreeRetry` is not. Adding an uncharged "clarification" round leaves **every safety property
intact** — the budget is never exceeded, because nothing is ever spent. Only liveness fails, and TLC
reports it as a **lasso**: a trace ending in `Back to state`, an infinite cycle.

An invariant-only checker cannot see this class of bug at all. It is the failure mode behind agents
that interact indefinitely without ever completing.

## The two halves say the same thing

The Dafny implementation is the TLA+ model in executable form, and the correspondence is exact where
it matters:

| TLA+ | Dafny |
|---|---|
| `BudgetSafe` invariant | the loop invariant, and `ensures spent <= budget` |
| `EventuallyTerminates` | `decreases budget - spent` |
| `Costs == 1..MaxCost` | `ensures 1 <= cost <= maxCost` on `Attempt` |
| `phase' \in {"ready","done"}` | `ok`, returned unconstrained |

`Attempt` is deliberately **bodiless**. An implementation may return anything, so the verifier
reasons about every possibility — the same universal quantification TLC performs over behaviours,
and the same reason neither tool needs to model the LLM itself.

The clearest evidence they are making one argument rather than two: the same bug breaks both, in the
same place. `Bug2_FreeRetry.tla` fails liveness with a lasso; `BoundedRetryFreeRetry.dfy` fails with
`decreases expression might not decrease`. **Termination and liveness are the same claim**, and both
rest on every pass consuming something.

## Crossing into Python

`BoundedRetryExtern.dfy` binds the model to real Python. The proof does not change — the cost bound
was always an assumption about the outside world — but the assumption now has an address.

```dafny
module {:extern "anchor_model"} AnchorModel {
  class {:extern "Model"} Model {
    static method {:extern "attempt"} Attempt(maxCost: nat) returns (ok: bool, cost: nat)
      requires maxCost > 0
      ensures 1 <= cost <= maxCost
  }
}
```

Translating that emits, in `module_.py`:

```python
import anchor_model as anchor_model
...
out0_, out1_ = anchor_model.Model.attempt(maxCost)
```

The extern names decide the emitted call verbatim, as `module.Class.method`.

**Dafny does emit the `import`.** Its reference manual states that "there is no syntax in Dafny to
insert such `import` statements" and that the generated file must be hand-edited. That is not what
happens when the *module* carries `{:extern}` — the import appears. Worth knowing, because designing
around the documented limitation would mean building a post-processing step that is not needed.

### The boundary is where the assumption gets enforced

`anchor_model.py` clamps the cost to `1 <= cost <= maxCost` rather than trusting whatever the model
reports. Dafny assumed that clause and cannot check Python, so this is the only place it can be made
true. A usage field reporting zero cost would break termination; one reporting more than `maxCost`
would break the budget bound. Neither is hypothetical — see the metrics trap in
[`tests/strands/README.md`](../../tests/strands/README.md).

### The audit

`DafnyProgram.AuditAsync` enumerates every point where a proof rests on something taken on trust —
bodiless declarations with an `ensures`, `{:axiom}`, `{:verify false}`, `assume`, and `{:extern}`
declarations carrying a `requires` or `ensures`.

For `BoundedRetryExtern.dfy` it reports exactly **two**, both on `Attempt`. That is the complete
trust boundary of the program, and a test pins the count so it cannot silently grow.

It is also precise about what does *not* count: in `BoundedRetryFreeRetry.dfy`, `Attempt` is reported
and `NeedsClarification` is not, because the latter promises nothing a proof could lean on.

## What this does not cover

- **The cost oracle.** The proof assumes reported token counts match what is billed. If the meter
  lies, the invariant is about a fiction.
- **Paths outside the model.** Nothing proves an implementation cannot call the model somewhere the
  state machine does not describe. That is the refinement obligation.
- **Crash-restart.** If the process dies between reserving and settling, the reservation is lost
  unless it is durable. The model assumes one continuous execution.
- **Concurrency.** One agent only. Several agents on one budget is [`SharedBudget`](../SharedBudget).
