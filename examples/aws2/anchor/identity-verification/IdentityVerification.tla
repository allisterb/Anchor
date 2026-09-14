---------------------------- MODULE IdentityVerification ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

Accounts == {Num(1), Num(2)}
Amounts  == {Num(499), Num(500), Num(2500), Num(2501)}
Gaps     == {1 * Minute, 15 * Minute, 15 * Minute + 1, 30 * Minute}
Booleans == {Bool(TRUE), Bool(FALSE)}

VARIABLES hasVerify, verifyAcc, transferAcc, isVerified, gap, amt

vars == <<hasVerify, verifyAcc, transferAcc, isVerified, gap, amt>>

Init ==
  /\ hasVerify   \in {TRUE, FALSE}
  /\ verifyAcc   \in Accounts
  /\ transferAcc \in Accounts
  /\ isVerified  \in Booleans
  /\ gap         \in Gaps
  /\ amt         \in Amounts

Next == UNCHANGED vars

Spec == Init /\ [][Next]_vars

Trace ==
  IF hasVerify
  THEN <<
    Ev("verify_identity", "response",
       [account |-> verifyAcc, amount |-> amt, charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       [approved |-> Bool(FALSE), verified |-> isVerified],
       100),
    Ev("initiate_transfer", "request",
       [account |-> transferAcc, amount |-> amt, charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       NoFields,
       100 + gap)
  >>
  ELSE <<
    Ev("initiate_transfer", "request",
       [account |-> transferAcc, amount |-> amt, charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       NoFields,
       100)
  >>

DecideIndex == IF hasVerify THEN 2 ELSE 1

TransferAllowed == D!Decide(Trace, Policies, DecideIndex, AllValues)

ValidVerification ==
  /\ hasVerify
  /\ isVerified = Bool(TRUE)
  /\ verifyAcc = transferAcc
  /\ gap <= 15 * Minute

TransferRequiresVerification ==
  ~ValidVerification => ~TransferAllowed

=============================================================================
