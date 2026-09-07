------------------------------- MODULE Workflow -------------------------------
(***************************************************************************)
(* The DAG under test, separated from the properties so it can be replaced. *)
(*                                                                          *)
(* DependencyDAG.tla EXTENDS this module, so the logic and the properties    *)
(* live in one place and only the shape of the graph changes. This version   *)
(* is hand-written; tests/strands/graph_to_tla.py emits the same two         *)
(* definitions from a live Strands Graph object, so a real workflow can be   *)
(* checked against the same properties without anyone rewriting them.        *)
(*                                                                          *)
(*        t1 ──┐                                                            *)
(*             ├──> t3 ──> t4                                               *)
(*        t2 ──┘                                                            *)
(*                                                                          *)
(* Deps[t] is the set t waits on. It must be acyclic: a cycle makes every    *)
(* task in it wait forever, which shows up as AllTerminate failing rather    *)
(* than as a separate check.                                                 *)
(***************************************************************************)

Tasks == {"t1", "t2", "t3", "t4"}

Deps ==
    [t \in Tasks |->
        CASE t = "t3" -> {"t1", "t2"}
          [] t = "t4" -> {"t3"}
          [] OTHER    -> {}]

=============================================================================
