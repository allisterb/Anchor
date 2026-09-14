---------------------------- MODULE IdentityVerification ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60
FifteenMinutes == 15 * Minute

VerifyAccounts == {1, 2}
TransferAccounts == {1, 2}
VerifiedValues == {TRUE, FALSE}
HasVerificationValues == {TRUE, FALSE}
Gaps == {60, 900, 901, 1200}

VARIABLES hasVerification, verifyAccount, verified, transferAccount, gap

Init ==
    /\ hasVerification \in HasVerificationValues
    /\ verifyAccount \in VerifyAccounts
    /\ verified \in VerifiedValues
    /\ transferAccount \in TransferAccounts
    /\ gap \in Gaps

Next == UNCHANGED <<hasVerification, verifyAccount, verified, transferAccount, gap>>

Spec == Init /\ [][Next]_<<hasVerification, verifyAccount, verified, transferAccount, gap>>

TransferReq(acc, t) ==
    Ev("initiate_transfer", "request",
       [account |-> Num(acc), amount |-> Num(499), charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       NoFields, t)

VerifyResp(acc, ver, t) ==
    Ev("verify_identity", "response",
       [account |-> Num(acc), amount |-> Num(499), charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       [verified |-> Bool(ver), approved |-> Bool(FALSE)], t)

TransferAllowed ==
    IF hasVerification
    THEN D!Decide(<< VerifyResp(verifyAccount, verified, 1), TransferReq(transferAccount, 1 + gap) >>,
                  Policies, 2, AllValues)
    ELSE D!Decide(<< TransferReq(transferAccount, 1 + gap) >>,
                  Policies, 1, AllValues)

VerifiedTransferAllowed ==
    (hasVerification /\ verified /\ (verifyAccount = transferAccount) /\ (gap <= FifteenMinutes))
        => TransferAllowed

UnverifiedTransferRefused ==
    (~hasVerification \/ ~verified \/ (verifyAccount /= transferAccount) \/ (gap > FifteenMinutes))
        => ~TransferAllowed

=============================================================================
