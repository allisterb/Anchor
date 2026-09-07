# Specs

TLA+ models of agent workflows. `SpecTests` in `tests/Anchor.Tests.Verifier` runs TLC over every
one of these on each build, so a spec that stops verifying — or a bug variant that stops being
caught — fails the suite.

| Model (TLA+) | |
|---|---|
| `BoundedRetry.tla` | an agent attempting a task against a model that may never succeed. Verifies. |
| `Bug1_Overshoot.tla` | with a wrong affordability check. Violates `BudgetSafe`. |
| `Bug2_FreeRetry.tla` | with an uncharged retry path. Violates `EventuallyTerminates`. |

| Implementation (Dafny) | |
|---|---|
| `BoundedRetry.dfy` | the same state machine, executable. Verifies. |
| `BoundedRetryFreeRetry.dfy` | the same uncharged retry path. Fails `decreases`. |
| `BoundedRetryExtern.dfy` | the model bound to real Python via `{:extern}`. Verifies, translates, runs. |
| `anchor_model.py` | the Python behind that boundary — the one thing the proof asks of the outside world. |

| Multi-agent (TLA+ only) | |
|---|---|
| `SharedBudget.tla` | several agents, one budget, atomic acquire. Verifies. |
| `Bug3_CheckThenReserve.tla` | check and reserve as two steps. Violates `BudgetSafe`. |

The two bug variants are the load-bearing half. A verifier that only ever reports success proves
nothing; these pin down that TLC catches a specific mistake and says which.

## BoundedRetry

**The model is deliberately not specified.** It appears only as nondeterminism: an attempt costs
anything in `1..MaxCost`, and returns success or failure by arbitrary choice. Every property has to
hold for all of those behaviours, including an adversarial model that never once succeeds and
charges the maximum every time. That follows from LLM non-determinism being a hardware-level
reality rather than something a prompt can fix — you cannot verify the model, so you verify the
harness under a model permitted to behave as badly as it likes.

Two design decisions carry the safety proof:

- **Affordability is checked against the worst case**, `spent + MaxCost <= Budget`, not against the
  expected cost. The real cost is unknown until the attempt returns.
- **The cost is reserved before the call, not charged after it.** `BudgetSafe` counts
  `spent + reserved`, which is what makes it hold across the window where a call is out and its cost
  is not yet known.

`EventuallyTerminates` is the more interesting property: the task ends *whatever the model does*,
because an unhelpful model still exhausts the budget and reaches `abandoned`.

That holds only because every attempt costs at least 1 — hence `ASSUME MaxCost > 0` and
`Costs == 1..MaxCost`. Any free path breaks it, which is exactly what `Bug2_FreeRetry` demonstrates.

## Why both a safety bug and a liveness bug

`Bug1_Overshoot` is a safety failure: a finite path to a bad state, which any invariant checker
would find.

`Bug2_FreeRetry` is not. Adding an uncharged "clarification" round leaves **every safety property
intact** — the budget is never exceeded, because nothing is ever spent. Only liveness fails, and TLC
reports it as a lasso: a trace ending in `Back to state`, an infinite cycle. An invariant-only
checker cannot see this class of bug at all, and it is the failure mode behind agents that interact
indefinitely without completing. That is the concrete argument for model checking here rather than
a constraint checker.

## The two halves say the same thing

The Dafny implementation is the TLA+ model in executable form, and the correspondence is exact
where it matters:

| TLA+ | Dafny |
|---|---|
| `BudgetSafe` invariant | the loop invariant, and `ensures spent <= budget` |
| `EventuallyTerminates` | `decreases budget - spent` |
| `Costs == 1..MaxCost` | `ensures 1 <= cost <= maxCost` on `Attempt` |
| `phase' \in {"ready","done"}` | `ok`, returned unconstrained |

`Attempt` is deliberately bodiless. An implementation may return anything, so the verifier reasons
about every possibility — the same universal quantification TLC performs over behaviours, and the
same reason neither tool needs to model the LLM itself.

The clearest evidence they are making one argument rather than two is that the same bug breaks both,
in the same place. `Bug2_FreeRetry.tla` fails liveness with a lasso; `BoundedRetryFreeRetry.dfy`
fails with `decreases expression might not decrease`. Termination and liveness are the same claim,
and both rest on every pass consuming something.

## Where TLA+ stops being redundant

On `BoundedRetry` the two tools agree, which is a useful cross-check but also means Dafny alone
would have caught both bugs. `SharedBudget` is where they part.

Several agents draw on one budget. Each runs the logic `BoundedRetry.dfy` already verifies, and each
is individually correct: every agent checks before it spends, and no agent overspends on its own.
Split the check from the reservation — two statements, which is what an implementation writes by
default — and TLC finds this:

```
 8: <Check>    spent = 5   reserved = (a1 :> 0 @@ a2 :> 0)   phase = (a1 :> "checked" @@ a2 :> "ready")
 9: <Check>    spent = 5   reserved = (a1 :> 0 @@ a2 :> 0)   phase = (a1 :> "checked" @@ a2 :> "checked")
10: <Reserve>  spent = 5   reserved = (a1 :> 3 @@ a2 :> 0)
11: <Reserve>  spent = 5   reserved = (a1 :> 3 @@ a2 :> 3)      -- 5 + 6 = 11 > 10
```

Both agents pass the check, because neither has reserved yet. Both then act on a decision that has
since stopped being true. The budget is broken by the *order*, not by either agent's logic.

**There is deliberately no Dafny counterpart to these two.** A loop invariant describes one thread of
control; it cannot say "and meanwhile another agent took the room I just checked for". Verifying
each agent separately — which is all Dafny offers here — finds nothing wrong, because nothing is
wrong with either agent. This is the division of labour: TLA+ for the protocol, Dafny for the
implementation.

The fix is in `SharedBudget.tla`: make the check and the reservation one atomic action, so nothing
can slip between deciding there is room and taking it.

## Crossing into Python

`BoundedRetryExtern.dfy` is `BoundedRetry.dfy` with the model bound to real Python. The proof does
not change — the cost bound was always an assumption about the outside world — but the assumption
now has an address.

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

The extern names decide the emitted call, verbatim, as `module.Class.method`. Dafny also writes an
empty `anchor_model.py` placeholder, which the real `anchor_model.py` in this directory replaces.

**Dafny does emit the `import`.** The reference manual states that "there is no syntax in Dafny to
insert such `import` statements" and that the generated file must be hand-edited. That is not what
happens when the *module* carries `{:extern}` — the import appears. Worth knowing, because designing
around the documented limitation would mean building a post-processing step that is not needed.

The round trip is a test, not a claim: `GeneratedPythonRunsAgainstTheRealModule` translates, writes
the output, drops in the real module, and runs it.

### The boundary is where Dafny's assumption gets enforced

`anchor_model.py` clamps the cost to `1 <= cost <= maxCost` rather than trusting whatever the model
reports. Dafny assumed that clause and cannot check Python, so this is the only place it can be made
true. A miscounted or absent usage field reporting zero cost would break termination; one reporting
more than `maxCost` would break the budget bound. Neither is hypothetical.

## The audit

`DafnyProgram.AuditAsync` enumerates every point where a proof rests on something taken on trust —
bodiless declarations with an `ensures`, `{:axiom}`, `{:verify false}`, `assume` statements, and
`{:extern}` declarations carrying a `requires` or `ensures`.

For `BoundedRetryExtern.dfy` it reports exactly two, both on `Attempt`: one for the requires, one for
the ensures. That is the complete trust boundary of the program, and it is checked by a test — so it
cannot silently grow.

It is also precise about what does *not* count. In `BoundedRetryFreeRetry.dfy`, `Attempt` is reported
and `NeedsClarification` is not, because the latter promises nothing that a proof could lean on.

## Running one by hand

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -tool -cleanup -config specs/BoundedRetry.cfg specs/BoundedRetry.tla
```

`CHECK_DEADLOCK FALSE` is set in each `.cfg`. `done` and `abandoned` have no successor action, which
is what termination looks like to TLC; without it, every correct ending is reported as a deadlock.

## What these proofs do not cover

Stated here rather than discovered later:

- **The cost oracle.** The proof assumes reported token counts match what is billed. If the meter
  lies, the invariant is about a fiction.
- **Paths outside the model.** Nothing here proves an implementation cannot call the model somewhere
  the state machine does not describe. That is the refinement obligation, and it is where the
  Dafny-to-Python translation lives.
- **Crash-restart.** If the process dies between reserving and settling, the reservation is lost
  unless it is durable. The model assumes one continuous execution.
