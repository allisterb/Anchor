---------------------------- MODULE Intent ----------------------------
\* What 03-cumulative-cap.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(*
 * Policy intention: Block a transfer if the total amount transferred
 * in the past 12 hours would exceed $50,000.
 *)

(***************************************************************************)
(* CONSTANTS AND DOMAINS FOR TESTING                                       *)
(***************************************************************************)
Minute == 60
Hour == 60 * Minute
TwelveHours == 12 * Hour
Day == 24 * Hour
TwoDays == 2 * Day

(*
 * Amount values to test the $50,000 cap boundary.
 * These are chosen to test scenarios around the limit, including values
 * not explicitly mentioned in the policy's vocabulary but necessary
 * to test the cumulative cap.
 *)
Amount1k == Num(1000)
Amount10k == Num(10000)
Amount40k == Num(40000)
Amount45k == Num(45000)
Amount50k == Num(50000) \* Exactly at the cap, if previous was zero
Amount5k == Num(5000)
Amount60k == Num(60000) \* Already over the cap

AmountsToTest == {Amount1k, Amount5k, Amount10k, Amount40k, Amount45k, Amount50k, Amount60k}

(*
 * Time gaps between transfers to test the 12-hour window.
 *)
TimeGapsToTest == {
    1,                       (* Very short gap, definitely within window *)
    TwelveHours - 1,         (* Just before the window closes *)
    TwelveHours,             (* Exactly at the window boundary *)
    TwelveHours + 1,         (* Just after the window closes *)
    TwoDays                  (* Well outside the window *)
}

(***************************************************************************)
(* HELPER OPERATORS                                                        *)
(***************************************************************************)

(*
 * Creates a two-event session for testing cumulative conditions.
 * The first event is at time 1, the second at 1 + gap_seconds.
 *)
TransferSession(initial_val, current_val, gap_seconds) ==
    << Ev("initiate_transfer", "request", [amount |-> initial_val], NoFields, 1),
       Ev("initiate_transfer", "request", [amount |-> current_val], NoFields, 1 + gap_seconds) >>

(*
 * Determines if the *second* transfer in the session is granted.
 *)
IsGranted(initial_val, current_val, gap_seconds) ==
    D!Decide(TransferSession(initial_val, current_val, gap_seconds), Policies, 2, AllValues)

(***************************************************************************)
(* STATE MACHINE DEFINITION                                                *)
(***************************************************************************)

(*
 * Variables represent the parameters of the two-transfer scenario
 * being tested in each state.
 *)
VARIABLE initial_transfer_amount, current_transfer_amount, time_since_initial_transfer

(* Initialize variables with values from their defined test domains. *)
Init ==
    initial_transfer_amount \in AmountsToTest /\
    current_transfer_amount \in AmountsToTest /\
    time_since_initial_transfer \in TimeGapsToTest

(* The state variables do not change during the model checking run for a given state. *)
Next == UNCHANGED <<initial_transfer_amount, current_transfer_amount, time_since_initial_transfer>>

(* The overall specification. *)
Spec == Init /\ [][Next]_<<initial_transfer_amount, current_transfer_amount, time_since_initial_transfer>>

(***************************************************************************)
(* THE INTENTIONAL CLAIM                                                   *)
(***************************************************************************)

(*
 * Claim: A transfer is blocked if the sum of its amount and the amount of
 * a previous transfer (within the last 12 hours) exceeds $50,000.
 *
 * This invariant checks that if the conditions for blocking are met,
 * the policy indeed forbids the transfer.
 *)
CumulativeCapIsEnforced ==
    LET
        (* Calculate the sum of the two transfer amounts, extracting integer values. *)
        total_amount_of_two_transfers == initial_transfer_amount.val + current_transfer_amount.val
    IN
        (* Condition for blocking: total amount exceeds 50k AND the previous transfer *)
        (* occurred within the last 12 hours (inclusive).                             *)
        (total_amount_of_two_transfers > 50000 /\ time_since_initial_transfer <= TwelveHours)
        (* Implication: if the condition is true, then the current transfer MUST NOT be granted. *)
        => ~IsGranted(initial_transfer_amount, current_transfer_amount, time_since_initial_transfer)

=============================================================================
