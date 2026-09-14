---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Profile(t)   == Ev("get_client_profile", "response", NoFields, NoFields, t)
Load(t)      == Ev("load_portfolio", "response", NoFields, NoFields, t)
Rebalance(t) == Ev("rebalance_portfolio", "request", NoFields, NoFields, t)

VARIABLE scenario

Init == scenario \in {"none", "profile_only", "load_only", "profile_then_load", "load_then_profile"}
Next == UNCHANGED scenario
Spec == Init /\ [][Next]_scenario

Trace ==
    CASE scenario = "none"              -> << Rebalance(10) >>
      [] scenario = "profile_only"      -> << Profile(1), Rebalance(10) >>
      [] scenario = "load_only"         -> << Load(5), Rebalance(10) >>
      [] scenario = "profile_then_load" -> << Profile(1), Load(5), Rebalance(10) >>
      [] scenario = "load_then_profile" -> << Load(1), Profile(5), Rebalance(10) >>

RebalanceAllowed == D!Decide(Trace, Policies, Len(Trace), AllValues)

RebalanceRequiresOrderedWorkflow ==
    RebalanceAllowed => (scenario = "profile_then_load")

=============================================================================
