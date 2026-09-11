---------------------------- MODULE DependencyDAG ----------------------------
(***************************************************************************)
(* HP10 from arXiv:2510.14133v2 Table 1 — the Orchestrator invokes a       *)
(* sub-task only once every one it depends on has completed.               *)
(*                                                                         *)
(*   AG( ∀i ∈ D : CL.invoke(EE, prot, sub_task_i)                          *)
(*                  → ∀p ∈ parents(sub_task_i) : Completed(p) )            *)
(*                                                                         *)
(* READINESS IS PER-EDGE, NOT PER-NODE.                                    *)
(*                                                                         *)
(* An earlier version of this model gated Unblock on                       *)
(* "\A p \in Deps[t] : Done(p)" — every parent complete. That is not what  *)
(* Strands does. Graph._is_node_ready_with_conditions returns TRUE on the  *)
(* FIRST incoming edge whose source is in the completed batch and whose    *)
(* condition passes, and GraphNode.dependencies is used only to find entry *)
(* points and to gather node inputs; it never gates execution. The SDK     *)
(* documents this: "In Python, the default behavior is OR semantics — a    *)
(* target node fires when any incoming edge's source completes. Use        *)
(* conditional edges to explicitly wait for all dependencies."             *)
(*                                                                         *)
(* Modelling it as AND made this spec describe a stricter orchestrator     *)
(* than the one that runs, which is the unsound direction: HP10 verified   *)
(* against a discipline nothing enforces. Unblock now takes the OR rule,   *)
(* and the AND is recovered where it actually lives — in EdgeCond, from    *)
(* the conditions a workflow author writes.                                *)
(*                                                                         *)
(* SIMPLIFICATION. TaskLifecycle.tla models one sub-task in full; this     *)
(* models several in outline, because HP10 is about the relation between   *)
(* tasks rather than the states within one. Retry, fallback and dispatch   *)
(* are therefore absent and FAILED is terminal here. Composing the two     *)
(* models is a separate exercise; this one would not fit in a checkable    *)
(* state space if each task carried the full eleven states.                *)
(*                                                                         *)
(* KNOWN GAP. The OR rule shows up a second way this model does not cover: *)
(* Strands admits a node once per satisfied incoming edge, so it can run   *)
(* more than once. On A→B, B→C, A→C the observed execution_order contains  *)
(* C twice — once off the A edge, once off the B edge. Where B and the     *)
(* first C fall relative to each other varies run to run, because the      *)
(* batch executes concurrently; the repeat does not vary. COMPLETED is     *)
(* terminal here, so that second C is outside the model. Re-execution      *)
(* needs its own spec; TerminalIsFinal below is a property of THIS model,  *)
(* not a claim about the SDK.                                              *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Workflow

States == {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELED"}
Terminal == {"COMPLETED", "FAILED", "CANCELED"}

VARIABLES
    state,           \* [Tasks -> States]
    oracle           \* [NondetEdges -> BOOLEAN] -- see below

vars == <<state, oracle>>

(***************************************************************************)
(* EDGES WHOSE CONDITION HAS NO DECLARED MEANING.                          *)
(*                                                                         *)
(* Workflow.tla lists these in NondetEdges. Their conditions are opaque    *)
(* Python, so their truth is not a function of anything this model holds,  *)
(* and `oracle` stands in for whatever they decide. It is chosen freely in *)
(* Init and never changes, so TLC explores the workflow once per           *)
(* combination — including the run in which an edge never fires.           *)
(*                                                                         *)
(* What that buys: a property that survives every combination holds        *)
(* WHATEVER the conditions decide, with nothing about them translated and  *)
(* so nothing to mistranslate. What it costs: precision. A property that   *)
(* depends on what a condition actually does cannot be established this    *)
(* way, and TLC will report the combination that breaks it.                *)
(*                                                                         *)
(* THE ABSTRACTION IS "UNKNOWN BUT FIXED", AND THAT IS A REAL LIMIT. A     *)
(* condition whose answer changes as the run progresses -- one reading     *)
(* accumulated results, say -- is not covered, because oracle cannot flip  *)
(* mid-behaviour. Fixing it per behaviour is what lets EdgeDead recognise  *)
(* an edge that will never fire, which is what lets an orphaned task be    *)
(* cancelled rather than waiting forever. A time-varying condition needs a *)
(* real predicate (tier 0 or tier 1), not this.                            *)
(*                                                                         *)
(* When NondetEdges is empty -- every graph checked before tier 2 --       *)
(* [NondetEdges -> BOOLEAN] holds exactly one function, so Init has one    *)
(* oracle value and nothing about those checks changes.                    *)
(***************************************************************************)

TypeOK == /\ state \in [Tasks -> States]
          /\ oracle \in [NondetEdges -> BOOLEAN]

Init == /\ state = [t \in Tasks |-> "BLOCKED"]
        /\ oracle \in [NondetEdges -> BOOLEAN]

Done(t) == state[t] = "COMPLETED"

\* The parent set HP10 is stated over. Derived from Edges rather than declared
\* alongside it, so the graph and the thing the property quantifies over cannot
\* drift apart.
Deps == [t \in Tasks |-> {p \in Tasks : <<p, t>> \in Edges}]

\* A task with no incoming edge. Nothing has to fire for it to run.
Entry(t) == Deps[t] = {}

(***************************************************************************)
(* EDGES                                                                   *)
(***************************************************************************)

\* Whether an edge's condition passes. A declared condition is a predicate over the
\* state; an undeclared one is whatever `oracle` says for this behaviour.
Traversable(p, t) ==
    IF <<p, t>> \in NondetEdges THEN oracle[<<p, t>>] ELSE EdgeCond(p, t, state)

\* An incoming edge that would admit t right now: its source has completed and
\* its condition holds. ONE of these is enough — that is the OR rule.
CanFire(p, t) ==
    /\ <<p, t>> \in Edges
    /\ Done(p)
    /\ Traversable(p, t)

\* An incoming edge that can never fire again. Two ways for that:
\*
\*   - the source reached a terminal state other than COMPLETED, so it will
\*     never complete; or
\*   - the source completed but the condition is false, and every task the
\*     condition reads has already settled, so no later move can make it true.
\*
\* The second case is why Workflow.tla has to supply EdgeSupport. Without it the
\* model would have to guess whether a currently-false condition might yet flip,
\* and either guess is wrong: assume it can and a guarded join can never be
\* cancelled, assume it cannot and a live task gets cancelled while one of its
\* dependencies is still running.
\* A nondeterministic edge has empty support and a fixed oracle, so this reduces to
\* "the source completed and the oracle said no" — which is exactly right: under the
\* unknown-but-fixed abstraction that edge will never fire in this behaviour.
EdgeDead(p, t) ==
    \/ state[p] \in {"FAILED", "CANCELED"}
    \/ /\ Done(p)
       /\ ~Traversable(p, t)
       /\ \A n \in EdgeSupport(p, t) : state[n] \in Terminal

\* No incoming edge can ever admit t. Entry points are never doomed.
Doomed(t) ==
    /\ ~Entry(t)
    /\ \A p \in Deps[t] : EdgeDead(p, t)

(***************************************************************************)
(* TRANSITIONS                                                             *)
(***************************************************************************)

\* The OR rule: an entry point is runnable at once, and any other task becomes
\* runnable as soon as ONE incoming edge fires. A join that must wait for all of
\* its parents says so in EdgeCond.
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
(* Failure propagation, and why it has to exist.                           *)
(*                                                                         *)
(* A task all of whose incoming edges are dead never runs — and, with      *)
(* nothing else to move it, never terminates either, which breaks TL1.     *)
(* HP10 and TL1 together force the orchestrator to cancel the orphaned     *)
(* subgraph rather than leave it waiting.                                  *)
(*                                                                         *)
(* The paper gestures at this — "the Orchestrator enforces causal          *)
(* isolation and failure containment ... a sub-task does not proceed if    *)
(* any dependency is FAILED" — but "does not proceed" is only half of it.  *)
(* Not proceeding satisfies HP10 and violates TL1. Bug5 is that half.      *)
(*                                                                         *)
(* Under the OR rule this obligation is narrower than it was under AND. A  *)
(* failed parent no longer strands its children on its own: another edge   *)
(* may still admit them. Only a task with no surviving edge is an orphan.  *)
(***************************************************************************)
CancelOrphan(t) ==
    /\ state[t] = "BLOCKED"
    /\ Doomed(t)
    /\ state' = [state EXCEPT ![t] = "CANCELED"]
    /\ UNCHANGED oracle

Next == \E t \in Tasks : Unblock(t) \/ Start(t) \/ Succeed(t) \/ Fail(t) \/ CancelOrphan(t)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* PROPERTIES                                                              *)
(***************************************************************************)

\* HP10 itself. Stated over IN_PROGRESS and COMPLETED rather than over the
\* invoke action, because COMPLETED is reachable only through IN_PROGRESS and an
\* invariant over states is what TLC checks directly.
\*
\* Note what this now checks. Under the old AND gate HP10 was a restatement of
\* Unblock and could not fail. Under the OR gate it is a real obligation on the
\* workflow: it holds only if every join carries a condition strong enough to
\* enforce it.
HP10 ==
    \A t \in Tasks :
        state[t] \in {"IN_PROGRESS", "COMPLETED"} => \A p \in Deps[t] : state[p] = "COMPLETED"

\* The TL1 analogue across the whole graph: no task waits forever.
AllTerminate == <>(\A t \in Tasks : state[t] \in Terminal)

\* Nothing that reached a terminal state moves again.
TerminalIsFinal ==
    [][ \A t \in Tasks : state[t] \in Terminal => state'[t] = state[t] ]_vars

\* Failure containment: an orphan is cancelled, never run. The property Bug5
\* breaks.
NoOrphanRuns ==
    \A t \in Tasks : Doomed(t) => state[t] \notin {"READY", "IN_PROGRESS", "COMPLETED"}

=============================================================================
