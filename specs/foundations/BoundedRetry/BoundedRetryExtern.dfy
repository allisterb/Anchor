// BoundedRetry with the model bound to a real Python module.
//
// This is BoundedRetry.dfy with one change: `Attempt` is no longer merely bodiless, it is
// {:extern} and names the Python that implements it. The proof is unchanged — the cost bound was
// always an assumption about the outside world — but the assumption now has an address.
//
// Translating this emits, in module_.py:
//
//     import anchor_model as anchor_model
//     ...
//     out0_, out1_ = anchor_model.Model.attempt(maxCost)
//
// and an empty anchor_model.py placeholder to be replaced by the real thing. See anchor_model.py
// in this directory for the implementation the boundary requires.
//
// `dafny audit` — DafnyProgram.AuditAsync — reports exactly two assumptions here, one for the
// requires and one for the ensures, both on Attempt. That is the whole trust boundary of this
// program, enumerated rather than described.

datatype Outcome = Done | Abandoned

// The model. `{:extern "anchor_model"}` on the module and `{:extern "Model"}` / `{:extern "attempt"}`
// beneath it decide the Python names; the emitted call is module.Class.method verbatim.
module {:extern "anchor_model"} AnchorModel {
  class {:extern "Model"} Model {

    // Dafny ASSUMES this ensures clause. It cannot check Python, so nothing here is proved — which
    // is precisely what the audit reports and why the Python side needs its own tests.
    static method {:extern "attempt"} Attempt(maxCost: nat) returns (ok: bool, cost: nat)
      requires maxCost > 0
      ensures 1 <= cost <= maxCost
  }
}

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
    reserved := maxCost;
    assert spent + reserved <= budget;

    var ok, cost := AnchorModel.Model.Attempt(maxCost);

    spent := spent + cost;
    reserved := 0;

    if ok {
      outcome := Done;
      return;
    }
  }
}
