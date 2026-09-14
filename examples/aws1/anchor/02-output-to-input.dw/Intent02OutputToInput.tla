---------------------------- MODULE Intent02OutputToInput ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Profiles == {"profile_1", "profile_2"}

GetProfile(p, t)    == Ev("get_client_profile", "response", NoFields, [profile |-> Str(p)], t)
LoadPortfolio(p, t) == Ev("load_portfolio", "response", [profile |-> Str(p)], [profile |-> Str(p)], t)
Rebalance(p, t)     == Ev("rebalance_portfolio", "request", [profile |-> Str(p)], NoFields, t)

Session(loaded, requested) ==
    << GetProfile(loaded, 1),
       LoadPortfolio(loaded, 10),
       Rebalance(requested, 20) >>

RebalanceAllowed(loaded, requested) ==
    D!Decide(Session(loaded, requested), Policies, 3, AllValues)

VARIABLES loadedProfile, requestedProfile

Init == /\ loadedProfile \in Profiles
        /\ requestedProfile \in Profiles

Next == UNCHANGED <<loadedProfile, requestedProfile>>

Spec == Init /\ [][Next]_<<loadedProfile, requestedProfile>>

ProfileMustMatchLoaded ==
    (requestedProfile /= loadedProfile) => ~RebalanceAllowed(loadedProfile, requestedProfile)

=============================================================================
