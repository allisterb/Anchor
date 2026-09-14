---------------------------- MODULE RefundRateLimit ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Constants *)
HourInSeconds == Num(3600) (* One hour in seconds *)

(* Define sets of values for our test cases.
   We explicitly define these sets to include values that may not be
   mentioned in the policy's literal domain, but are necessary to
   thoroughly test the property (e.g., more than two charge_ids). *)
AccountValues == {Num(1), Num(2)}
(* We need at least 4 distinct charge_ids to represent 4 unique refund attempts
   for the same account. The policy's named domain for 'charge_id' only includes
   Num(1) and Num(2), so we add more. *)
ChargeIdForRefunds == {Num(1), Num(2), Num(3), Num(4), Num(5)}

(* Define time deltas for the 4th refund event relative to the first.
   These deltas are chosen to test scenarios:
   - within one hour (e.g., 10, 3500 seconds)
   - exactly one hour (3600 seconds)
   - beyond one hour (e.g., 3601, 7200 seconds) *)
TestTimeDeltas == {Num(10), Num(3500), HourInSeconds, Num(3601), Num(7200)}

(*
   Construct a session with four 'issue_refund' events for the same account.
   The first three events happen at times 0, 1, and 2 seconds.
   The fourth event happens at 'delta' seconds from the first event.
   This setup allows us to control the time window of the four events
   to test the 1-hour rate limit. Each refund uses a distinct charge_id.
*)
RefundSession(acc, delta) ==
  <<
    Ev("issue_refund", "request", [account |-> acc, charge_id |-> Num(1)], NoFields, Num(0)),
    Ev("issue_refund", "request", [account |-> acc, charge_id |-> Num(2)], NoFields, Num(1)),
    Ev("issue_refund", "request", [account |-> acc, charge_id |-> Num(3)], NoFields, Num(2)),
    Ev("issue_refund", "request", [account |-> acc, charge_id |-> Num(4)], NoFields, delta)
  >>

(*
   Determines the policy's decision for the fourth event in the session.
   The index is 4 because we are interested in the decision for the 4th event
   in our constructed sequence.
*)
RefundDecisionForFourthEvent(acc, delta) ==
  D!Decide(RefundSession(acc, delta), Policies, 4, AllValues)

(*
   State variables to nondeterministically select test cases.
   TLC will explore all combinations of `current_account` and `current_delta_t`.
*)
VARIABLE current_account, current_delta_t

Init ==
  /\ current_account \in AccountValues
  /\ current_delta_t \in TestTimeDeltas

Next ==
  UNCHANGED current_account
  /\ UNCHANGED current_delta_t

Spec == Init /\ [][Next]_<<current_account, current_delta_t>>

(*
   CLAIM 1: "The agent might attempt no more than three refunds against the same
   account within one hour." This means that if there are four refund attempts
   for the same account within a 1-hour period (current_delta_t <= 3600),
   the policy MUST refuse the fourth refund.
*)
FourthRefundWithinHourIsRefused ==
  (current_delta_t <= HourInSeconds)
  => ~RefundDecisionForFourthEvent(current_account, current_delta_t)

(*
   CLAIM 2 (Complementary): If the fourth refund occurs *outside* the 1-hour
   window (current_delta_t > 3600), it should NOT be refused due to *this*
   specific rate limit. This helps verify that the rate limit isn't always
   active or that refunds aren't unconditionally denied by other rules.
   It assumes that, in the absence of a rate limit violation, the refund would
   otherwise be permitted. If this invariant fails, it indicates either another
   rule is unconditionally denying refunds, or the rate limit logic is flawed.
*)
FourthRefundOutsideHourIsPermittedByRateLimit ==
  (current_delta_t > HourInSeconds)
  => RefundDecisionForFourthEvent(current_account, current_delta_t)

=============================================================================
