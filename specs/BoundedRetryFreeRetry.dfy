// BoundedRetry with one addition: a clarification round that asks the user rather than the model,
// and so is not charged.
//
// This is the same bug as Bug2_FreeRetry.tla, and it fails for the same reason. There, TLC reports
// a lasso — an infinite cycle that never reaches a terminal state. Here, Dafny rejects the loop
// because `budget - spent` does not decrease on the clarification path.
//
// The two tools are making the same argument. Termination and the liveness property are the same
// claim, and both rest on every pass through the loop consuming something.
//
// Note what still holds: every safety property. The budget is never exceeded, because nothing is
// ever spent on this path. An invariant-only checker sees nothing wrong here at all.

datatype Outcome = Done | Abandoned

method Attempt(maxCost: nat) returns (ok: bool, cost: nat)
  requires maxCost > 0
  ensures 1 <= cost <= maxCost

// Does this round need a clarification from the user rather than a call to the model?
method NeedsClarification() returns (clarify: bool)

method RunTask(budget: nat, maxCost: nat) returns (outcome: Outcome, spent: nat)
  requires maxCost > 0
  ensures spent <= budget
  ensures outcome == Abandoned ==> spent + maxCost > budget
{
  spent := 0;
  var reserved := 0;
  outcome := Abandoned;

  while spent + maxCost <= budget
    invariant spent + reserved <= budget
    invariant reserved == 0
    decreases budget - spent
  {
    var clarify := NeedsClarification();
    if clarify {
      // THE BUG. This round never reaches the model, so nothing is charged, so `spent` is
      // unchanged and the measure does not decrease. Nothing here is wrong on its own; the
      // damage is that it creates a way round the loop that costs nothing.
      continue;
    }

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
