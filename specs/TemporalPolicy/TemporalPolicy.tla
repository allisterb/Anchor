---------------------------- MODULE TemporalPolicy ----------------------------
(***************************************************************************)
(* Vacuity checking for session-aware (temporal) authorization policies.   *)
(*                                                                         *)
(* THE QUESTION. AgentCore's temporal policies -- written in Dogwood, a    *)
(* Cedar superset -- decide using the history of a session rather than the *)
(* current request alone. AWS says plainly that they "do not currently     *)
(* support the powerful automated reasoning analysis tools that Cedar      *)
(* provides." So Dogwood ENFORCES a policy on the session that happens,    *)
(* and nothing checks that the policy set means what its author intended   *)
(* across the sessions that could happen.                                  *)
(*                                                                         *)
(* The cheapest such check is VACUITY: is there any session at all in      *)
(* which this permit grants something? A permit that can never fire is a   *)
(* silent deny-everything. It looks like a working policy, it validates,   *)
(* it deploys, and the capability it was written to allow is simply gone.  *)
(*                                                                         *)
(* READ THE RESULT BACKWARDS. This module checks `NeverFires`, so:         *)
(*                                                                         *)
(*     TLC reports a VIOLATION  ->  the permit is SATISFIABLE, and the     *)
(*                                  counterexample is the witness session  *)
(*     TLC reports NO ERROR     ->  the permit is VACUOUS. This is the bad *)
(*                                  outcome, and it is the quiet one.      *)
(*                                                                         *)
(* TLA+ is linear-time and has no `EF`, so reachability is checked as the  *)
(* negation of an invariant and the trace is read as the witness. Here     *)
(* that workaround is the whole tool.                                      *)
(*                                                                         *)
(* TWO LAYERS, AND THEY ARE NOT THE SAME THING                             *)
(*                                                                         *)
(* Dogwood, the LANGUAGE, does not have a fixed event vocabulary. Its own  *)
(* grammar says so: "Event kinds are author-defined, not a fixed set --    *)
(* `request` / `response` are merely the conventional ones." A schema      *)
(* declares the kinds and marks one of them the `decision event`.          *)
(*                                                                         *)
(* AgentCore, the SERVICE, supplies the convention: it records a `request` *)
(* event for every attempt, then a `response` if the action was permitted  *)
(* and completed, or an `error` if a policy denied it.                     *)
(*                                                                         *)
(* This module models the SERVICE convention, because that is what decides *)
(* whether a policy written against it means anything. Policies.tla holds  *)
(* the schema-declared vocabulary so the two stay visibly separate.        *)
(*                                                                         *)
(* TWO EVENTS PER ATTEMPT. An earlier version of this spec collapsed an    *)
(* attempt into one event. The reference corpus shows otherwise -- 3302    *)
(* `::request` against 1069 `::response` across its traces, and a denied   *)
(* attempt still appears as a `request`. That distinction is the whole     *)
(* difference between the two permits in Policies.tla.                     *)
(*                                                                         *)
(* THE DECISION SEES ITS OWN REQUEST EVENT, which AgentCore documents:     *)
(* "When a temporal condition references the same action that is being     *)
(* authorized, the current request's own event is included in the          *)
(* evaluation." It is also where every `count`-based limit gets its        *)
(* off-by-one.                                                             *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, Policies

CONSTANTS
    MaxAttempts,    \* bound on session length, in attempts (two events each)
    Target          \* the permit id under test

ASSUME VacuityAssumption ==
    /\ MaxAttempts \in Nat /\ MaxAttempts > 0
    /\ Target \in PolicyIds

\* What the agent may attempt. Every combination, at any time.
Requests == [action: Actions, stock: Stocks]

MaxTime == 2 * MaxAttempts

Events == [action: Actions, stock: Stocks, kind: EventKinds,
           approved: BOOLEAN, time: 1..MaxTime]

VARIABLES
    hist,       \* Seq(Events) -- the session's recorded trajectory
    fired       \* SUBSET PolicyIds -- permits that have actually granted something

vars == <<hist, fired>>

\* Time is the position in the trajectory, as in the corpus traces, where a
\* verdict is reported at `(time point N)` -- the index of the decision event.
Now == Len(hist)

TypeOK ==
    /\ fired \subseteq PolicyIds
    /\ Len(hist) \in 0..MaxTime
    /\ \A i \in DOMAIN hist : hist[i] \in Events

Init ==
    /\ hist = << >>
    /\ fired = {}

(***************************************************************************)
(* THE DECISION                                                            *)
(*                                                                         *)
(* Deny by default, forbid overrides permit -- Cedar's model, which        *)
(* Dogwood keeps. `h` is the trajectory INCLUDING the request event being  *)
(* authorized, and `t` its time.                                           *)
(***************************************************************************)
Matching(req, h, t) == {p \in PolicyIds : PermitFires(p, req, h, t)}

Allowed(req, h, t) == Matching(req, h, t) # {} /\ ~ForbidFires(req, h, t)

\* A permit "fired" when it matched AND the request was allowed. A permit that
\* matches but is always overridden by a forbid grants nothing, and counting it
\* as fired would report an inert policy as live.
Granted(req, h, t) == IF Allowed(req, h, t) THEN Matching(req, h, t) ELSE {}

(***************************************************************************)
(* TRANSITIONS                                                             *)
(*                                                                         *)
(* One attempt appends two events: the decision event, then its outcome.   *)
(* The agent picks anything; an approver may return either verdict. Both   *)
(* are behaviours, so a result holds whatever the agent and approver do.   *)
(***************************************************************************)
Event(req, kind, approved, t) ==
    [action |-> req.action, stock |-> req.stock, kind |-> kind,
     approved |-> approved, time |-> t]

Attempt(req, approved) ==
    /\ Len(hist) + 2 <= MaxTime
    /\ LET t        == Now + 1
           withReq  == Append(hist, Event(req, DecisionKind, FALSE, t))
           ok       == Allowed(req, withReq, t)
           \* AgentCore's convention: permitted-and-completed is a `response`,
           \* denied is an `error`. The request event above is recorded either way.
           outcome  == IF ok THEN Event(req, "response", approved, t + 1)
                             ELSE Event(req, "error", FALSE, t + 1)
       IN /\ hist' = Append(withReq, outcome)
          /\ fired' = fired \union Granted(req, withReq, t)

Next == \E req \in Requests, approved \in BOOLEAN : Attempt(req, approved)

\* No fairness. Vacuity is a reachability question -- does ANY session make this
\* permit fire -- so nothing needs to be forced to happen.
Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* THE PROPERTY                                                            *)
(***************************************************************************)

\* Checked as an invariant, and MEANT TO FAIL. A violation is the witness session
\* proving the permit can grant something; completing without error means it never
\* can, in any session of up to MaxAttempts attempts.
NeverFires == Target \notin fired

=============================================================================
