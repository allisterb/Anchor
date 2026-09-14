---------------------------- MODULE SupervisorApproval ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Constants for time calculations *)
Minute == 60
HalfHour == 30 * Minute

(* Helper functions to construct events *)
(* An approval event, where the approval was granted.
   `approved: TRUE` is an output field of the `request_approval` action. *)
ApprovedRequestApproval(chargeId, time) == 
    Ev("request_approval", "response", NoFields, [approved |-> Bool(TRUE)], time)

(* A refund request event. *)
IssueRefund(amountVal, chargeId, time) ==
    Ev("issue_refund", "request", [amount |-> amountVal, charge_id |-> chargeId], NoFields, time)

(* Added: Verification event, as a common prerequisite that many policies require before other actions.
   This helps address the "CONSTANT decision" error by providing necessary context for the policy
   to potentially grant the refund. *)
VerifyIdentity(time) ==
    Ev("verify_identity", "request", NoFields, NoFields, time)

(* A session composed of verification, approval, then refund.
   All events must be in time order. *)
RefundSession(verificationTime, approvalTime, refundTime, amountVal, chargeId) ==
    << VerifyIdentity(verificationTime),
       ApprovedRequestApproval(chargeId, approvalTime), 
       IssueRefund(amountVal, chargeId, refundTime) >>

(* The policy's decision for the refund event (the third event, index 3) in the session. *)
RefundAllowed(verificationTime, approvalTime, refundTime, amountVal, chargeId) ==
    D!Decide(RefundSession(verificationTime, approvalTime, refundTime, amountVal, chargeId), Policies, 3, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
(* Values chosen to test the boundaries of the policy.                     *)
(***************************************************************************)
(* Amounts to test: below, at, and above the $500 threshold. *)
amountValues == {Num(499), Num(500), Num(501), Num(2500), Num(2501)}
chargeIdValues == {Num(1), Num(2)}

(* Time differences (deltaT = refundTime - approvalTime) between approval and refund.
   Must be non-negative for approval to precede or coincide with the refund.
   Values cover: exact same time, within window, at window boundary, just outside, and well outside. *)
deltaTValues == {
    0,                                (* Approval and refund at same time *)
    1,                                (* Approval 1 second before refund *)
    HalfHour \div 2,                  (* Approval in middle of window (integer division) *)
    HalfHour - 1,                     (* Approval just before window end *)
    HalfHour,                         (* Approval exactly at window end (30 minutes) *)
    HalfHour + 1,                     (* Approval just outside window (> 30 minutes) *)
    HalfHour + 10 * Minute            (* Approval well outside window *)
}

(* Variables that define the state space for model checking *)
VARIABLE amount_var, charge_id_var, deltaT_var

(* Initial state: each variable takes one value from its defined domain *)
Init == 
    amount_var \in amountValues /\
    charge_id_var \in chargeIdValues /\
    deltaT_var \in deltaTValues

(* Next state: variables remain unchanged, as we test one scenario (request) per state *)
Next == UNCHANGED <<amount_var, charge_id_var, deltaT_var>>

(* Specification: Start in an initial state, then stay in that state *)
Spec == Init /\ [][Next]_<<amount_var, charge_id_var, deltaT_var>>

(***************************************************************************)
(* THE CLAIMS.                                                             *)
(* "A refund over $500 requires a supervisor approval for that charge     *)
(* within the previous 30 minutes."                                        *)
(***************************************************************************)
(* Common predicates used in the invariants *)
IsRefundOver500 == amount_var > Num(500)
ApprovalIsWithin30Minutes == deltaT_var <= HalfHour
ApprovalIsOutside30Minutes == deltaT_var > HalfHour

(* Define base times for the session:
   Verification at t=1, approval at t=2, refund at t=2+deltaT_var.
   This ensures verification always precedes approval, and all event times are >= 1. *)
verificationBaseTime == 1
approvalBaseTime == 2
refundActualTime == approvalBaseTime + deltaT_var

(* Invariant 1: If a refund is over $500 AND its required approval is older than 30 minutes,
   then the policy MUST forbid this refund. *)
RefundOver500WithOldApprovalIsForbidden ==
    (IsRefundOver500 /\ ApprovalIsOutside30Minutes)
    => ~RefundAllowed(verificationBaseTime, approvalBaseTime, refundActualTime, amount_var, charge_id_var)

(* Invariant 2: If a refund is over $500 AND its required approval happened within 30 minutes,
   then the policy MUST permit this refund. *)
RefundOver500WithRecentApprovalIsPermitted ==
    (IsRefundOver500 /\ ApprovalIsWithin30Minutes)
    => RefundAllowed(verificationBaseTime, approvalBaseTime, refundActualTime, amount_var, charge_id_var)

=============================================================================
