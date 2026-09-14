---------------------------- MODULE CumulativeCap ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Constants for time and amount *)
OneHour == 3600 (* seconds *)
TwelveHours == 12 * OneHour (* 43200 seconds *)
CapAmount == Num(50000) (* $50,000, using Num constructor *)

(* Helper to create an initiate_transfer event with dummy values for other required input fields *)
Transfer(amount_val, time_val) ==
    Ev("initiate_transfer", "request",
       [account |-> Num(1), amount |-> amount_val, charge_id |-> Num(1), systemNowTime |-> Num(32400000)],
       NoFields, time_val)

(* Session definition: two transfers, separated by time_delta *)
Session(amt1, amt2, td) ==
    << Transfer(amt1, 1), Transfer(amt2, 1 + td) >>

(* Function to calculate cumulative amount of 'initiate_transfer' events
   within the 12-hour window *before* the event at 'idx'.
   Amounts are tagged with Num(). SUM operator works with sets of numbers. *)
CumulativeAmountBeforeEvent(trace, idx) ==
    LET current_event == trace[idx]
        current_time == current_event.time
        relevant_transfers_amounts == { e.input.amount : e \in {trace[j] : j \in 1..idx-1} :
                                (e.action = "initiate_transfer") /\
                                (current_time - e.time < TwelveHours) /\ (* Event must be within the past 12 hours *)
                                (e.time < current_time) }                 (* Event must have occurred before current_time *)
    IN IF relevant_transfers_amounts = {} THEN Num(0)
       ELSE SUM relevant_transfers_amounts

(* Policy decision for a specific event in a session *)
PolicyDecision(session, event_idx) ==
    D!Decide(session, Policies, event_idx, AllValues)

(* State space for testing:
   TestAmounts includes values that can cross the cap when combined.
   TimeGaps includes values within and outside the 12-hour window. *)
TestAmounts == {Num(1), Num(25000), Num(25001), Num(49999), Num(50000), Num(50001)}
TimeGaps == {1, OneHour, TwelveHours - 1, TwelveHours, TwelveHours + 1, (2 * 24 * OneHour)} (* 1s, 1h, 11h59m59s, 12h, 12h0m1s, 2 days *)

VARIABLE first_amount, second_amount, time_delta
Init ==
    first_amount \in TestAmounts /\
    second_amount \in TestAmounts /\
    time_delta \in TimeGaps

Next ==
    UNCHANGED <<first_amount, second_amount, time_delta>>

Spec == Init /\ [][Next]_<<first_amount, second_amount, time_delta>>

(* The claim: A transfer should be refused if, including its own amount,
   the cumulative total within the past 12 hours would exceed CapAmount ($50,000). *)
CumulativeCapExceededIsRefused ==
    LET session_trace == Session(first_amount, second_amount, time_delta)
        current_event_idx == 2 (* We are checking the second transfer in our two-event session *)
        amount_current_transfer == session_trace[current_event_idx].input.amount
        cumulative_before == CumulativeAmountBeforeEvent(session_trace, current_event_idx)
        total_if_granted == cumulative_before + amount_current_transfer
    IN (total_if_granted > CapAmount) => ~PolicyDecision(session_trace, current_event_idx)

=============================================================================
