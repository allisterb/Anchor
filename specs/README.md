# Specs

TLA+ models of agent workflows. `SpecTests` in `tests/Anchor.Tests.Verifier` runs TLC over every
one of these on each build, so a spec that stops verifying — or a bug variant that stops being
caught — fails the suite.

| | |
|---|---|
| `BoundedRetry` | an agent attempting a task against a model that may never succeed. Verifies. |
| `Bug1_Overshoot` | `BoundedRetry` with a wrong affordability check. Violates `BudgetSafe`. |
| `Bug2_FreeRetry` | `BoundedRetry` with an uncharged retry path. Violates `EventuallyTerminates`. |

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
