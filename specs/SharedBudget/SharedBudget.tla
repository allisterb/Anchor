---------------------------- MODULE SharedBudget ----------------------------
(***************************************************************************)
(* Several agents drawing on one budget.                                   *)
(*                                                                         *)
(* This is where TLA+ stops overlapping with Dafny. Each agent here is     *)
(* individually correct -- the same logic BoundedRetry.dfy verifies. What  *)
(* has to be checked is the interleaving, and an interleaving is not       *)
(* something a Dafny loop invariant can talk about.                        *)
(*                                                                         *)
(* In this version acquiring the reservation is ATOMIC: the check that     *)
(* there is room and the taking of it are one action, so nothing can slip  *)
(* between them. Bug3_CheckThenReserve.tla splits them, which is what an   *)
(* implementation does by default.                                         *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS
    Agents,     \* the set of agents sharing the budget
    Budget,     \* total spend permitted across all of them
    MaxCost     \* the most a single attempt can cost

ASSUME SharedBudgetAssumption ==
    /\ Agents # {}
    /\ Budget \in Nat
    /\ MaxCost \in Nat
    /\ MaxCost > 0

Costs == 1..MaxCost

VARIABLES
    phase,      \* [Agents -> Phases]
    spent,      \* shared: irrevocably committed by anyone
    reserved    \* [Agents -> Nat] held against each agent's in-flight attempt

vars == <<phase, spent, reserved>>

Phases == {"ready", "inflight", "done", "abandoned"}
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

\* Room for one more attempt, counting what everyone else already holds.
CanAfford == spent + TotalReserved + MaxCost <= Budget

(***************************************************************************)
(* Check and reserve as ONE action. This is the fix; see the bug variant    *)
(* for what happens when they are two.                                      *)
(***************************************************************************)
Acquire(a) ==
    /\ phase[a] = "ready"
    /\ CanAfford
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
    \/ Acquire(a)
    \/ \E c \in Costs : Settle(a, c)
    \/ GiveUp(a)

Next == \E a \in Agents : Step(a)

Fairness == \A a \in Agents : WF_vars(Step(a))

Spec == Init /\ [][Next]_vars /\ Fairness

(***************************************************************************)
(* PROPERTIES                                                              *)
(***************************************************************************)

\* The shared budget covers everything committed and everything promised,
\* across all agents at once.
BudgetSafe == spent + TotalReserved <= Budget

\* Every agent ends. No agent is starved by the others taking the budget
\* first -- whoever loses the race reaches "abandoned" rather than waiting.
AllTerminate == <>(\A a \in Agents : phase[a] \in Terminal)

=============================================================================
