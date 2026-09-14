---------------------------- MODULE Intent05HumanApproval ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Amounts == {10000, 25000, 25001, 50000}
HasApproval == {TRUE, FALSE}

VARIABLE amt, approved

Init ==
  /\ amt \in Amounts
  /\ approved \in HasApproval

Next == UNCHANGED <<amt, approved>>
Spec == Init /\ [][Next]_<<amt, approved>>

Approval(t) == Ev("approve_trade", "response", NoFields, NoFields, t)
Trade(a, t) == Ev("execute_trade", "request", [amount |-> Num(a)], NoFields, t)

Session ==
  IF approved
  THEN << Approval(1), Trade(amt, 2) >>
  ELSE << Trade(amt, 1) >>

TradeIndex == IF approved THEN 2 ELSE 1

TradeAllowed == D!Decide(Session, Policies, TradeIndex, AllValues)

TradeOver25kRequiresApproval ==
  (amt > 25000 /\ ~approved) => ~TradeAllowed

=============================================================================
