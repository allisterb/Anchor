---------------------------- MODULE IdentityVerification ----------------------------
\* What agent-policy.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.

EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Constants *)
Minute == 60

(* Helper to define a session of two events:
 * 1. A verify_identity response at time 1.
 * 2. An initiate_transfer request at time 1 + gap.
 * Both events are for the same account.
 * The verify_identity event's output.verified field is set by verification_success.
 *)
Session(account_id, verification_success_bool, event_gap) ==
    <<
        Ev(
            "verify_identity",
            "response",
            [account |-> account_id],
            [verified |-> Bool(verification_success_bool)],
            1
        ),
        Ev(
            "initiate_transfer",
            "request",
            [account |-> account_id],
            NoFields,
            1 + event_gap
        )
    >>

(* Decides whether the initiate_transfer event (the second event in Session) is granted *)
GrantsTransfer(account_id, verification_success_bool, event_gap) ==
    D!Decide(Session(account_id, verification_success_bool, event_gap), Policies, 2, AllValues)


(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
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
Accounts == {Num(1), Num(2)} (* From inputFields.account domain in vocabulary *)
VerificationOutcomes == {TRUE, FALSE}
Gaps == {
    1,                       (* Very short gap *)
    15 * Minute - 1,         (* Just before the window expires *)
    15 * Minute,             (* Exactly at the window expiry *)
    15 * Minute + 1,         (* Just after the window expires *)
    30 * Minute              (* Well after the window expires *)
}

(* State variables chosen nondeterministically *)
VARIABLE acc, v_success, gap

Init ==
    /\ acc \in Accounts
    /\ v_success \in VerificationOutcomes
    /\ gap \in Gaps

Next ==
    UNCHANGED <<acc, v_success, gap>>

Spec == Init /\ [][Next]_<<acc, v_success, gap>>

(***************************************************************************)
(* THE CLAIM.                                                              *)
(* "Do not initiate a transfer unless the caller's identity has been      *)
(*  verified for that same account within the previous 15 minutes."        *)
(*                                                                         *)
(* This is formulated as: If the conditions for refusing a transfer are    *)
(* met (either verification failed, or it's older than 15 minutes), then  *)
(* the transfer must indeed be refused.                                    *)
(***************************************************************************)
TransferForbiddenUnlessRecentAndSuccessfulVerification ==
    (   (* Condition for refusing a transfer: *)
        (* 1. Verification was unsuccessful, OR *)
        (v_success = FALSE)
        \/
        (* 2. Verification was successful but happened more than 15 minutes ago *)
        (gap > 15 * Minute)
    )
    =>
    (* Then the transfer must be refused *)
    ~GrantsTransfer(acc, v_success, gap)

=============================================================================
