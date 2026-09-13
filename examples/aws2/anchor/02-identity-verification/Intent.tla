---------------------------- MODULE Intent ----------------------------
\* What 02-identity-verification.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
\*
\* Check it with:  anchor check 02-identity-verification.dw --property Intent.tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\* Helper to get the decision for a specific event in a trace.
Decision(trace, eventIndex) == D!Decide(trace, Policies, eventIndex, AllValues)

Minute == 60

(***************************************************************************)
(* THE VALUES THIS CLAIM IS ABOUT.                                         *)
(*                                                                         *)
(* Written out rather than derived from InputDomain, and that is the       *)
(* point. A space derived from the policy's own literals cannot test a     *)
(* claim about a value the policy never mentions: delete the rule that     *)
(* names a value and it vanishes from the vocabulary, so the claim ranges  *)
(* over nothing and PASSES having looked at nothing.                       *)
(*                                                                         *)
(* Add the values your claim is about, including ones this policy never    *)
(* mentions.                                                               *)
(***************************************************************************)
Accounts == {Num(1), Num(2)}
\* Gaps between the verification event and the transfer request event.
\* We test short gaps, around the 15-minute threshold, and longer ones.
Gaps == {
    1,                 \* Very short gap
    5 * Minute,        \* Well within time
    15 * Minute - 1,   \* Just before the threshold
    15 * Minute,       \* Exactly at the threshold
    15 * Minute + 1,   \* Just after the threshold
    20 * Minute        \* Well past the threshold
}
VerificationOutcomes == {TRUE, FALSE}

\* Variables for the model checker to explore different scenarios.
\* - `transferAccount`: The account specified in the initiate_transfer request.
\* - `verifyAccount`: The account specified in the verify_identity response.
\* - `gap`: The time difference (in seconds) between the verification and the transfer attempt.
\* - `verifiedSuccess`: Whether the identity verification event reported success (TRUE) or failure (FALSE).
VARIABLE transferAccount, verifyAccount, gap, verifiedSuccess

Init ==
    transferAccount \in Accounts /\
    verifyAccount \in Accounts /\
    gap \in Gaps /\
    verifiedSuccess \in VerificationOutcomes

Next == UNCHANGED <<transferAccount, verifyAccount, gap, verifiedSuccess>>
Spec == Init /\ [][Next]_<<transferAccount, verifyAccount, gap, verifiedSuccess>>

(***************************************************************************)
(* HELPERS FOR THE CLAIM.                                                  *)
(***************************************************************************)

\* Returns TRUE if the verification conditions meet the policy's requirement
\* for allowing a transfer: same account, within 15 minutes, and actually verified.
SatisfiesVerificationCondition(transferAcc, verifyAcc, timeGap, isSuccess) ==
    (transferAcc = verifyAcc) /\
    (timeGap <= 15 * Minute) /\
    (isSuccess = TRUE)

\* Helper to construct the verification event.
ConstructVerifyEvent(verifyAcc, isSuccess) ==
    Ev("verify_identity", "response", [account |-> verifyAcc], [verified |-> Bool(isSuccess)], 1)

\* Helper to construct the transfer event.
ConstructTransferEvent(transferAcc, timeGap) ==
    Ev("initiate_transfer", "request", [account |-> transferAcc], NoFields, 1 + timeGap)

\* Constructs a two-event trace: a verification followed by a transfer attempt.
\* Returns the policy's decision for the transfer attempt (the second event).
IsTransferAllowed(transferAcc, verifyAcc, timeGap, isSuccess) ==
    LET
        verifyEv = ConstructVerifyEvent(verifyAcc, isSuccess)
        transferEv = ConstructTransferEvent(transferAcc, timeGap)
        trace = <<verifyEv, transferEv>>
    IN
        \* We are interested in the decision for the 'initiate_transfer' event, which is the second event (index 2).
        Decision(trace, 2)

(***************************************************************************)
(* THE CLAIM.                                                              *)
\* "Do not initiate a transfer unless the caller's identity has been        *)
\* verified for that same account within the previous 15 minutes."          *)
(***************************************************************************)
NoTransferWithoutVerification ==
    \* If the verification conditions are NOT met, then the transfer must NOT be allowed.
    ~SatisfiesVerificationCondition(transferAccount, verifyAccount, gap, verifiedSuccess)
    =>
    ~IsTransferAllowed(transferAccount, verifyAccount, gap, verifiedSuccess)

=============================================================================
