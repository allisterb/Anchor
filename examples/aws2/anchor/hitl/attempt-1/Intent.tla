---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

Amounts == {Num(499), Num(500), Num(2500), Num(2501)}
ChargeIds == {Num(1), Num(2)}
Gaps == {10 * Minute, 29 * Minute, 30 * Minute, 31 * Minute, 45 * Minute}
Booleans == {TRUE, FALSE}
Times == {Num(32400000)}

Scenarios ==
    [ hasApproval : Booleans,
      approvalApproved : Booleans,
      approvalCharge : ChargeIds,
      refundCharge : ChargeIds,
      refundAmount : Amounts,
      gap : Gaps,
      nowTime : Times ]

VARIABLE scenario

Init == scenario \in Scenarios
Next == UNCHANGED scenario
Spec == Init /\ [][Next]_scenario

ApprovalInput(s) ==
    [ account |-> Num(1),
      amount |-> s.refundAmount,
      charge_id |-> s.approvalCharge,
      systemNowTime |-> s.nowTime ]

ApprovalOutput(s) ==
    [ approved |-> Bool(s.approvalApproved),
      verified |-> Bool(FALSE) ]

RefundInput(s) ==
    [ account |-> Num(1),
      amount |-> s.refundAmount,
      charge_id |-> s.refundCharge,
      systemNowTime |-> s.nowTime ]

RefundOutput ==
    [ approved |-> Bool(FALSE),
      verified |-> Bool(FALSE) ]

Trace(s) ==
    IF s.hasApproval THEN
        << Ev("request_approval", "response", ApprovalInput(s), ApprovalOutput(s), 1),
           Ev("issue_refund", "request", RefundInput(s), RefundOutput, 1 + s.gap) >>
    ELSE
        << Ev("issue_refund", "request", RefundInput(s), RefundOutput, 1) >>

RefundIndex(s) == IF s.hasApproval THEN 2 ELSE 1

RefundAllowed(s) == D!Decide(Trace(s), Policies, RefundIndex(s), AllValues)

ValidApproval(s) ==
    /\ s.hasApproval
    /\ s.approvalApproved
    /\ s.approvalCharge = s.refundCharge
    /\ s.gap <= 30 * Minute

IsOver500(s) == s.refundAmount \in {Num(2500), Num(2501)}

RefundOver500RequiresApproval ==
    (IsOver500(scenario) /\ ~ValidApproval(scenario)) => ~RefundAllowed(scenario)

=============================================================================
