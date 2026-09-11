----------------------------- MODULE StrandsGraph -----------------------------
(***************************************************************************)
(* The Strands graph executor as it actually runs, rather than as the      *)
(* orchestrator a paper would specify.                                     *)
(*                                                                         *)
(* WHY THIS EXISTS SEPARATELY FROM DependencyDAG.tla. That model is the    *)
(* Host Agent of arXiv:2510.14133 — it cancels an orphaned subgraph, and   *)
(* AllTerminate says every task reaches a terminal state. Strands does     *)
(* neither. It has no CANCELED status, it fail-fasts the whole run when a  *)
(* node raises, and when nothing is ready it simply STOPS, leaving         *)
(* whatever was never admitted unrun and reporting success. Modelling both *)
(* orchestrators in one file would mean checking properties of a system    *)
(* nobody is running; this one is checked against the SDK's own loop.      *)
(*                                                                         *)
(* THE LOOP, from Graph._execute_graph:                                    *)
(*                                                                         *)
(*     while ready_nodes:                                                  *)
(*         current_batch = ready_nodes.copy()                              *)
(*         ready_nodes.clear()                                             *)
(*         await self._execute_nodes_parallel(current_batch, ...)          *)
(*         newly_ready = self._find_newly_ready_nodes(current_batch)       *)
(*         ready_nodes.extend(newly_ready)                                 *)
(*                                                                         *)
(* Three consequences the DependencyDAG model structurally cannot state,   *)
(* each of which this one checks:                                          *)
(*                                                                         *)
(*   NoSilentSkip   the loop ends when ready_nodes empties, so a node      *)
(*                  whose conditions never pass is never run and the run   *)
(*                  still reports success. Probed: a two-branch router     *)
(*                  reports COMPLETED having run 2 of 3 nodes.             *)
(*   RunsAtMostOnce readiness is recomputed per completed batch, so a node *)
(*                  reachable by two edges that complete in different      *)
(*                  batches is admitted TWICE. Probed on A->B, B->C, A->C: *)
(*                  execution_order contains C twice.                      *)
(*   HP10           the same OR-readiness obligation DependencyDAG checks, *)
(*                  restated here so the two models can be compared on one *)
(*                  workflow.                                              *)
(*                                                                         *)
(* THE STATUS VOCABULARY IS THE SDK'S, not the paper's. Status has no      *)
(* CANCELED, because Strands has none. UNRUN covers both "not reached yet" *)
(* and "never will be" — the executor does not distinguish them, and       *)
(* neither does this model.                                                *)
(*                                                                         *)
(* Workflow.tla is shared with DependencyDAG unchanged. That works because *)
(* a condition can only observe the two statuses the SDK writes into       *)
(* state.results — COMPLETED and FAILED — and those are spelled the same   *)
(* in both models.                                                         *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Workflow

CONSTANT MaxRuns        \* bound on admissions per task; see RunsAtMostOnce

ASSUME MaxRunsAssumption == MaxRuns \in Nat /\ MaxRuns > 0

Status == {"UNRUN", "RUNNING", "COMPLETED", "FAILED"}

VARIABLES
    status,     \* [Tasks -> Status]
    runs,       \* [Tasks -> Nat] -- how many times each task has been admitted
    ready,      \* queued for the next batch
    batch,      \* executing right now
    phase,      \* "RUNNING" | "DONE" | "ABORTED"
    oracle      \* [NondetEdges -> BOOLEAN], as in DependencyDAG.tla

vars == <<status, runs, ready, batch, phase, oracle>>

\* The parent set, derived from Edges so it cannot disagree with the graph.
\* Named as in the CommunityModules Graphs module, where this is Predecessors(G, t).
Parents(t) == {p \in Tasks : <<p, t>> \in Edges}

\* Tasks with no incoming edge. Graphs would call these Roots(G); Strands seeds
\* ready_nodes with them, via GraphBuilder's entry-point detection.
Entry == {t \in Tasks : Parents(t) = {}}

TypeOK ==
    /\ status \in [Tasks -> Status]
    /\ runs \in [Tasks -> 0..MaxRuns]
    /\ ready \subseteq Tasks
    /\ batch \subseteq Tasks
    /\ phase \in {"RUNNING", "DONE", "ABORTED"}
    /\ oracle \in [NondetEdges -> BOOLEAN]

Init ==
    /\ status = [t \in Tasks |-> "UNRUN"]
    /\ runs = [t \in Tasks |-> 0]
    /\ ready = Entry
    /\ batch = {}
    /\ phase = "RUNNING"
    /\ oracle \in [NondetEdges -> BOOLEAN]

(***************************************************************************)
(* EDGES                                                                   *)
(*                                                                         *)
(* Evaluated against a status function passed in, because readiness is     *)
(* computed AFTER a batch finishes and so must see the new statuses.       *)
(***************************************************************************)
Traversable(p, t, st) ==
    IF <<p, t>> \in NondetEdges THEN oracle[<<p, t>>] ELSE EdgeCond(p, t, st)

\* _find_newly_ready_nodes: the targets of edges out of the batch that just
\* completed, keeping those with at least one satisfied incoming edge FROM THAT
\* BATCH. The restriction to the batch is what makes a node admissible more than
\* once — an edge that fired in an earlier batch does not disqualify a later one.
NewlyReady(done, st) ==
    { t \in Tasks :
        \E p \in done : /\ <<p, t>> \in Edges
                        /\ st[p] = "COMPLETED"
                        /\ Traversable(p, t, st) }

(***************************************************************************)
(* TRANSITIONS                                                             *)
(***************************************************************************)

\* current_batch = ready_nodes.copy(); ready_nodes.clear()
StartBatch ==
    /\ phase = "RUNNING"
    /\ batch = {}
    /\ ready # {}
    /\ batch' = ready
    /\ ready' = {}
    /\ status' = [t \in Tasks |-> IF t \in ready THEN "RUNNING" ELSE status[t]]
    /\ runs' = [t \in Tasks |-> IF t \in ready THEN runs[t] + 1 ELSE runs[t]]
    /\ UNCHANGED <<phase, oracle>>

\* The batch runs to completion, then readiness is recomputed. Which nodes fail
\* is not modelled -- every subset of the batch is a behaviour, including none
\* and all, so the properties hold whatever the agents do.
\*
\* Any failure aborts the whole run: _execute_nodes_parallel cancels the
\* remaining tasks and re-raises, so there is no partial continuation and no
\* cancellation of the subgraph below. Fail-fast, not failure propagation.
FinishBatch(failed) ==
    /\ phase = "RUNNING"
    /\ batch # {}
    /\ failed \subseteq batch
    /\ LET st == [t \in Tasks |-> IF t \in batch
                                  THEN IF t \in failed THEN "FAILED" ELSE "COMPLETED"
                                  ELSE status[t]]
       IN /\ status' = st
          /\ IF failed # {}
             THEN /\ phase' = "ABORTED"
                  /\ ready' = {}
             ELSE /\ phase' = "RUNNING"
                  /\ ready' = NewlyReady(batch, st)
    /\ batch' = {}
    /\ UNCHANGED <<runs, oracle>>

\* while ready_nodes: falls through. The run ends HERE, with no check that
\* anything was left unrun -- which is the whole of NoSilentSkip.
EndRun ==
    /\ phase = "RUNNING"
    /\ batch = {}
    /\ ready = {}
    /\ phase' = "DONE"
    /\ UNCHANGED <<status, runs, ready, batch, oracle>>

Next ==
    \/ StartBatch
    \/ \E failed \in SUBSET batch : FinishBatch(failed)
    \/ EndRun

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* PROPERTIES                                                              *)
(***************************************************************************)

\* THE ONE THIS MODEL EXISTS FOR. The executor reported success, and something
\* never ran. No error, no warning, no record in state.results -- the node is
\* simply absent from a run that looks like it worked.
NoSilentSkip == phase = "DONE" => \A t \in Tasks : status[t] # "UNRUN"

\* HP10, restated over this model's vocabulary so one workflow can be checked
\* against both. A task runs only once every parent has completed.
HP10 ==
    \A t \in Tasks :
        status[t] \in {"RUNNING", "COMPLETED"} => \A p \in Parents(t) : status[p] = "COMPLETED"

\* An agent admitted twice is invoked twice -- charged twice, and its output
\* recomputed. Nothing in the executor prevents it.
RunsAtMostOnce == \A t \in Tasks : runs[t] <= 1

\* The loop always leaves, one way or the other. Weaker than DependencyDAG's
\* AllTerminate on purpose: this says the RUN ends, not that the tasks did.
Terminates == <>(phase \in {"DONE", "ABORTED"})

=============================================================================
