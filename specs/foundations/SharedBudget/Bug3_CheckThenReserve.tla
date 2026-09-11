------------------------- MODULE Bug3_CheckThenReserve -------------------------
(***************************************************************************)
(* SharedBudget with one change: deciding there is room and taking it are   *)
(* two actions rather than one.                                            *)
(*                                                                         *)
(* This is what an implementation does by default. You read the remaining  *)
(* budget, conclude an attempt fits, and then reserve it -- two statements, *)
(* and nothing holds the budget still in between.                          *)
(*                                                                         *)
(* Each agent is individually correct. Every one of them checks before it  *)
(* spends, and no single agent ever overspends. The fault exists only in   *)
(* the interleaving, which is why verifying the agents one at a time --    *)
(* which is all a Dafny loop invariant can do -- finds nothing.            *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Agents, Budget, MaxCost

ASSUME SharedBudgetAssumption ==
    /\ Agents # {}
    /\ Budget \in Nat
    /\ MaxCost \in Nat
    /\ MaxCost > 0

Costs == 1..MaxCost

VARIABLES phase, spent, reserved

vars == <<phase, spent, reserved>>

Phases == {"ready", "checked", "inflight", "done", "abandoned"}
Terminal == {"done", "abandoned"}

RECURSIVE SumReserved(_)
SumReserved(S) ==
    IF S = {} THEN 0
    ELSE LET a == CHOOSE x \in S : TRUE
         IN reserved[a] + SumReserved(S \ {a})

TotalReserved == SumReserved(Agents)

TypeOK ==
    /\ phase \in [Agents -> Phases]
    /\ spent \in Nat
    /\ reserved \in [Agents -> Nat]

Init ==
    /\ phase = [a \in Agents |-> "ready"]
    /\ spent = 0
    /\ reserved = [a \in Agents |-> 0]

CanAfford == spent + TotalReserved + MaxCost <= Budget

(***************************************************************************)
(* THE BUG, in two halves.                                                 *)
(***************************************************************************)

\* The decision, taken against the budget as it stands right now.
Check(a) ==
    /\ phase[a] = "ready"
    /\ CanAfford
    /\ phase' = [phase EXCEPT ![a] = "checked"]
    /\ UNCHANGED <<spent, reserved>>

\* The commitment, taken later. By now another agent may have claimed the room
\* this decision was based on, and nothing looks again.
Reserve(a) ==
    /\ phase[a] = "checked"
    /\ reserved' = [reserved EXCEPT ![a] = MaxCost]
    /\ phase' = [phase EXCEPT ![a] = "inflight"]
    /\ UNCHANGED spent

Settle(a, c) ==
    /\ phase[a] = "inflight"
    /\ spent' = spent + c
    /\ reserved' = [reserved EXCEPT ![a] = 0]
    /\ \E p \in {"ready", "done"} : phase' = [phase EXCEPT ![a] = p]

GiveUp(a) ==
    /\ phase[a] = "ready"
    /\ ~CanAfford
    /\ phase' = [phase EXCEPT ![a] = "abandoned"]
    /\ UNCHANGED <<spent, reserved>>

Step(a) ==
    \/ Check(a)
    \/ Reserve(a)
    \/ \E c \in Costs : Settle(a, c)
    \/ GiveUp(a)

Next == \E a \in Agents : Step(a)

Fairness == \A a \in Agents : WF_vars(Step(a))

Spec == Init /\ [][Next]_vars /\ Fairness

BudgetSafe == spent + TotalReserved <= Budget

AllTerminate == <>(\A a \in Agents : phase[a] \in Terminal)

=============================================================================
