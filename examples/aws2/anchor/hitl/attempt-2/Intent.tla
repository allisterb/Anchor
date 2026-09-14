---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Inp(acc, amt, cid, tNow) == [account |-> acc, amount |-> amt, charge_id |-> cid, systemNowTime |-> tNow]
Out(app, ver)            == [approved |-> app, verified |-> ver]

VerifyEvent(t)              == Ev("verify_identity", "response", Inp(Num(1), Num(0), Num(1), Num(32400000)), Out(Bool(FALSE), Bool(TRUE)), t)
ApprovalEvent(t, cid, app)  == Ev("request_approval", "response", Inp(Num(1), Num(2500), cid, Num(32400000)), Out(Bool(app), Bool(FALSE)), t)
RefundEvent(t, cid, amt)    == Ev("issue_refund", "request", Inp(Num(1), amt, cid, Num(32400000)), Out(Bool(FALSE), Bool(FALSE)), t)

VARIABLE gap, app, sameCharge, amt

Init ==
    /\ gap \in {300, 1800, 2400}
    /\ app \in {TRUE, FALSE}
    /\ sameCharge \in {TRUE, FALSE}
    /\ amt \in {Num(500), Num(2500)}

Next == UNCHANGED <<gap, app, sameCharge, amt>>

Spec == Init /\ [][Next]_<<gap, app, sameCharge, amt>>

RefundAllowed ==
    LET cid == IF sameCharge THEN Num(1) ELSE Num(2)
        trace == <<
            VerifyEvent(1),
            ApprovalEvent(10, cid, app),
            RefundEvent(10 + gap, Num(1), amt)
        >>
    IN D!Decide(trace, Policies, 3, AllValues)

RefundOver500RequiresRecentApproval ==
    (amt = Num(2500) /\ ~(app = TRUE /\ sameCharge = TRUE /\ gap <= 1800)) => ~RefundAllowed

RefundOver500WithApprovalPermitted ==
    (amt = Num(2500) /\ app = TRUE /\ sameCharge = TRUE /\ gap <= 1800) => RefundAllowed

RefundUnder500Permitted ==
    (amt = Num(500)) => RefundAllowed

=============================================================================
