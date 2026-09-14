---------------------------- MODULE Intent03DataFreshness ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60
Gaps == {10, 60, 290, 300, 301, 360, 600}

LoadPortfolio(t)       == Ev("load_portfolio", "response", NoFields, NoFields, t)
RebalancePortfolio(t)  == Ev("rebalance_portfolio", "request", NoFields, NoFields, t)

Session(gap) == << LoadPortfolio(1), RebalancePortfolio(1 + gap) >>
RebalanceAllowed(gap) == D!Decide(Session(gap), Policies, 2, AllValues)

VARIABLE gap
Init == gap \in Gaps
Next == UNCHANGED gap
Spec == Init /\ [][Next]_gap

FreshDataGrants   == (gap <= 300) => RebalanceAllowed(gap)
StaleDataRefused  == (gap > 300) => ~RebalanceAllowed(gap)

=============================================================================
