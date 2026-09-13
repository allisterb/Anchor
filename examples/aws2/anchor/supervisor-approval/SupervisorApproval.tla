---------------------------- MODULE SupervisorApproval ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Helper to decide on a specific event in a trace *)
DecideOnEvent(trace, event_idx) == D!Decide(trace, Policies, event_idx, AllValues)

(* --- Constants for the claim --- *)
MinAmountForApproval == Num(500)
ApprovalWindowSeconds == 30 * 60 (* 30 minutes in seconds *)
Minute == 60

(* --- Domains for testing --- *)
(* Amount values, covering cases below, at, and above the threshold *)
TestAmounts == {Num(499), Num(500), Num(2500), Num(2501)}

(* Charge IDs to link approval and refund *)
TestChargeIds == {Num(1), Num(2)}

(* Time differences between approval and refund events *)
(* 1s: very quick approval, should be within window *)
(* 29min: just under 30min, should be within window *)
(* 30min: exactly 30min, should be within window (inclusive interpretation) *)
(* 30min + 1s: just over 30min, should be outside window *)
(* 60min: clearly too old, should be outside window *)
TestTimeDiffs == {1, 29 * Minute, 30 * Minute, 30 * Minute + 1, 60 * Minute}

(* --- Session construction --- *)
(* An approval event for a given charge_id at a specific time *)
ApprovalEvent(cid, t) == Ev("request_approval", "request", [charge_id |-> cid], NoFields, t)

(* A refund event for a given charge_id and amount at a specific time *)
RefundEvent(cid, amt, t) == Ev("issue_refund", "request", [charge_id |-> cid, amount |-> amt], NoFields, t)

(* A session consisting of an approval followed by a refund for the same charge_id *)
(* The approval happens at t=1, the refund at t=1+time_diff. *)
(* The times are chosen arbitrarily but consistently for relative duration testing. *)
TestSession(cid, amt, time_diff) == <<
    ApprovalEvent(cid, 1),
    RefundEvent(cid, amt, 1 + time_diff)
>>

(* Decides if the refund event (the second event) in the constructed session is granted *)
GrantsRefund(cid, amt, time_diff) == DecideOnEvent(TestSession(cid, amt, time_diff), 2)

(* --- Model variables --- *)
VARIABLE charge_id_v, amount_v, time_diff_v

Init ==
    charge_id_v \in TestChargeIds /\
    amount_v \in TestAmounts /\
    time_diff_v \in TestTimeDiffs

Next == UNCHANGED <<charge_id_v, amount_v, time_diff_v>>

Spec == Init /\ [][Next]_<<charge_id_v, amount_v, time_diff_v>>

(* --- The Claim: "A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes." --- *)

(* This invariant states that if the refund amount is over $500 AND the approval event *)
(* occurred more than 30 minutes before the refund, then the policy MUST deny the refund. *)
SupervisorApprovalNotMetDeniesRefund ==
    (amount_v > MinAmountForApproval /\ time_diff_v > ApprovalWindowSeconds)
    => ~GrantsRefund(charge_id_v, amount_v, time_diff_v)

=============================================================================
