---------------------------- MODULE BusinessHours ----------------------------
\* What agent-policy.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
\*
\* SAVE THIS AS BusinessHours.tla -- TLA+ requires the file name to match the module name, and a
\* module name may not contain `-` or `.` or begin with a digit, so it is not always the policy's
\* own name.
\*
\* Check it with:  python src/checker/properties.py agent-policy.dw --property BusinessHours.tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\* The verdict for issuing a refund. No session: "what does this policy decide for this request" is
\* not a temporal question, so there is no state machine beyond holding one request still.
RefundGranted(input) == D!Decide(<<Request("issue_refund", input)>>, Policies, 1, AllValues)

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
accountValues == {Num(1), Num(2)}
amountValues == {Num(499), Num(500), Num(2500), Num(2501)}
charge_idValues == {Num(1), Num(2)}
systemNowTimeValues == {Num(32399999), Num(32400000), Num(61200000), Num(61200001)}

Requests == {[account |-> account, amount |-> amount, charge_id |-> charge_id, systemNowTime |-> systemNowTime] : account \in accountValues, amount \in amountValues, charge_id \in charge_idValues, systemNowTime \in systemNowTimeValues}

\* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
\* request that breaks the claim rather than merely reporting that one exists.
VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* CONSTANTS AND HELPERS FOR THE CLAIM.                                    *)
(***************************************************************************)
\* Business hours are 9:00 AM - 5:00 PM UTC
MinBusinessHour == Num(32400) \* 9 * 3600 seconds from midnight
MaxBusinessHour == Num(61200) \* 17 * 3600 seconds from midnight

\* Maximum allowed refund amount
MaxRefundAmount == Num(2500)

IsDuringBusinessHours(time) == (time >= MinBusinessHour) /\ (time <= MaxBusinessHour)
IsAllowedAmount(amount) == (amount <= MaxRefundAmount)

(***************************************************************************)
(* THE CLAIM.                                                              *)
(***************************************************************************)
\* Refunds might be issued only during business hours (9:00 AM-5:00 PM UTC)
\* and only for amounts of $2,500 or less.
RefundsOnlyDuringBusinessHoursAndLimit ==
    RefundGranted(req) => (IsDuringBusinessHours(req.systemNowTime) /\ IsAllowedAmount(req.amount))

=============================================================================
