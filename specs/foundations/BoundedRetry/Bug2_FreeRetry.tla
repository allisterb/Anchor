---------------------------- MODULE Bug2_FreeRetry ----------------------------
(***************************************************************************)
(* BoundedRetry with one addition: a "clarification" round that does not    *)
(* reach the model, and so costs nothing.                                   *)
(*                                                                          *)
(* This is the failure the Agent Contracts work describes -- agents that     *)
(* interact indefinitely without completing. Every safety property still    *)
(* holds: the budget is never exceeded, because nothing is ever spent.      *)
(* Only liveness fails.                                                     *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Budget, MaxCost

ASSUME BudgetAssumption ==
    /\ Budget \in Nat
    /\ MaxCost \in Nat
    /\ MaxCost > 0

Costs == 1..MaxCost

VARIABLES phase, spent, reserved

vars == <<phase, spent, reserved>>

Phases == {"ready", "inflight", "done", "abandoned", "clarifying"}
Terminal == {"done", "abandoned"}

TypeOK ==
    /\ phase \in Phases
    /\ spent \in Nat
    /\ reserved \in Nat

Init ==
    /\ phase = "ready"
    /\ spent = 0
    /\ reserved = 0

CanAfford == spent + MaxCost <= Budget

Attempt ==
    /\ phase = "ready"
    /\ CanAfford
    /\ phase' = "inflight"
    /\ reserved' = MaxCost
    /\ UNCHANGED spent

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

\* THE BUG. Asking the user to clarify never reaches the model, so it is not
\* charged. Nothing here is wrong on its own; the damage is that it creates a
\* cycle through which the agent can move forever without spending.
Clarify ==
    /\ phase = "ready"
    /\ phase' = "clarifying"
    /\ UNCHANGED <<spent, reserved>>

Resume ==
    /\ phase = "clarifying"
    /\ phase' = "ready"
    /\ UNCHANGED <<spent, reserved>>

Next ==
    \/ Attempt
    \/ \E c \in Costs : Settle(c)
    \/ GiveUp
    \/ Clarify
    \/ Resume

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

BudgetSafe == spent + reserved <= Budget

StaysTerminal == (phase \in Terminal) => (vars' = vars)

TerminalIsFinal == [][StaysTerminal]_vars

EventuallyTerminates == <>(phase \in Terminal)

=============================================================================
