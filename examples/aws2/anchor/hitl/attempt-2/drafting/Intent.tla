---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Hour == 3600

Amts1 == {20000, 40000, 60000}
Amts2 == {10000, 20000, 40000, 60000}
Gaps  == {1 * Hour, 13 * Hour}

Transfer(a, t) == Ev("initiate_transfer", "request", [amount |-> Num(a)], NoFields, t)
Session(a1, a2, g) == << Transfer(a1, 1), Transfer(a2, 1 + g) >>

FirstAllowed(a1) == D!Decide(<< Transfer(a1, 1) >>, Policies, 1, AllValues)
SecondAllowed(a1, a2, g) == D!Decide(Session(a1, a2, g), Policies, 2, AllValues)

EffectivePrior(a1, g) ==
  IF g <= 12 * Hour /\ FirstAllowed(a1) THEN a1 ELSE 0

VARIABLES a1, a2, gap

Init ==
  /\ a1 \in Amts1
  /\ a2 \in Amts2
  /\ gap \in Gaps

Next == UNCHANGED <<a1, a2, gap>>
Spec == Init /\ [][Next]_<<a1, a2, gap>>

ExceedingBudgetIsRefused ==
  (EffectivePrior(a1, gap) + a2 > 50000) => ~SecondAllowed(a1, a2, gap)

WithinBudgetIsAllowed ==
  (EffectivePrior(a1, gap) + a2 <= 50000) => SecondAllowed(a1, a2, gap)

=============================================================================