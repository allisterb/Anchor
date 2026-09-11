# SharedBudget

**Several agents, one budget.** Each agent runs logic that is individually correct — the same logic
Dafny verifies in [`BoundedRetry`](../BoundedRetry) — and the budget is still broken. The fault is
in the *order* the agents interleave, not in any agent.

This directory is the concrete answer to "why not just use Dafny for everything".

| file | what it is |
|---|---|
| `SharedBudget.tla` | reservation acquired **atomically**. Verifies. |
| `Bug3_CheckThenReserve.tla` | check and reserve as two steps — what an implementation writes by default. Violates `BudgetSafe`. |

New to TLA+? [`specs/strands/DependencyDAG/README.md`](../../strands/DependencyDAG/README.md) has a notation primer.

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config specs/foundations/SharedBudget/SharedBudget.cfg specs/foundations/SharedBudget/SharedBudget.tla
```

## The shape

Everything from `BoundedRetry` becomes per-agent. `phase` and `reserved` are now **functions** from
agent to value; only `spent` stays shared:

```tla
VARIABLES
    phase,      \* [Agents -> Phases]
    spent,      \* shared: irrevocably committed by anyone
    reserved    \* [Agents -> Nat] held against each agent's in-flight attempt
```

Affordability now has to count what *everyone else* is holding, not just what has been spent:

```tla
CanAfford == spent + TotalReserved + MaxCost <= Budget
```

`TotalReserved` sums the reservations across all agents. That sum is the entire subject of this
model.

`Next` is a disjunction over agents, so TLC explores **every interleaving** — every order in which
two agents can check, reserve, call and settle relative to each other.

## The bug, in four states

Split the check from the reservation — two statements, which is what an implementation writes
without thinking about it — and TLC finds this:

```
 8: <Check>    spent = 5   reserved = (a1 :> 0 @@ a2 :> 0)   phase = (a1 :> "checked" @@ a2 :> "ready")
 9: <Check>    spent = 5   reserved = (a1 :> 0 @@ a2 :> 0)   phase = (a1 :> "checked" @@ a2 :> "checked")
10: <Reserve>  spent = 5   reserved = (a1 :> 3 @@ a2 :> 0)
11: <Reserve>  spent = 5   reserved = (a1 :> 3 @@ a2 :> 3)      -- 5 + 6 = 11 > 10
```

> `(a1 :> 0 @@ a2 :> 0)` is how TLC prints a function: `a1` maps to 0, `a2` maps to 0.

Both agents pass the check at steps 8 and 9, because **neither has reserved yet**. Both then act at
steps 10 and 11 on a decision that has since stopped being true.

Every agent checked before it spent. The check was correct. No agent overspent on its own. The
budget is broken by the interleaving alone.

The fix in `SharedBudget.tla` is to make the check and the reservation one atomic action, so nothing
can slip between deciding there is room and taking it.

## Why there is deliberately no Dafny counterpart

A Dafny loop invariant describes **one thread of control**. It cannot say "and meanwhile another
agent took the room I just checked for". Verifying each agent separately — which is all Dafny offers
here — finds nothing wrong, because nothing *is* wrong with either agent.

This is the division of labour the project rests on:

| | |
|---|---|
| **TLA+** | the protocol. What happens when several things run at once. |
| **Dafny** | the implementation. What one piece of code does, and that it terminates. |

On `BoundedRetry` the two tools agree, which is a useful cross-check but also means Dafny alone
would have caught both bugs there. `SharedBudget` is where they part, and it is the reason TLA+ is
in this project at all.

## The race is real, not a modelling artifact

`tests/strands/shared_budget.py` implements both ledgers against the actual Strands SDK, with three
agents and a scripted model. The naive ledger — check the budget, make the call, charge what it cost
— takes a 10 000 token budget to **15 000**. The reserving ledger, which is this spec's atomic
acquire, stays at 9 000.

The same file also turned up a trap that this spec does **not** protect against:
`result.metrics.accumulated_usage` is the running total across an agent's invocations, not the cost
of the last call. Charging it per call bills the first attempt again on the second, and the first two
again on the third — an overcharge that compounds and looks entirely plausible in a log. The per-call
figure is `result.metrics.agent_invocations[-1].usage`.

That is worth dwelling on. `BudgetSafe` holds over a variable called `spent`; nothing in the model
says `spent` is computed from the right field of the right object. Read the wrong one and every proof
still passes while the budget is silently wrong. That is the **refinement gap** in one concrete line,
and the argument for keeping the boundary between spec and SDK narrow and tested.
