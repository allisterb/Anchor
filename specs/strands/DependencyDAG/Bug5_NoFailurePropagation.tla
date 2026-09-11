---------------------------- MODULE Bug5_NoFailurePropagation ----------------------------
(***************************************************************************)
(* DependencyDAG with failure propagation removed: CancelOrphan is gone    *)
(* from Next, so a task whose incoming edges are all dead simply waits.    *)
(*                                                                         *)
(* HP10 satisfied and TL1 broken at the same time, which is the point:     *)
(* one task fails, everything downstream stays BLOCKED, the graph never    *)
(* finishes. NOTHING UNSAFE HAPPENS -- HP10 holds throughout, and so does  *)
(* NoOrphanRuns. Only liveness fails.                                      *)
(*                                                                         *)
(* An orchestrator audited against HP10 alone would pass this and then     *)
(* hang in production on the first failed sub-task. HP10 and TL1 are not   *)
(* independent: satisfying HP10 creates an obligation to cancel the        *)
(* orphaned subgraph, which Table 1 never states.                          *)
(***************************************************************************)
(* HP10 from arXiv:2510.14133v2 Table 1 — the Orchestrator invokes a       *)
(* sub-task only once every one it depends on has completed.               *)
(*                                                                         *)
(*   AG( ∀i ∈ D : CL.invoke(EE, prot, sub_task_i)                          *)
(*                  → ∀p ∈ parents(sub_task_i) : Completed(p) )            *)
(*                                                                         *)
(* Readiness is per-edge, not per-node — see the header of                 *)
(* DependencyDAG.tla for why, and for the SIMPLIFICATION and KNOWN GAP     *)
(* notes that apply here unchanged.                                        *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Workflow

States == {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELED"}
Terminal == {"COMPLETED", "FAILED", "CANCELED"}

VARIABLES
    state,           \* [Tasks -> States]
    oracle           \* [NondetEdges -> BOOLEAN] -- see the header of DependencyDAG.tla

vars == <<state, oracle>>

TypeOK == /\ state \in [Tasks -> States]
          /\ oracle \in [NondetEdges -> BOOLEAN]

Init == /\ state = [t \in Tasks |-> "BLOCKED"]
        /\ oracle \in [NondetEdges -> BOOLEAN]

Done(t) == state[t] = "COMPLETED"

Deps == [t \in Tasks |-> {p \in Tasks : <<p, t>> \in Edges}]

Entry(t) == Deps[t] = {}

Traversable(p, t) ==
    IF <<p, t>> \in NondetEdges THEN oracle[<<p, t>>] ELSE EdgeCond(p, t, state)

CanFire(p, t) ==
    /\ <<p, t>> \in Edges
    /\ Done(p)
    /\ Traversable(p, t)

EdgeDead(p, t) ==
    \/ state[p] \in {"FAILED", "CANCELED"}
    \/ /\ Done(p)
       /\ ~Traversable(p, t)
       /\ \A n \in EdgeSupport(p, t) : state[n] \in Terminal

Doomed(t) ==
    /\ ~Entry(t)
    /\ \A p \in Deps[t] : EdgeDead(p, t)

(***************************************************************************)
(* TRANSITIONS                                                             *)
(***************************************************************************)

\* The OR rule: an entry point is runnable at once, and any other task becomes
\* runnable as soon as ONE incoming edge fires.
Unblock(t) ==
    /\ state[t] = "BLOCKED"
    /\ \/ Entry(t)
       \/ \E p \in Deps[t] : CanFire(p, t)
    /\ state' = [state EXCEPT ![t] = "READY"]
    /\ UNCHANGED oracle

Start(t) ==
    /\ state[t] = "READY"
    /\ state' = [state EXCEPT ![t] = "IN_PROGRESS"]
    /\ UNCHANGED oracle

Succeed(t) ==
    /\ state[t] = "IN_PROGRESS"
    /\ state' = [state EXCEPT ![t] = "COMPLETED"]
    /\ UNCHANGED oracle

Fail(t) ==
    /\ state[t] = "IN_PROGRESS"
    /\ state' = [state EXCEPT ![t] = "FAILED"]
    /\ UNCHANGED oracle

(***************************************************************************)
(* The bug. CancelOrphan is defined but never reached from Next, so the    *)
(* orphaned subgraph is left waiting instead of being cancelled.           *)
(***************************************************************************)
CancelOrphan(t) ==
    /\ state[t] = "BLOCKED"
    /\ Doomed(t)
    /\ state' = [state EXCEPT ![t] = "CANCELED"]
    /\ UNCHANGED oracle

Next == \E t \in Tasks : Unblock(t) \/ Start(t) \/ Succeed(t) \/ Fail(t)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* PROPERTIES                                                              *)
(***************************************************************************)

HP10 ==
    \A t \in Tasks :
        state[t] \in {"IN_PROGRESS", "COMPLETED"} => \A p \in Deps[t] : state[p] = "COMPLETED"

\* The TL1 analogue across the whole graph: no task waits forever.
AllTerminate == <>(\A t \in Tasks : state[t] \in Terminal)

\* Nothing that reached a terminal state moves again.
TerminalIsFinal ==
    [][ \A t \in Tasks : state[t] \in Terminal => state'[t] = state[t] ]_vars

\* Failure containment: an orphan is cancelled, never run. The property this
\* variant breaks.
NoOrphanRuns ==
    \A t \in Tasks : Doomed(t) => state[t] \notin {"READY", "IN_PROGRESS", "COMPLETED"}

=============================================================================
