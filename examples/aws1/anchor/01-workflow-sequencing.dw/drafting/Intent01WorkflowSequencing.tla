---------------------------- MODULE Intent01WorkflowSequencing ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

ProfileResponse(t) == Ev("get_client_profile", "response", NoFields, NoFields, t)
LoadResponse(t)    == Ev("load_portfolio", "response", NoFields, NoFields, t)
LoadRequest(t)     == Ev("load_portfolio", "request", NoFields, NoFields, t)
RebalanceRequest(t)== Ev("rebalance_portfolio", "request", NoFields, NoFields, t)

VARIABLES hasProfile, hasLoad

Init ==
  /\ hasProfile \in {TRUE, FALSE}
  /\ hasLoad    \in {TRUE, FALSE}

Next == UNCHANGED <<hasProfile, hasLoad>>
Spec == Init /\ [][Next]_<<hasProfile, hasLoad>>

LoadTrace ==
  IF hasProfile
  THEN <<ProfileResponse(1), LoadRequest(2)>>
  ELSE <<LoadRequest(1)>>

LoadAllowed ==
  D!Decide(LoadTrace, Policies, Len(LoadTrace), AllValues)

LoadRequiresProfile ==
  LoadAllowed => hasProfile

RebalanceTrace ==
  IF hasProfile /\ hasLoad
  THEN <<ProfileResponse(1), LoadResponse(2), RebalanceRequest(3)>>
  ELSE IF hasLoad
       THEN <<LoadResponse(1), RebalanceRequest(2)>>
       ELSE IF hasProfile
            THEN <<ProfileResponse(1), RebalanceRequest(2)>>
            ELSE <<RebalanceRequest(1)>>

RebalanceAllowed ==
  D!Decide(RebalanceTrace, Policies, Len(RebalanceTrace), AllValues)

RebalanceRequiresLoad ==
  RebalanceAllowed => hasLoad

=============================================================================