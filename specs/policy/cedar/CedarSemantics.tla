---------------------------- MODULE CedarSemantics ----------------------------
(***************************************************************************)
(* Cedar's authorization decision, for the subset Strands' CedarAuthorization *)
(* handler can actually produce.                                            *)
(*                                                                          *)
(* This module is the hand-written half and the part to review. The policies *)
(* it evaluates are translated mechanically from a .cedar file; the oracle   *)
(* it is compared against comes from the real cedarpy engine. Neither is     *)
(* written by hand, which is the point: the only thing anyone has to trust   *)
(* by reading is the semantics below.                                        *)
(*                                                                          *)
(* SUBSET MODELLED. The translator refuses anything outside it rather than   *)
(* guessing, because a translator that silently mishandles a construct is    *)
(* worse than one that stops:                                                *)
(*                                                                          *)
(*   - permit / forbid                                                       *)
(*   - principal: unconstrained, == an entity, or a bare type match          *)
(*   - action:    unconstrained, == one action, or `in` a set                *)
(*   - resource:  unconstrained ONLY. Strands hardcodes Resource::"agent"    *)
(*                on every request, so resource-scoped policies cannot be    *)
(*                expressed through that handler at all.                     *)
(*   - when { context.session.call_count <op> N } for op in < <= > >= ==     *)
(***************************************************************************)
EXTENDS Naturals, Sequences, TLC

CONSTANTS
    Policies,       \* Seq of policy records, translated from the .cedar file
    Oracle,         \* [Requests -> {"Allow","Deny"}], from the real engine
    PrincipalSet,   \* set of [type |-> STRING, id |-> STRING]
    ActionSet,      \* set of tool names
    CallCountSet    \* set of Nat -- the session.call_count values to explore

Requests == [principal: PrincipalSet, action: ActionSet, callCount: CallCountSet]

(***************************************************************************)
(* Scope matching                                                          *)
(***************************************************************************)

MatchesPrincipal(scope, req) ==
    CASE scope.kind = "any"  -> TRUE
      [] scope.kind = "eq"   -> req.principal = scope.entity
      [] scope.kind = "type" -> req.principal.type = scope.entityType
      [] OTHER               -> FALSE

MatchesAction(scope, req) ==
    CASE scope.kind = "any" -> TRUE
      [] scope.kind = "eq"  -> req.action = scope.name
      [] scope.kind = "in"  -> req.action \in scope.names
      [] OTHER              -> FALSE

(***************************************************************************)
(* Conditions. Only session.call_count is modelled, because it is the only  *)
(* context field the handler populates that a policy can meaningfully       *)
(* range over. hour_utc is wall-clock and enricher fields are arbitrary.    *)
(***************************************************************************)

SatisfiesCondition(cond, req) ==
    CASE cond.op = "lt"  -> req.callCount <  cond.value
      [] cond.op = "lte" -> req.callCount <= cond.value
      [] cond.op = "gt"  -> req.callCount >  cond.value
      [] cond.op = "gte" -> req.callCount >= cond.value
      [] cond.op = "eq"  -> req.callCount =  cond.value
      [] OTHER           -> FALSE

Matches(pol, req) ==
    /\ MatchesPrincipal(pol.principal, req)
    /\ MatchesAction(pol.action, req)
    /\ \A i \in DOMAIN pol.conditions : SatisfiesCondition(pol.conditions[i], req)

(***************************************************************************)
(* The decision.                                                           *)
(*                                                                          *)
(* Cedar is deny-by-default and forbid overrides permit unconditionally --   *)
(* a matching forbid wins however many permits also match. Getting this      *)
(* ordering wrong is the single most likely way for the model to diverge     *)
(* from the engine, which is what the differential test is for.              *)
(***************************************************************************)

ForbidMatches(req) ==
    \E i \in DOMAIN Policies : Policies[i].effect = "forbid" /\ Matches(Policies[i], req)

PermitMatches(req) ==
    \E i \in DOMAIN Policies : Policies[i].effect = "permit" /\ Matches(Policies[i], req)

Decide(req) ==
    IF ForbidMatches(req) THEN "Deny"
    ELSE IF PermitMatches(req) THEN "Allow"
    ELSE "Deny"

(***************************************************************************)
(* The differential property: over the whole finite request space, this     *)
(* model and the real engine reach the same decision. A counterexample      *)
(* names the exact request they disagree on.                                *)
(***************************************************************************)

(* Assert rather than a bare equality, so a failure names the request and both verdicts. A plain
   conjunction would only report "invariant violated", leaving the disagreement to be hunted for by
   hand across the whole request space -- which is most of the value of running this at all. *)
Agree ==
    \A r \in Requests :
        \/ Decide(r) = Oracle[r]
        \/ Assert(FALSE,
             <<"DISAGREEMENT", r, "model says", Decide(r), "engine says", Oracle[r]>>)

=============================================================================
