---------------------------- MODULE BoundedRetry ----------------------------
(***************************************************************************)
(* An agent attempting a task against a model that may never succeed.      *)
(*                                                                         *)
(* The model itself is NOT specified. It appears here only as              *)
(* nondeterminism: an attempt may cost anything up to MaxCost, and may or  *)
(* may not produce an acceptable answer. Every property below must hold    *)
(* for every one of those choices, including an adversarial model that     *)
(* never once succeeds and always costs the maximum. That is the point --  *)
(* we cannot verify the model, so we verify the harness under a model that *)
(* is allowed to behave as badly as it likes.                              *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS
    Budget,     \* total spend permitted for this task
    MaxCost     \* the most a single attempt can cost

ASSUME BudgetAssumption ==
    /\ Budget \in Nat
    /\ MaxCost \in Nat
    /\ MaxCost > 0      \* see LIVENESS NOTE below: a free attempt breaks termination

\* What an attempt actually costs is learned only after it returns.
Costs == 1..MaxCost

VARIABLES
    phase,      \* "ready" | "inflight" | "done" | "abandoned"
    spent,      \* irrevocably committed
    reserved    \* held against an attempt that is still out

vars == <<phase, spent, reserved>>

Phases == {"ready", "inflight", "done", "abandoned"}
Terminal == {"done", "abandoned"}

TypeOK ==
    /\ phase \in Phases
    /\ spent \in Nat
    /\ reserved \in Nat

Init ==
    /\ phase = "ready"
    /\ spent = 0
    /\ reserved = 0

(***************************************************************************)
(* Affordability is checked against the WORST case, not the expected one.  *)
(* The actual cost is unknown until the attempt returns, so committing on  *)
(* an average would leave a window in which a call has been made that      *)
(* cannot be paid for. This is the whole design decision.                  *)
(***************************************************************************)
CanAfford == spent + MaxCost <= Budget

Attempt ==
    /\ phase = "ready"
    /\ CanAfford
    /\ phase' = "inflight"
    /\ reserved' = MaxCost      \* reserve before calling, not after
    /\ UNCHANGED spent

\* The attempt returns: real cost c, and an outcome the agent does not control.
Settle(c) ==
    /\ phase = "inflight"
    /\ spent' = spent + c
    /\ reserved' = 0
    /\ phase' \in {"ready", "done"}

GiveUp ==
    /\ phase = "ready"
    /\ ~CanAfford
    /\ phase' = "abandoned"
    /\ UNCHANGED <<spent, reserved>>

Next ==
    \/ Attempt
    \/ \E c \in Costs : Settle(c)
    \/ GiveUp

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* SAFETY                                                                  *)
(***************************************************************************)

\* Money already gone plus money promised never exceeds the budget. Counting
\* the reservation is what makes this hold across the in-flight window.
BudgetSafe == spent + reserved <= Budget

\* Nothing is spent, and no phase changes, once the task has ended.
StaysTerminal == (phase \in Terminal) => (vars' = vars)

TerminalIsFinal == [][StaysTerminal]_vars

(***************************************************************************)
(* LIVENESS                                                                *)
(*                                                                         *)
(* The task always ends -- whatever the model does. A model that never      *)
(* returns an acceptable answer still terminates, by exhausting the budget  *)
(* and reaching "abandoned". This is the property that the "recursive       *)
(* clarification loop" failure violates.                                    *)
(*                                                                          *)
(* LIVENESS NOTE: this holds only because every attempt costs at least 1.   *)
(* Add a path that retries for free -- a cached reply, a clarification that *)
(* does not reach the model, a retry after a validation error charged to    *)
(* nobody -- and `spent` stops increasing, the budget is never exhausted,   *)
(* and this property fails. The free path IS the bug.                       *)
(***************************************************************************)

EventuallyTerminates == <>(phase \in Terminal)

=============================================================================
