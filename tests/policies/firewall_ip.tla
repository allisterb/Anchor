---------------------------- MODULE firewall_ip ----------------------------
\* "Nothing from 10.0.0.0/8 is granted" -- the claim `firewall_ip.dw` is supposed to satisfy.
\*
\* Checked by property because it cannot be checked by replay: `dogwood replay` has no way to put
\* an address in a trace (its log parser has no case for an extension value), so the engine
\* silently allows what the policy says to forbid. The containment this rests on is differentially
\* tested against Python's `ipaddress` module instead -- a real oracle for the arithmetic, and the
\* honest limit of what can be claimed here.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Grants(input) == D!Decide(<<Request("Connect", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* The addresses this claim is about -- stated, not derived.               *)
(*                                                                         *)
(* Five, not 16.7 million. A policy comparing against a range partitions   *)
(* the address space into finitely many classes, so one representative per *)
(* class plus BOTH BOUNDARIES is what there is to learn; enumerating 10/8  *)
(* would take a very long time and add nothing. The boundaries are the     *)
(* point, because a range bug is an off-by-one or a wrong prefix length.   *)
(***************************************************************************)
Addresses == { Addr(9, 255, 255, 255),        \* just below
               Addr(10, 0, 0, 0),             \* first in range
               Addr(10, 127, 255, 255),       \* last of the lower half -- a /9 would stop here
               Addr(10, 255, 255, 255),       \* last in range
               Addr(11, 0, 0, 0) }            \* just above

Requests == {[src |-> a] : a \in Addresses}

VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

\* The claim, stated over the same containment the policy is evaluated with, so the property and
\* the evaluator cannot disagree about what "in range" means.
BlockedRangeIsRefused ==
    D!InRange(req.src.v, <<10, 0, 0, 0>>, 8) => ~Grants(req)

=============================================================================
