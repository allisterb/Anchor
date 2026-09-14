---------------------------- MODULE IdentityVerification ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

Verify(acc, ver, t) ==
  Ev("verify_identity", "response", [account |-> Num(acc)], [verified |-> Bool(ver)], t)

Transfer(acc, t) ==
  Ev("initiate_transfer", "request",
     [account |-> Num(acc), amount |-> Num(500), charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
     NoFields, t)

Session(accV, accT, ver, gap) ==
  << Verify(accV, ver, 1), Transfer(accT, 1 + gap) >>

TransferAllowed(accV, accT, ver, gap) ==
  D!Decide(Session(accV, accT, ver, gap), Policies, 2, AllValues)

VARIABLES accV, accT, verified, gap

Accounts == {1, 2}
Gaps == {60, 15 * Minute, 16 * Minute}
Booleans == {TRUE, FALSE}

Init ==
  /\ accV \in Accounts
  /\ accT \in Accounts
  /\ verified \in Booleans
  /\ gap \in Gaps

Next == UNCHANGED <<accV, accT, verified, gap>>

Spec == Init /\ [][Next]_<<accV, accT, verified, gap>>

TransferRequiresVerification ==
  (~verified \/ accV /= accT \/ gap > 15 * Minute) =>
    ~TransferAllowed(accV, accT, verified, gap)

=============================================================================
