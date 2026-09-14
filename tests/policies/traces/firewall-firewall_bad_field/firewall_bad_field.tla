---------------------------- MODULE firewall_bad_field ----------------------------
\* What `firewall.dw` is SUPPOSED to mean, stated by its author and checked against the same
\* records the built-in questions are checked against.
\*
\* The three built-ins -- VACUOUS, REDUNDANT/DEAD, and diff -- are the claims statable without
\* knowing intent. They would all pass a policy that let the whole internet in, because "every rule
\* fires and none is redundant" is true of that policy too. This is the other kind, and only the
\* author can write it.
\*
\* Extends the GENERATED module, not Vacuity.tla. There is no session to explore: "what does this
\* policy decide for this request" is not a temporal question, so there is no state machine beyond
\* holding one request still while the claim is evaluated against it.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Grants(input) == D!Decide(<<Request("Connect", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT, stated here rather than derived.      *)
(*                                                                         *)
(* PolicyUnderTest deliberately does not offer an `Inputs`. A request      *)
(* space derived from the policy's own literals cannot test a claim about  *)
(* a value the policy never mentions -- drop the `forbid` from firewall.dw *)
(* and "external" vanishes from the vocabulary, so `OutsideIsRefused`      *)
(* ranges over nothing and passes. It reports success having looked at     *)
(* nothing, which is worse than failing.                                   *)
(*                                                                         *)
(* Naming them here is two lines and it is what makes the claim real.      *)
(***************************************************************************)
Origins == {"local", "external"}
Ports   == {22, 2222}

Requests == {[port |-> Num(p), origin |-> Str(o)] : p \in Ports, o \in Origins}

\* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
\* request that breaks the claim rather than merely reporting that one exists.
VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* THE CLAIM.                                                              *)
(***************************************************************************)
\* Selects a field no request record has. SANY resolves NAMES, not record fields, so this
\* compiles cleanly and dies at evaluation -- which is the case this fixture exists for.
LocalSshIsAllowed ==
    (req.nosuchfield = Num(22) /\ req.origin = Str("local")) => Grants(req)

OutsideIsRefused ==
    (req.origin = Str("external")) => ~Grants(req)

=============================================================================
