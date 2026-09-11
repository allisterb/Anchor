------------------------------- MODULE Policies -------------------------------
(***************************************************************************)
(* The schema and the policy set, separated from the engine so they can be *)
(* replaced -- the same arrangement as Workflow.tla under DependencyDAG.   *)
(*                                                                         *)
(* The policy is the trading example from the AgentCore temporal-policy    *)
(* docs:                                                                   *)
(*                                                                         *)
(*   permit (principal, action == "SellShares", resource == gateway)       *)
(*   when temporal {                                                       *)
(*       formerly within 1h Action::"ApproveSale"::response{               *)
(*           input.stock:     context.input.stock,                         *)
(*           output.approved: true                                         *)
(*       }                                                                 *)
(*   };                                                                    *)
(*                                                                         *)
(* Three things in that one condition, each modelled below:                *)
(*                                                                         *)
(*   `within 1h`        the metric bound -- Window                         *)
(*   `input.stock:`     the FIRST-ORDER join. Not "some approval happened" *)
(*                      but "an approval for THIS stock". A propositional  *)
(*                      temporal logic cannot say that                     *)
(*   `::response`       the event kind -- and the subject of this file     *)
(***************************************************************************)
EXTENDS Naturals, Sequences

(***************************************************************************)
(* THE SCHEMA                                                              *)
(*                                                                         *)
(* Event kinds are declared here rather than built into the engine,        *)
(* because in Dogwood they are author-defined. From its own grammar:       *)
(* "Event kinds are author-defined, not a fixed set -- `request` /         *)
(* `response` are merely the conventional ones." A schema names them and   *)
(* marks one the `decision event`: the point at which authorization runs.  *)
(*                                                                         *)
(* `error` is not a Dogwood concept at all. It is AgentCore's convention   *)
(* for recording an action a policy denied, and it is why the two permits  *)
(* below -- identical but for one word -- behave completely differently.   *)
(***************************************************************************)
EventKinds == {"request", "response", "error"}
DecisionKind == "request"

Actions == {"ApproveSale", "SellShares"}
Stocks == {"ACME", "ZORP"}

PolicyIds == {"p_approve", "p_sell_response", "p_sell_request"}

\* The metric bound, in trajectory positions. `within 1h` in the docs; the unit
\* does not matter to the question, only that the look-back is bounded.
Window == 4

(***************************************************************************)
(* The one line that decides whether the approval gate means anything.     *)
(*                                                                         *)
(* Set in the .cfg rather than by swapping files, so every policy set is   *)
(* checked against the same engine with nothing else different. A          *)
(* plausible history for the TRUE case: approvals were tightened after the *)
(* SellShares rules were written, by someone who never looked at them.     *)
(***************************************************************************)
CONSTANT ForbidApprovals

ASSUME ForbidApprovalsAssumption == ForbidApprovals \in BOOLEAN

(***************************************************************************)
(* Does permit `p` match this request, given the trajectory `h` so far --  *)
(* which INCLUDES the request event being authorized -- at time `t`?       *)
(***************************************************************************)
PermitFires(p, req, h, t) ==
    CASE p = "p_approve" -> req.action = "ApproveSale"

      \* Gated on a COMPLETED approval.
      \*   formerly within Window ApproveSale::response{ stock: req.stock,
      \*                                                 approved: TRUE }
      [] p = "p_sell_response" ->
            /\ req.action = "SellShares"
            /\ \E i \in DOMAIN h :
                  /\ h[i].action = "ApproveSale"
                  /\ h[i].kind = "response"
                  /\ h[i].approved = TRUE
                  /\ h[i].stock = req.stock    \* the first-order join
                  /\ t - h[i].time <= Window   \* the metric bound

      \* The same rule with ONE WORD CHANGED, and it is a different security
      \* property. A `request` event is recorded for every attempt, permitted or
      \* not, so this gate matches "somebody TRIED to get an approval" -- which
      \* is not what it reads like, and not what its author meant.
      [] p = "p_sell_request" ->
            /\ req.action = "SellShares"
            /\ \E i \in DOMAIN h :
                  /\ h[i].action = "ApproveSale"
                  /\ h[i].kind = "request"
                  /\ h[i].stock = req.stock
                  /\ t - h[i].time <= Window

      [] OTHER -> FALSE

\* forbid (principal, action == "ApproveSale", resource);
\*
\* Note what this does NOT touch: both SellShares permits are unchanged, still
\* reference ApproveSale, and still validate.
ForbidFires(req, h, t) == ForbidApprovals /\ req.action = "ApproveSale"

=============================================================================
