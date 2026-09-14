---------------------------- MODULE BusinessHours ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(*
The verdict for one request. No session: "what does this policy decide for this request" is
not a temporal question, so there is no state machine beyond holding one request still.
This Grants operator is specifically for the 'issue_refund' action.
*)
Grants(input) == D!Decide(<<Request("issue_refund", input)>>, Policies, 1, AllValues)

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
(* These systemNowTime values cover boundaries of business hours effectively *)
systemNowTimeValues == {Num(32399999), Num(32400000), Num(61200000), Num(61200001)}

Requests ==
  {[account |-> account, amount |-> amount,
    charge_id |-> charge_id, systemNowTime |-> systemNowTime]
    : account \in accountValues, amount \in amountValues,
      charge_id \in charge_idValues, systemNowTime \in systemNowTimeValues}

(* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
   request that breaks the claim rather than merely reporting that one exists. *)
VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* THE CLAIMS.                                                             *)
(*                                                                         *)
(* Refunds might be issued only during business hours, defined as 9:00 AM-5:00 PM UTC, *)
(* and only for amounts of $2,500 or less.                                 *)
(***************************************************************************)
BusinessHourStart == Num(9 * 3600 * 1000)   (* 9:00 AM UTC in milliseconds (32400000) *)
BusinessHourEnd   == Num(17 * 3600 * 1000)  (* 5:00 PM UTC in milliseconds (61200000) *)
AmountLimit       == Num(2500)

(* Claim 1: Refunds that meet all conditions (within business hours, within amount limit) should be permitted. *)
RefundsWithinBusinessHoursAndLimitArePermitted ==
  (req.amount <= AmountLimit) /\
  (req.systemNowTime >= BusinessHourStart) /\
  (req.systemNowTime <= BusinessHourEnd) =>
  Grants(req)

(* Claim 2: Refunds outside business hours should be forbidden. *)
RefundsOutsideBusinessHoursAreForbidden ==
  ((req.systemNowTime < BusinessHourStart) \/ (req.systemNowTime > BusinessHourEnd)) =>
  ~Grants(req)

(* Claim 3: Refunds for amounts greater than $2,500 should be forbidden. *)
RefundsAboveLimitAreForbidden ==
  (req.amount > AmountLimit) =>
  ~Grants(req)

=============================================================================
