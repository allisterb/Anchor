---------------------------- MODULE IdentityVerification ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(***************************************************************************)
(* Concrete values from vocabulary for checking identity verification      *)
(***************************************************************************)
AccountValues == {Num(1), Num(2)}
VerifiedValues == {Bool(TRUE), Bool(FALSE)}
Gaps == {60, 960}

VARIABLES gap, verified, accVerify, accTransfer

Init ==
  /\ gap \in Gaps
  /\ verified \in VerifiedValues
  /\ accVerify \in AccountValues
  /\ accTransfer \in AccountValues

Next == UNCHANGED <<gap, verified, accVerify, accTransfer>>
Spec == Init /\ [][Next]_<<gap, verified, accVerify, accTransfer>>

(***************************************************************************)
(* Hand-built traces of verify_identity response followed by transfer req. *)
(***************************************************************************)
VerifyEvent(t, acc, v) ==
  Ev("verify_identity", "response", [account |-> acc], [verified |-> v], t)

TransferEvent(t, acc) ==
  Ev("initiate_transfer", "request",
     [account |-> acc, amount |-> Num(499), systemNowTime |-> Num(32400000)],
     NoFields,
     t)

Session(g, v, av, at) ==
  << VerifyEvent(1, av, v), TransferEvent(1 + g, at) >>

TransferAllowed ==
  D!Decide(Session(gap, verified, accVerify, accTransfer), Policies, 2, AllValues)

(***************************************************************************)
(* Claims:                                                                 *)
(* 1. Verified transfers for the same account within 15m must be allowed.  *)
(* 2. Transfers without recent verification on that account are forbidden. *)
(***************************************************************************)
VerifiedTransferAllowed ==
  (verified = Bool(TRUE) /\ accVerify = accTransfer /\ gap <= 900) => TransferAllowed

UnverifiedTransferForbidden ==
  (verified = Bool(FALSE) \/ accVerify # accTransfer \/ gap > 900) => ~TransferAllowed

=============================================================================
