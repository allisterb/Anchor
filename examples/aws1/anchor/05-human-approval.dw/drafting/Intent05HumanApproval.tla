---------------------------- MODULE Intent05HumanApproval ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Profile(t)   == Ev("get_client_profile", "response", NoFields, NoFields, t)
Portfolio(t) == Ev("load_portfolio", "response", NoFields, NoFields, t)
Rebalance(t) == Ev("rebalance_portfolio", "request", NoFields, NoFields, t)

Gaps == {10, 600}
HasProfile == {TRUE, FALSE}
HasPortfolio == {TRUE, FALSE}

VARIABLE gap, hasProfile, hasPortfolio

Init ==
  /\ gap \in Gaps
  /\ hasProfile \in HasProfile
  /\ hasPortfolio \in HasPortfolio

Next == UNCHANGED <<gap, hasProfile, hasPortfolio>>
Spec == Init /\ [][Next]_<<gap, hasProfile, hasPortfolio>>

Session ==
  IF hasProfile /\ hasPortfolio
  THEN << Profile(1), Portfolio(2), Rebalance(2 + gap) >>
  ELSE IF hasPortfolio
       THEN << Portfolio(1), Rebalance(1 + gap) >>
       ELSE << Rebalance(1) >>

Idx == Len(Session)

Allowed == D!Decide(Session, Policies, Idx, AllValues)

SequentialWorkflow ==
  (~hasPortfolio \/ gap > 300) => ~Allowed

=============================================================================