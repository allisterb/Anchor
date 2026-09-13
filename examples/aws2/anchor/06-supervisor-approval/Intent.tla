---------------------------- MODULE Intent ----------------------------
\* What 06-supervisor-approval.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Minute == 60
ThirtyMinutes == 30 * Minute

(* --- Event Constructors for the Session --- *)
(* An approval response for a given charge, marked as approved.
   This simulates a prior approval event that the policy's history
   mechanism would detect. *)
ApprovalResponseEvent(charge, time) ==
    Ev("request_approval", "response", [charge_id |-> charge], [approved |-> Bool(TRUE)], time)

(* A refund request for a given charge and amount. This is the event
   whose decision we are checking. *)
RefundRequestEvent(charge, amount, time) ==
    Ev("issue_refund", "request", [charge_id |-> charge, amount |-> amount], NoFields, time)

(* Construct a session: an approval response followed by a refund request.
   The 'gap' is the time difference between the approval response (at time 1)
   and the refund request (at time 1 + gap). *)
Session(charge, amount, gap) ==
    << ApprovalResponseEvent(charge, 1), RefundRequestEvent(charge, amount, 1 + gap) >>

(* Policy's decision for the refund request event (the second event in the session). *)
RefundAllowed(charge, amount, gap) ==
    D!Decide(Session(charge, amount, gap), Policies, 2, AllValues)

(***************************************************************************)
(* THE VALUES TO TEST: charge ID, refund amount, and time gap.             *)
(*                                                                         *)
(* These sets are explicitly defined to include values relevant to the     *)
(* claim, including those around the boundary conditions (e.g., amount     *)
(* 500, and gaps of 30 minutes). This avoids the trap where a claim        *)
(* ranges over nothing because the policy's vocabulary doesn't mention     *)
(* certain values.                                                         *)
(***************************************************************************)
chargeValues == {Num(1), Num(2)}
refundAmountValues == {Num(499), Num(500), Num(501)}
(* Test gaps: immediate, within 30 min, exactly 30 min, just over 30 min, well over 30 min. *)
gapValues == {0, Minute, 15 * Minute, ThirtyMinutes, ThirtyMinutes + 1, 45 * Minute}

(* One set of parameters (charge, amount, gap) chosen nondeterministically and held. *)
(* A violation's counterexample will NAME the specific scenario that breaks the claim. *)
VARIABLE charge, refundAmount, gap
Init == charge \in chargeValues /\ refundAmount \in refundAmountValues /\ gap \in gapValues
Next == UNCHANGED charge /\ UNCHANGED refundAmount /\ UNCHANGED gap
Spec == Init /\ [][Next]_charge /\ [][Next]_refundAmount /\ [][Next]_gap

(***************************************************************************)
(* THE CLAIMS.                                                             *)
(* Formalizing the intent:                                                 *)
(* "A refund over $500 requires a supervisor approval for that charge     *)
(*  within the previous 30 minutes."                                       *)
(***************************************************************************)

(* Invariant 1: Refunds of $500 or less should always be allowed.
   The policy does not impose any temporal or approval requirement for these. *)
SmallRefundsAlwaysAllowed ==
    (refundAmount <= Num(500)) => RefundAllowed(charge, refundAmount, gap)

(* Invariant 2: Large refunds (over $500) within 30 minutes of approval should be allowed. *)
LargeRefundsWithinTimeWindowAreAllowed ==
    (refundAmount > Num(500) /\ gap <= ThirtyMinutes) => RefundAllowed(charge, refundAmount, gap)

(* Invariant 3: Large refunds (over $500) requested more than 30 minutes after approval should be refused. *)
LargeRefundsAfterTimeWindowAreRefused ==
    (refundAmount > Num(500) /\ gap > ThirtyMinutes) => ~RefundAllowed(charge, refundAmount, gap)

=============================================================================
