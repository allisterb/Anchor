---------------------------- MODULE CumulativeCap ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Hour == 3600
Window == 12 * Hour

PastAmounts == {0, 20000, 40000, 50000}
CurrentAmounts == {500, 10000, 20000, 50001}
Gaps == {1 * Hour, 6 * Hour, 12 * Hour, 13 * Hour, 24 * Hour}

TransferInput(amt) ==
  [account |-> Num(1), amount |-> Num(amt), charge_id |-> Num(1), systemNowTime |-> Num(32400000)]

SuccessOutput ==
  [approved |-> Bool(TRUE), verified |-> Bool(TRUE)]

Session(pAmt, cAmt, g) ==
  IF pAmt = 0 THEN
    << Ev("verify_identity", "request", TransferInput(cAmt), NoFields, 80),
       Ev("verify_identity", "response", TransferInput(cAmt), SuccessOutput, 85),
       Ev("request_approval", "request", TransferInput(cAmt), NoFields, 90),
       Ev("request_approval", "response", TransferInput(cAmt), SuccessOutput, 95),
       Ev("initiate_transfer", "request", TransferInput(cAmt), NoFields, 100) >>
  ELSE
    << Ev("verify_identity", "request", TransferInput(pAmt), NoFields, 10),
       Ev("verify_identity", "response", TransferInput(pAmt), SuccessOutput, 15),
       Ev("request_approval", "request", TransferInput(pAmt), NoFields, 20),
       Ev("request_approval", "response", TransferInput(pAmt), SuccessOutput, 25),
       Ev("initiate_transfer", "request", TransferInput(pAmt), NoFields, 30),
       Ev("initiate_transfer", "response", TransferInput(pAmt), SuccessOutput, 35),
       Ev("verify_identity", "request", TransferInput(cAmt), NoFields, 30 + g - 20),
       Ev("verify_identity", "response", TransferInput(cAmt), SuccessOutput, 30 + g - 15),
       Ev("request_approval", "request", TransferInput(cAmt), NoFields, 30 + g - 10),
       Ev("request_approval", "response", TransferInput(cAmt), SuccessOutput, 30 + g - 5),
       Ev("initiate_transfer", "request", TransferInput(cAmt), NoFields, 30 + g) >>

TransferAllowed(pAmt, cAmt, g) ==
  LET s == Session(pAmt, cAmt, g)
  IN D!Decide(s, Policies, Len(s), AllValues)

CumulativeAmount(pAmt, cAmt, g) ==
  IF g <= Window THEN pAmt + cAmt ELSE cAmt

VARIABLE pastAmt, currentAmt, gap

Init ==
  /\ pastAmt \in PastAmounts
  /\ currentAmt \in CurrentAmounts
  /\ gap \in Gaps

Next == UNCHANGED <<pastAmt, currentAmt, gap>>

Spec == Init /\ [][Next]_<<pastAmt, currentAmt, gap>>

TransferExceeds12hCap == CumulativeAmount(pastAmt, currentAmt, gap) > 50000

TransfersOver50kIn12hBlocked ==
  TransferExceeds12hCap => ~TransferAllowed(pastAmt, currentAmt, gap)

=============================================================================
