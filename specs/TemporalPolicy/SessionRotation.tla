--------------------------- MODULE SessionRotation ---------------------------
(***************************************************************************)
(* What a caller who controls the session ID can do to a temporal policy.  *)
(*                                                                         *)
(* AgentCore scopes temporal history to a POLICY SESSION, and the session  *)
(* id travels in a caller-supplied header. AWS says what follows, in their *)
(* own security considerations:                                            *)
(*                                                                         *)
(*   "Because temporal history is scoped to a session and the session ID   *)
(*    is supplied by the caller, a count-based limit such as 'at most N    *)
(*    calls per session' counts only the events recorded for that session. *)
(*    Starting a new session begins a new count, so a temporal rate limit  *)
(*    constrains activity within a session rather than across all of a     *)
(*    caller's sessions."                                                  *)
(*                                                                         *)
(* So this is not a discovery. What is not written down is which policy    *)
(* SHAPES survive it, and that turns out to split cleanly -- in opposite   *)
(* directions, from the same cause.                                        *)
(*                                                                         *)
(* THE ASYMMETRY. On a fresh trajectory the history is empty, so:          *)
(*                                                                         *)
(*   a PERMIT gated on a prior event   does not fire -> default deny       *)
(*                                     -> FAILS CLOSED. Rotation costs the *)
(*                                        caller the capability.           *)
(*                                                                         *)
(*   a FORBID on an aggregate          sees sum/count = 0, does not fire   *)
(*                                     -> FAILS OPEN. Rotation hands the   *)
(*                                        caller a fresh allowance.        *)
(*                                                                         *)
(* Budget caps, rate limits and mutual-exclusion rules are all the second  *)
(* shape. Approval gates are the first.                                    *)
(*                                                                         *)
(* NEITHER THE DECISION NOR THE POLICY IS WRITTEN HERE.                    *)
(*                                                                         *)
(* The decision comes from DogwoodSemantics, whose reading of `formerly`,  *)
(* `sum` and `tp` agrees with the reference implementation on 654 recorded *)
(* cases. The policy comes from rotation_aggregate.dw and                  *)
(* rotation_approval.dw -- real Dogwood text, translated by the same       *)
(* parser, into RotationPolicies.tla.                                      *)
(*                                                                         *)
(* Two earlier versions of this spec each hand-wrote one of those halves,  *)
(* and each time the headline finding rested on something unchecked: first *)
(* a hand-rolled `SumTrades`, then hand-written policy records that no one *)
(* had compared against the Dogwood text in their own comment. The only    *)
(* thing this module still asserts on its own is the adversary.            *)
(*                                                                         *)
(* THE CONTROL MATTERS. `NoRotation_CapHolds.cfg` runs the same policy and *)
(* the same adversary with rotation disabled, and the cap holds. Without   *)
(* that config the violation would not be attributable to rotation.        *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC, RotationPolicies

CONSTANTS
    MaxAmount,      \* the largest single trade
    MaxSteps,       \* bound on the run
    Gate,           \* "aggregate" (forbid on a sum) or "approval" (permit on a prior event)
    MayRotate       \* whether the caller may start a fresh session

ASSUME RotationAssumption ==
    /\ MaxAmount \in Nat /\ MaxAmount > 0
    /\ MaxSteps \in Nat /\ MaxSteps > 0
    /\ Gate \in {"aggregate", "approval"}
    /\ MayRotate \in BOOLEAN

Amounts == 1..MaxAmount

\* `Cases` is only read by DogwoodSemantics!Agree, which this module never calls; the
\* evaluator's Decide takes its trace and policies as arguments.
D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(***************************************************************************)
(* The policy set, generated from the .dw sources. `Cap` is the bound the  *)
(* aggregate policy states, lifted out of the same text so the property    *)
(* and the rule cannot disagree about what the cap is.                     *)
(***************************************************************************)
Policies == IF Gate = "aggregate" THEN AggregatePolicies ELSE ApprovalPolicies

Str(x) == [k |-> "s", v |-> x]
Num(x) == [k |-> "n", v |-> x]

EmptyRec == [f \in {} |-> Str("")]
Anon == Str("caller")

\* The domain a bound variable of non-Timepoint type ranges over.
Values == {Num(x) : x \in Amounts}

VARIABLES
    trace,      \* the CURRENT session's trajectory -- all the policy engine can see
    traded,     \* the true total across every session -- what the author meant to bound
    unapproved, \* TRUE once a trade was allowed with no approval in its own session
    steps

vars == <<trace, traded, unapproved, steps>>

TypeOK ==
    /\ traded \in 0..(MaxSteps * MaxAmount)
    /\ unapproved \in BOOLEAN
    /\ steps \in 0..MaxSteps
    /\ Len(trace) \in 0..MaxSteps

Init ==
    /\ trace = << >>
    /\ traded = 0
    /\ unapproved = FALSE
    /\ steps = 0

SessionApproved == \E i \in DOMAIN trace : trace[i].action = "Approve"

Event(action, amount) ==
    [time     |-> Len(trace) + 1,
     action   |-> action,
     kind     |-> "request",
     input    |-> IF action = "Trade" THEN [amount |-> Num(amount)] ELSE EmptyRec,
     output   |-> EmptyRec,
     principal |-> Anon,
     resource  |-> Anon,
     isDecision |-> TRUE]

(***************************************************************************)
(* TRANSITIONS                                                             *)
(*                                                                         *)
(* The request event is appended BEFORE the decision, because AgentCore    *)
(* documents that a self-referential condition sees the current request --  *)
(* which is what makes the cap bite on the trade that would breach it      *)
(* rather than one trade late.                                             *)
(***************************************************************************)
Attempt(action, amount) ==
    /\ steps < MaxSteps
    /\ LET withReq == Append(trace, Event(action, amount))
           idx     == Len(withReq)
       IN /\ D!Decide(withReq, Policies, idx, Values)
          /\ trace' = withReq
          /\ traded' = IF action = "Trade" THEN traded + amount ELSE traded
          \* Parenthesised deliberately: `\/` binds looser than `=`, so without them this
          \* reads as a disjunction rather than an assignment and TLC reports the variable
          \* as unassigned the moment the right-hand side holds.
          /\ unapproved' = (unapproved \/ (action = "Trade" /\ ~SessionApproved))
    /\ steps' = steps + 1

\* The caller supplies the session id, so this needs no cooperation from anyone: send the
\* next request under a new one and the engine sees an empty trajectory. The global total
\* is untouched, because the world does not reset.
Rotate ==
    /\ MayRotate
    /\ steps < MaxSteps
    /\ trace # << >>
    /\ trace' = << >>
    /\ steps' = steps + 1
    /\ UNCHANGED <<traded, unapproved>>

Next ==
    \/ \E amount \in Amounts : Attempt("Trade", amount)
    \/ Attempt("Approve", 0)
    \/ Rotate

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* PROPERTIES                                                              *)
(*                                                                         *)
(* Each shape is checked against the thing it is supposed to give you.     *)
(* They are different properties on purpose: an aggregate forbid is a      *)
(* volume control and an approval gate is an authorization control, and    *)
(* the point is that rotation defeats one and not the other.               *)
(***************************************************************************)

\* What the author of the aggregate policy meant: never more than Cap in total.
\* The engine only ever enforces it per session.
GlobalCapHolds == traded <= Cap

\* What the author of the approval policy meant: no trade without an approval.
\* Rotation cannot manufacture one -- an empty trajectory denies.
EveryTradeApproved == ~unapproved

=============================================================================
