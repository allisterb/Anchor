---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

AmountsOver500  == {Num(2500), Num(2501)}
AmountsUnder500 == {Num(499), Num(500)}
AllAmounts      == AmountsOver500 \cup AmountsUnder500

ChargeIds     == {Num(1), Num(2)}
ApprovedFlags == {Bool(TRUE), Bool(FALSE)}
Gaps          == {60, 1800, 1801, 3600}

Requests == [
  hasApproval      : {TRUE, FALSE},
  approvalApproved : ApprovedFlags,
  approvalChargeId : ChargeIds,
  refundChargeId   : ChargeIds,
  refundAmount     : AllAmounts,
  approvalGap      : Gaps
]

VerifyEv ==
  Ev("verify_identity", "response",
     [account |-> Num(1), amount |-> Num(500), charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
     [approved |-> Bool(FALSE), verified |-> Bool(TRUE)],
     1)

ApprovalEv(r) ==
  Ev("request_approval", "response",
     [account |-> Num(1), amount |-> r.refundAmount, charge_id |-> r.approvalChargeId, systemNowTime |-> Num(32400000)],
     [approved |-> r.approvalApproved, verified |-> Bool(FALSE)],
     100)

RefundEv(r) ==
  LET refundTime == IF r.hasApproval THEN 100 + r.approvalGap ELSE 100
  IN Ev("issue_refund", "request",
        [account |-> Num(1), amount |-> r.refundAmount, charge_id |-> r.refundChargeId, systemNowTime |-> Num(32400000)],
        NoFields,
        refundTime)

Trace(r) ==
  IF r.hasApproval
  THEN << VerifyEv, ApprovalEv(r), RefundEv(r) >>
  ELSE << VerifyEv, RefundEv(r) >>

DecideIndex(r) == IF r.hasApproval THEN 3 ELSE 2

RefundGranted(r) == D!Decide(Trace(r), Policies, DecideIndex(r), AllValues)

ValidApproval(r) ==
  /\ r.hasApproval
  /\ r.approvalApproved = Bool(TRUE)
  /\ r.approvalChargeId = r.refundChargeId
  /\ r.approvalGap <= 1800

VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

(***************************************************************************)
(* A refund over $500 requires a supervisor approval for that charge       *)
(* within the previous 30 minutes (1800 seconds).                          *)
(***************************************************************************)
RefundOver500RequiresApproval ==
  (req.refundAmount \in AmountsOver500 /\ ~ValidApproval(req)) => ~RefundGranted(req)

=============================================================================
