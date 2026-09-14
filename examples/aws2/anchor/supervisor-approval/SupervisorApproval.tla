---------------------------- MODULE SupervisorApproval ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

AmountsOver500 == {Num(2500), Num(2501)}
AmountsUnderOrEqualTo500 == {Num(499), Num(500)}
AmountValues == AmountsUnderOrEqualTo500 \cup AmountsOver500
ChargeIdValues == {Num(1), Num(2)}
GapValues == {10 * Minute, 30 * Minute, 45 * Minute}

VARIABLE amount, gap, hasApproval, isApproved, approvalChargeId, refundChargeId
vars == << amount, gap, hasApproval, isApproved, approvalChargeId, refundChargeId >>

InputRec(acc, amt, cid, timeVal) ==
  [account |-> acc, amount |-> amt, charge_id |-> cid, systemNowTime |-> timeVal]

OutputRec(app, ver) ==
  [approved |-> Bool(app), verified |-> Bool(ver)]

VerifyInput == InputRec(Num(1), Num(500), Num(1), Num(32400000))
VerifyOutput == OutputRec(FALSE, TRUE)

ApprovalInput(cid, amt) == InputRec(Num(1), amt, cid, Num(32400000))
ApprovalOutput(app) == OutputRec(app, FALSE)

RefundInput(cid, amt) == InputRec(Num(1), amt, cid, Num(32400000))
RefundOutput == OutputRec(FALSE, FALSE)

VerifyEvent ==
  Ev("verify_identity", "response", VerifyInput, VerifyOutput, 1)

ApprovalEvent(cid, amt, app, t) ==
  Ev("request_approval", "response", ApprovalInput(cid, amt), ApprovalOutput(app), t)

RefundEvent(cid, amt, t) ==
  Ev("issue_refund", "request", RefundInput(cid, amt), RefundOutput, t)

Trace ==
  IF hasApproval
  THEN << VerifyEvent, ApprovalEvent(approvalChargeId, amount, isApproved, 100), RefundEvent(refundChargeId, amount, 100 + gap) >>
  ELSE << VerifyEvent, RefundEvent(refundChargeId, amount, 100 + gap) >>

DecideIndex == IF hasApproval THEN 3 ELSE 2

RefundAllowed == D!Decide(Trace, Policies, DecideIndex, AllValues)

Init ==
  /\ amount \in AmountValues
  /\ gap \in GapValues
  /\ hasApproval \in {TRUE, FALSE}
  /\ isApproved \in {TRUE, FALSE}
  /\ approvalChargeId \in ChargeIdValues
  /\ refundChargeId \in ChargeIdValues

Next == UNCHANGED vars
Spec == Init /\ [][Next]_vars

IsOver500(amt) == amt \in AmountsOver500

HasValidApproval ==
  /\ hasApproval
  /\ isApproved
  /\ approvalChargeId = refundChargeId
  /\ gap <= 30 * Minute

RefundOver500RequiresApproval ==
  (IsOver500(amount) /\ ~HasValidApproval) => ~RefundAllowed

=============================================================================
