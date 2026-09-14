---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

Amounts == {500, 2500}
ChargeIds == {1, 2}
Gaps == {60, 1800, 1801}
Booleans == {TRUE, FALSE}

VARIABLE hasApproval, approvalCharge, isApproved, refundCharge, amount, gap

Init ==
    /\ hasApproval \in Booleans
    /\ approvalCharge \in ChargeIds
    /\ isApproved \in Booleans
    /\ refundCharge \in {1}
    /\ amount \in Amounts
    /\ gap \in Gaps

Next == UNCHANGED <<hasApproval, approvalCharge, isApproved, refundCharge, amount, gap>>

Spec == Init /\ [][Next]_<<hasApproval, approvalCharge, isApproved, refundCharge, amount, gap>>

ApprovalEvent ==
    Ev("request_approval", "response",
       [account |-> Num(1), amount |-> Num(2500), charge_id |-> Num(approvalCharge), systemNowTime |-> Num(32400000)],
       [approved |-> Bool(isApproved), verified |-> Bool(FALSE)],
       100)

RefundEvent ==
    Ev("issue_refund", "request",
       [account |-> Num(1), amount |-> Num(amount), charge_id |-> Num(refundCharge), systemNowTime |-> Num(32400000)],
       [approved |-> Bool(FALSE), verified |-> Bool(FALSE)],
       100 + gap)

Session ==
    IF hasApproval
    THEN << ApprovalEvent, RefundEvent >>
    ELSE << RefundEvent >>

RefundDecided ==
    IF hasApproval
    THEN D!Decide(Session, Policies, 2, AllValues)
    ELSE D!Decide(Session, Policies, 1, AllValues)

RefundOver500WithoutApprovalRefused ==
    (amount = 2500 /\ ~hasApproval) => ~RefundDecided

RefundOver500WithUnapprovedResponseRefused ==
    (amount = 2500 /\ hasApproval /\ ~isApproved) => ~RefundDecided

RefundOver500WithMismatchedChargeRefused ==
    (amount = 2500 /\ hasApproval /\ approvalCharge /= refundCharge) => ~RefundDecided

RefundOver500WithExpiredApprovalRefused ==
    (amount = 2500 /\ hasApproval /\ gap > 30 * Minute) => ~RefundDecided

RefundOver500WithValidApprovalGranted ==
    (amount = 2500 /\ hasApproval /\ isApproved /\ approvalCharge = refundCharge /\ gap <= 30 * Minute) => RefundDecided

RefundAtOrBelow500Granted ==
    (amount = 500) => RefundDecided

=============================================================================
