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
(*   a FORBID on an aggregate          sees count/sum = 0, does not fire   *)
(*                                     -> FAILS OPEN. Rotation hands the   *)
(*                                        caller a fresh allowance.        *)
(*                                                                         *)
(* Budget caps, rate limits and mutual-exclusion rules are all the second  *)
(* shape. Approval gates are the first.                                    *)
(*                                                                         *)
(* THE CONTROL MATTERS. `NoRotation_CapHolds.cfg` runs the same policy and *)
(* the same adversary with rotation disabled, and the cap holds. Without   *)
(* that config the violation below would not be attributable to rotation.  *)
(*                                                                         *)
(* SELF-REFERENTIAL INCLUSION IS MODELLED. AgentCore documents that "when  *)
(* a temporal condition references the same action that is being           *)
(* authorized, the current request's own event is included in the          *)
(* evaluation", so the aggregate below counts the trade being decided.     *)
(* That is what makes the cap bite at all rather than one trade late.      *)
(***************************************************************************)
EXTENDS Naturals, Sequences

CONSTANTS
    Limit,          \* the total the policy author means to allow
    MaxAmount,      \* the largest single trade
    MaxSteps,       \* bound on the run
    Gate,           \* "aggregate" (forbid on a sum) or "approval" (permit on a prior event)
    MayRotate       \* whether the caller may start a fresh session

ASSUME RotationAssumption ==
    /\ Limit \in Nat /\ Limit > 0
    /\ MaxAmount \in Nat /\ MaxAmount > 0
    /\ MaxSteps \in Nat /\ MaxSteps > 0
    /\ Gate \in {"aggregate", "approval"}
    /\ MayRotate \in BOOLEAN

Amounts == 1..MaxAmount

VARIABLES
    hist,       \* the CURRENT session's trajectory -- what the policy engine can see
    traded,     \* the true total across every session -- what the author meant to bound
    unapproved, \* TRUE once a trade was allowed with no approval in its own session
    steps

vars == <<hist, traded, unapproved, steps>>

Events == [action: {"Approve", "Trade"}, amount: 0..MaxAmount]

TypeOK ==
    /\ traded \in 0..(MaxSteps * MaxAmount)
    /\ unapproved \in BOOLEAN
    /\ steps \in 0..MaxSteps
    /\ \A i \in DOMAIN hist : hist[i] \in Events

Init ==
    /\ hist = << >>
    /\ traded = 0
    /\ unapproved = FALSE
    /\ steps = 0

(***************************************************************************)
(* WHAT THE ENGINE CAN SEE -- and it can only see the current session.     *)
(***************************************************************************)
RECURSIVE SumTrades(_)
SumTrades(s) ==
    IF s = << >> THEN 0
    ELSE (IF Head(s).action = "Trade" THEN Head(s).amount ELSE 0) + SumTrades(Tail(s))

\* `sum within W Trade::request{...}` over this session.
SessionTraded == SumTrades(hist)

\* `formerly within W Approve::response{...}` in this session.
SessionApproved == \E i \in DOMAIN hist : hist[i].action = "Approve"

(***************************************************************************)
(* THE DECISION                                                            *)
(*                                                                         *)
(* aggregate: permit Trade, and forbid it when the session's running total *)
(*            INCLUDING this request would exceed the cap.                 *)
(* approval:  permit Trade only when an approval is in this session.       *)
(***************************************************************************)
Allowed(action, amount) ==
    IF action = "Approve" THEN TRUE
    ELSE IF Gate = "aggregate" THEN SessionTraded + amount <= Limit
    ELSE SessionApproved

(***************************************************************************)
(* TRANSITIONS                                                             *)
(***************************************************************************)
Attempt(action, amount) ==
    /\ steps < MaxSteps
    /\ Allowed(action, amount)
    /\ hist' = Append(hist, [action |-> action, amount |-> amount])
    /\ traded' = IF action = "Trade" THEN traded + amount ELSE traded
    \* Parenthesised deliberately: `\/` binds looser than `=`, so without them this reads
    \* as `(unapproved' = unapproved) \/ (...)` -- a disjunction, not an assignment, and TLC
    \* reports the variable as unassigned the moment the right-hand disjunct holds.
    /\ unapproved' = (unapproved \/ (action = "Trade" /\ ~SessionApproved))
    /\ steps' = steps + 1

\* The caller supplies the session id, so this needs no cooperation from anyone:
\* send the next request under a new one and the engine sees an empty trajectory.
\* The global total is untouched, because the world does not reset.
Rotate ==
    /\ MayRotate
    /\ steps < MaxSteps
    /\ hist # << >>
    /\ hist' = << >>
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

\* What the author of the aggregate policy meant: never more than Limit in total.
\* The engine only ever enforces it per session.
GlobalCapHolds == traded <= Limit

\* What the author of the approval policy meant: no trade without an approval.
\* Rotation cannot manufacture one -- an empty trajectory denies.
EveryTradeApproved == ~unapproved

=============================================================================
