---------------------------- MODULE RefundRateLimit ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60
Hour == 3600

RefundInput(acc) == [
    account |-> Num(acc),
    amount |-> Num(499),
    charge_id |-> Num(1),
    systemNowTime |-> Num(32400000)
]

Refund(t, acc) == Ev("issue_refund", "request", RefundInput(acc), NoFields, t)

Session(g) == <<
    Refund(1, 1),
    Refund(2, 1),
    Refund(3, 1),
    Refund(1 + g, 1)
>>

RefundAllowed(g) == D!Decide(Session(g), Policies, 4, AllValues)

Gaps == {10 * Minute, 30 * Minute, 59 * Minute, 60 * Minute, 61 * Minute, 120 * Minute}

VARIABLE gap
Init == gap \in Gaps
Next == UNCHANGED gap
Spec == Init /\ [][Next]_gap

FourthRefundWithinHourRefused == (gap <= Hour) => ~RefundAllowed(gap)

=============================================================================
