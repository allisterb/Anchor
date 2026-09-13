---------------------------- MODULE Intent ----------------------------
\* What firewall.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
\*
\* SAVE THIS AS Intent.tla -- TLA+ requires the file name to match the module name, and a
\* module name may not contain `-` or `.` or begin with a digit, so it is not always the policy's
\* own name.
\*
\* Check it with:  python src/checker/properties.py firewall.dw --property Intent.tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\* The verdict for one request. No session: "what does this policy decide for this request" is
\* not a temporal question, so there is no state machine beyond holding one request still.
Grants(input) == D!Decide(<<Request("Connect", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
(*                                                                         *)
(* Written out rather than derived from InputDomain, and that is the       *)
(* point. A space derived from the policy's own literals cannot test a     *)
(* claim about a value the policy never mentions: delete the rule that     *)
(* names a value and it vanishes from the vocabulary, so the claim ranges  *)
(* over nothing and PASSES having looked at nothing.                       *)
(*                                                                         *)
(* Add the values your claim is about, including ones this policy never    *)
(* mentions.                                                               *)
(***************************************************************************)
originValues == {Str("external"), Str("local")}
portValues == {Num(21), Num(22), Num(23)}

Requests == {[origin |-> origin, port |-> port] : origin \in originValues, port \in portValues}

\* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
\* request that breaks the claim rather than merely reporting that one exists.
VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* THE CLAIM.                                                              *)
(***************************************************************************)
\* Intention: SSH from the local range is permitted, and every external source is denied.

\* SSH from the local range is permitted
SshFromLocalIsPermitted == (req.port = Num(22) /\ req.origin = Str("local")) => Grants(req)

\* Every external source is denied
ExternalIsDenied == (req.origin = Str("external")) => ~Grants(req)

=============================================================================
