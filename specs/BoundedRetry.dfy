// The BoundedRetry workflow, implemented.
//
// This is the same state machine as BoundedRetry.tla, in executable form. The correspondence is
// deliberate and worth reading side by side:
//
//   TLA+                              Dafny
//   ----                              -----
//   BudgetSafe (invariant)            the loop invariant, and `ensures spent <= budget`
//   EventuallyTerminates (liveness)   `decreases budget - spent`
//   Costs == 1..MaxCost               `ensures 1 <= cost <= maxCost` on Attempt
//   phase' \in {"ready","done"}       `ok`, returned unconstrained
//
// The liveness property and the termination measure are the same argument: each pass must consume
// something, or neither holds.

datatype Outcome = Done | Abandoned

// The model, as the workflow sees it.
//
// Deliberately bodiless. An implementation may return anything at all, and the verifier reasons
// about every possibility — which is the point, since LLM non-determinism is not something the
// caller can constrain. The single promise is the cost bound, matching the TLA+ spec drawing cost
// from 1..MaxCost and letting the outcome be an arbitrary choice.
method Attempt(maxCost: nat) returns (ok: bool, cost: nat)
  requires maxCost > 0
  ensures 1 <= cost <= maxCost

// Run a task against the model.
method RunTask(budget: nat, maxCost: nat) returns (outcome: Outcome, spent: nat)
  requires maxCost > 0

  // Safety: the budget is never exceeded, whatever the model returns.
  ensures spent <= budget

  // No premature surrender: we only give up when another attempt genuinely could not be covered.
  // Without this, `outcome := Abandoned; return;` at the top would satisfy everything else.
  ensures outcome == Abandoned ==> spent + maxCost > budget
{
  spent := 0;
  var reserved := 0;
  outcome := Abandoned;

  while spent + maxCost <= budget
    invariant spent + reserved <= budget
    invariant reserved == 0

    // Termination. Each pass increases `spent` by at least 1, because Attempt promises
    // `cost >= 1`. A pass that could cost nothing would leave this unchanged and Dafny would
    // reject the loop — see BoundedRetryFreeRetry.dfy, where it does.
    decreases budget - spent
  {
    // Reserve the worst case before calling, not the actual cost after. The actual cost is
    // unknown until Attempt returns, so a check against anything smaller would leave a window
    // in which a call has been made that cannot be paid for.
    reserved := maxCost;
    assert spent + reserved <= budget;

    var ok, cost := Attempt(maxCost);

    spent := spent + cost;
    reserved := 0;

    if ok {
      outcome := Done;
      return;
    }
  }
}
