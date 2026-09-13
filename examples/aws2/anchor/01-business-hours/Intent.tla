---------------------------- MODULE Intent ----------------------------
\* What 01-business-hours.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\* The verdict for one request. No session: "what does this policy decide for this request" is
\* not a temporal question, so there is no state machine beyond holding one request still.
Grants(input) == D!Decide(<<Request("issue_refund", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* CONSTANTS FOR BUSINESS LOGIC                                            *)
(*                                                                         *)
(* Business hours are 9:00 AM - 5:00 PM UTC. Times are in seconds from     *)
(* midnight UTC.                                                           *)
(***************************************************************************)
NineAM == Num(9 * 3600)    \* 32400 seconds
FivePM == Num(17 * 3600)   \* 61200 seconds
MaxRefundAmount == Num(2500)

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
\* Values for amount, covering less than, equal to, and greater than the limit
amountValues == {Num(1), Num(2499), Num(2500), Num(2501), Num(10000)}

\* Values for systemNowTime, covering times before, at, and after business hours boundaries
systemNowTimeValues == {
    Num(0), Num(32399), NineAM, Num(32401), \* Before, at, and just after 9 AM
    Num(45000),                              \* Middle of business hours
    Num(61199), FivePM, Num(61201), Num(86399) \* Just before, at, and after 5 PM, and end of day
}

Requests == {[amount |-> amount, systemNowTime |-> systemNowTime] : amount \in amountValues, systemNowTime \in systemNowTimeValues}

\* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
\* request that breaks the claim rather than merely reporting that one exists.
VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* THE CLAIM.                                                              *)
(*                                                                         *)
(* Refunds might be issued only during business hours (9:00 AM-5:00 PM UTC)*)
(* and only for amounts of $2,500 or less.                                 *)
(***************************************************************************)

\* Claim 1: Refunds for amounts greater than $2,500 must be denied.
AmountTooHighIsDenied == (req.amount > MaxRefundAmount) => ~Grants(req)

\* Claim 2: Refunds outside business hours must be denied.
OutsideBusinessHoursIsDenied == ((req.systemNowTime < NineAM) \/ (req.systemNowTime > FivePM)) => ~Grants(req)

=============================================================================
