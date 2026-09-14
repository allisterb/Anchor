---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Hour == 3600

VARIABLES prevAmount, curAmount, gap

Amounts == {20000, 30000, 40000}
Gaps    == {1 * Hour, 13 * Hour}

Init ==
  /\ prevAmount \in Amounts
  /\ curAmount  \in Amounts
  /\ gap        \in Gaps

Next == UNCHANGED <<prevAmount, curAmount, gap>>
Spec == Init /\ [][Next]_<<prevAmount, curAmount, gap>>

Transfer(amt, t) == Ev("initiate_transfer", "request", [amount |-> Num(amt)], NoFields, t)

Session == << Transfer(prevAmount, 1), Transfer(curAmount, 1 + gap) >>
Allowed == D!Decide(Session, Policies, 2, AllValues)

BlockOverCap ==
  (gap <= 12 * Hour /\ prevAmount + curAmount > 50000) => ~Allowed

=============================================================================
