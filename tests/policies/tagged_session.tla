---------------------------- MODULE tagged_session ----------------------------
\* A property module that COMPILES AND THEN DOES NOT EVALUATE, recorded from a live drafting
\* session against `examples/aws2/agent-policy.dw`. TLC stops while computing initial states:
\*
\*     Error: Attempted to check equality of integer 1 with non-integer:
\*     FALSE
\*     Error: TLC was unable to fingerprint.
\*
\* The fault is that VARIABLES range over TAGGED values -- `{Num(1), Num(2)}` and
\* `{Bool(TRUE), Bool(FALSE)}` as Init domains. Moving the tags to the point of use, changing
\* nothing else, makes the same claims evaluate. Three live sessions died on this before the rule
\* was written down in `writing-a-property-module.md`.
\*
\* KEPT AS A FIXTURE because a smaller reconstruction did not reproduce it: two variables over a
\* Num domain and a Bool domain evaluate fine. Whatever the trigger is, it needs more of this
\* module than an explanation of it predicted -- so the real one is what gets checked in.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

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

VerifiedTransferAllowed ==
  (verified = Bool(TRUE) /\ accVerify = accTransfer /\ gap <= 900) => TransferAllowed

UnverifiedTransferForbidden ==
  (verified = Bool(FALSE) \/ accVerify # accTransfer \/ gap > 900) => ~TransferAllowed

=============================================================================
