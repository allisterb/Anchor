------------------------------- MODULE HourClock -------------------------------

(***************************************************************************)
(* Spec of the Caesar algorithm, based on my interpretation of Balaji's    *)
(* pseudo-code.  The spec does not include crash-recovery.  We assume that *)
(* all commandes conflict (no commands commute).                           *)
(*                                                                         *)
(* We do not model the network.  Instead the processes can read each       *)
(* others private state directly.                                          *)
(***************************************************************************)


(***************************************************************************)
(* It seems to me that we can express Caesar in the framework of the BA    *)
(* using the same algorithm merging technique as for EPaxos.  Only phase 1 *)
(* is a little different with the waiting.                                 *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets, TLC


=============================================================================
\* Modification History
\* Last modified Tue Mar 08 18:10:51 EST 2016 by nano
\* Created Mon Mar 07 11:08:24 EST 2016 by nano

