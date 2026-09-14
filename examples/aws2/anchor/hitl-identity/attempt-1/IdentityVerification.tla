---------------------------- MODULE IdentityVerification ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60

Accounts == {Num(1), Num(2)}
Amounts  == {Num(500), Num(2500)}
VerifiedVals == {Bool(TRUE), Bool(FALSE)}
Gaps     == {0, 60, 300, 899, 900, 901, 1200}

VARIABLE hasVerify, vAccount, vVerified, gap, tAccount, amount

Init ==
  /\ hasVerify \in BOOLEAN
  /\ vAccount \in Accounts
  /\ vVerified \in VerifiedVals
  /\ gap \in Gaps
  /\ tAccount \in Accounts
  /\ amount \in Amounts

Next == UNCHANGED <<hasVerify, vAccount, vVerified, gap, tAccount, amount>>

Spec == Init /\ [][Next]_<<hasVerify, vAccount, vVerified, gap, tAccount, amount>>

VerifyEvent == Ev("verify_identity", "response", [account |-> vAccount], [verified |-> vVerified], 1)
TransferEvent(t) == Ev("initiate_transfer", "request", [account |-> tAccount, amount |-> amount], NoFields, t)

Session ==
  IF hasVerify
  THEN << VerifyEvent, TransferEvent(1 + gap) >>
  ELSE << TransferEvent(1) >>

DecideIndex == IF hasVerify THEN 2 ELSE 1

TransferAllowed == D!Decide(Session, Policies, DecideIndex, AllValues)

VerifiedWithin15Min ==
  /\ hasVerify
  /\ vAccount = tAccount
  /\ vVerified = Bool(TRUE)
  /\ gap <= 15 * Minute

TransferRequiresIdentityVerification ==
  ~VerifiedWithin15Min => ~TransferAllowed

=============================================================================
