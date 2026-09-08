------------------------------- MODULE Workflow -------------------------------
(***************************************************************************)
(* The workflow under test, separated from the properties so it can be      *)
(* replaced. DependencyDAG.tla EXTENDS this module, so the transition logic  *)
(* and the properties live in one place and only the graph changes. This     *)
(* version is hand-written; tests/strands/graph_to_tla.py emits the same     *)
(* definitions from a live Strands Graph object.                            *)
(*                                                                          *)
(*        t1 ──┐                                                            *)
(*             ├──> t3 ──> t4                                               *)
(*        t2 ──┘                                                            *)
(*                                                                          *)
(* FOUR definitions, because readiness in Strands is decided per EDGE, not   *)
(* per node. An earlier version of this module emitted `Tasks` and a `Deps`  *)
(* AND-set, which described a stricter orchestrator than the one that runs.  *)
(* See the header of DependencyDAG.tla.                                      *)
(*                                                                          *)
(*   Tasks        the nodes.                                                *)
(*   Edges        the edges, as <<from, to>> pairs. The parent set HP10 is   *)
(*                stated over is derived from this, not declared separately, *)
(*                so the two cannot disagree.                               *)
(*   EdgeCond     each edge's traversal condition, TRUE where the edge is    *)
(*                unconditional. State is a parameter rather than a free     *)
(*                variable because this module is EXTENDed by the one that   *)
(*                declares VARIABLE state, so it cannot see it.             *)
(*   EdgeSupport  the tasks each condition reads. Lets the model decide when *)
(*                a false condition can no longer become true — see          *)
(*                EdgeDead. A support set that omits a task the condition    *)
(*                really reads would let the model declare an edge dead too  *)
(*                early, so this is part of what a translation must get      *)
(*                right, and part of what a differential test must check.    *)
(*                                                                          *)
(* The graph must be acyclic: a cycle makes every task in it wait forever,   *)
(* which shows up as AllTerminate failing rather than as a separate check.   *)
(***************************************************************************)

Tasks == {"t1", "t2", "t3", "t4"}

Edges == {<<"t1", "t3">>, <<"t2", "t3">>, <<"t3", "t4">>}

(***************************************************************************)
(* THE JOIN INTO t3 IS GUARDED, AND HAS TO BE.                              *)
(*                                                                          *)
(* Strands' default is OR: without a condition t3 starts as soon as EITHER   *)
(* t1 or t2 completes, and HP10 is violated. These two arms are what         *)
(* `all_dependencies_complete(["t1", "t2"])` means — the factory the Strands *)
(* graph documentation tells users to write when they want AND semantics.    *)
(* Delete either arm and HP10 fails; tests/strands/graph_to_tla.py checks    *)
(* an unguarded graph and reports exactly that.                             *)
(***************************************************************************)
AllComplete(ns, st) == \A n \in ns : st[n] = "COMPLETED"

EdgeCond(from, to, st) ==
    CASE <<from, to>> = <<"t1", "t3">> -> AllComplete({"t1", "t2"}, st)
      [] <<from, to>> = <<"t2", "t3">> -> AllComplete({"t1", "t2"}, st)
      [] OTHER                         -> TRUE

EdgeSupport(from, to) ==
    CASE <<from, to>> = <<"t1", "t3">> -> {"t1", "t2"}
      [] <<from, to>> = <<"t2", "t3">> -> {"t1", "t2"}
      [] OTHER                         -> {}

\* Edges whose condition has no declared meaning, modelled as an unknown-but-fixed
\* choice rather than translated. Every condition here is a combinator, so there
\* are none; see the header of DependencyDAG.tla for what this does when there are.
NondetEdges == {}

=============================================================================
