---------------------------- MODULE Bug5_NoFailurePropagation ----------------------------
(***************************************************************************)
(* DependencyDAG with failure propagation removed: CancelOrphan is gone    *)
(* from Next, so a task whose dependency failed simply waits.              *)
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
(* SIMPLIFICATION. TaskLifecycle.tla models one sub-task in full; this     *)
(* models several in outline, because HP10 is about the relation between   *)
(* tasks rather than the states within one. Retry, fallback and dispatch   *)
(* are therefore absent and FAILED is terminal here. Composing the two     *)
(* models is a separate exercise; this one would not fit in a checkable    *)
(* state space if each task carried the full eleven states.                *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Workflow

States == {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELED"}
Terminal == {"COMPLETED", "FAILED", "CANCELED"}

VARIABLE state       \* [Tasks -> States]

vars == <<state>>

TypeOK == state \in [Tasks -> States]

Init == state = [t \in Tasks |-> "BLOCKED"]

Done(t) == state[t] = "COMPLETED"

\* A dependency that failed or was cancelled will never complete, so anything
\* waiting on it can never become READY.
Doomed(t) == \E p \in Deps[t] : state[p] \in {"FAILED", "CANCELED"}

(***************************************************************************)
(* TRANSITIONS                                                             *)
(***************************************************************************)

\* The HP10 gate: a task becomes runnable only once every parent is COMPLETED.
Unblock(t) ==
    /\ state[t] = "BLOCKED"
    /\ \A p \in Deps[t] : Done(p)
    /\ state' = [state EXCEPT ![t] = "READY"]

Start(t) ==
    /\ state[t] = "READY"
    /\ state' = [state EXCEPT ![t] = "IN_PROGRESS"]

Succeed(t) ==
    /\ state[t] = "IN_PROGRESS"
    /\ state' = [state EXCEPT ![t] = "COMPLETED"]

Fail(t) ==
    /\ state[t] = "IN_PROGRESS"
    /\ state' = [state EXCEPT ![t] = "FAILED"]

(***************************************************************************)
(* Failure propagation, and why it has to exist.                           *)
(*                                                                         *)
(* HP10 admits a task into IN_PROGRESS only when all its parents COMPLETED.*)
(* A task whose parent FAILED therefore never runs — and, with nothing     *)
(* else to move it, never terminates either, which breaks TL1. HP10 and    *)
(* TL1 together force the orchestrator to cancel the orphaned subgraph     *)
(* rather than leave it waiting.                                           *)
(*                                                                         *)
(* The paper gestures at this — "the Orchestrator enforces causal          *)
(* isolation and failure containment ... a sub-task does not proceed if    *)
(* any dependency is FAILED" — but "does not proceed" is only half of it.  *)
(* Not proceeding satisfies HP10 and violates TL1. Bug5 is that half.      *)
(***************************************************************************)
CancelOrphan(t) ==
    /\ state[t] = "BLOCKED"
    /\ Doomed(t)
    /\ state' = [state EXCEPT ![t] = "CANCELED"]

Next == \E t \in Tasks : Unblock(t) \/ Start(t) \/ Succeed(t) \/ Fail(t)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* PROPERTIES                                                              *)
(***************************************************************************)

\* HP10 itself. Stated over IN_PROGRESS and COMPLETED rather than over the
\* invoke action, because COMPLETED is reachable only through IN_PROGRESS and
\* an invariant over states is what TLC checks directly.
HP10 ==
    \A t \in Tasks :
        state[t] \in {"IN_PROGRESS", "COMPLETED"} => \A p \in Deps[t] : state[p] = "COMPLETED"

\* The TL1 analogue across the whole graph: no task waits forever.
AllTerminate == <>(\A t \in Tasks : state[t] \in Terminal)

\* Nothing that reached a terminal state moves again.
TerminalIsFinal ==
    [][ \A t \in Tasks : state[t] \in Terminal => state'[t] = state[t] ]_vars

\* Failure containment: an orphan is cancelled, never run. The contrapositive of
\* HP10 restricted to the failure case, and the property Bug5 breaks.
NoOrphanRuns ==
    \A t \in Tasks : Doomed(t) => state[t] \notin {"READY", "IN_PROGRESS", "COMPLETED"}

=============================================================================
