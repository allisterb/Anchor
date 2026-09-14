---------------------------- MODULE BusinessHours ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

GrantsRefund(input) == D!Decide(<<Request("issue_refund", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
(***************************************************************************)
accountValues == {Num(1), Num(2)}
amountValues == {Num(499), Num(500), Num(2500), Num(2501)}
charge_idValues == {Num(1), Num(2)}
systemNowTimeValues == {Num(32399999), Num(32400000), Num(61200000), Num(61200001)}

Requests == {[account |-> account, amount |-> amount, charge_id |-> charge_id, systemNowTime |-> systemNowTime] :
             account \in accountValues,
             amount \in amountValues,
             charge_id \in charge_idValues,
             systemNowTime \in systemNowTimeValues}

VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* DOMAINS FOR BUSINESS HOURS AND ALLOWED AMOUNTS.                         *)
(* 9:00 AM UTC = 32,400,000 ms, 5:00 PM UTC = 61,200,000 ms                *)
(* Max refund amount = $2,500                                              *)
(***************************************************************************)
BusinessHoursValues == {Num(32400000), Num(61200000)}
AllowedAmounts      == {Num(499), Num(500), Num(2500)}

(***************************************************************************)
(* THE CLAIMS.                                                             *)
(***************************************************************************)
RefundsOnlyDuringBusinessHoursAndWithinLimit ==
  GrantsRefund(req) => (req.systemNowTime \in BusinessHoursValues /\ req.amount \in AllowedAmounts)

OutsideBusinessHoursRefused ==
  req.systemNowTime \notin BusinessHoursValues => ~GrantsRefund(req)

OverLimitRefused ==
  req.amount \notin AllowedAmounts => ~GrantsRefund(req)

=============================================================================
