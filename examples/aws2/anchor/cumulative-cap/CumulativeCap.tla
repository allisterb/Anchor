---------------------------- MODULE CumulativeCap ----------------------------
\* What the policy is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\* Constants for the policy logic
TwelveHours == 12 * 60 * 60  \* 12 hours in seconds
CapAmount   == 50000         \* The cumulative cap amount in dollars

\* Helper function to create an initiate_transfer event
\* time_val, amount_val, and acc_val are plain integers for calculation and Ev() function
\* arguments; they are wrapped in Num() for the input record fields.
TransferEvent(time_val, amount_val, acc_val) ==
  Ev("initiate_transfer", "request",
     [amount |-> Num(amount_val),
      account |-> Num(acc_val),
      charge_id |-> Num(1), \* Fixed charge_id, as it's not relevant to this property
      systemNowTime |-> Num(time_val)],
     NoFields,
     time_val)

\* A session with two transfers for the same account: a previous one and a current one.
\* p_a: amount of the previous transfer (plain integer)
\* c_a: amount of the current transfer (plain integer)
\* g:   time gap in seconds between the two transfers (plain integer)
\* acc: account ID (plain integer)
Session(p_a, c_a, g, acc) ==
  <<TransferEvent(1, p_a, acc),           \* Previous transfer at time 1
    TransferEvent(1 + g, c_a, acc)>>      \* Current transfer at time (1 + gap)

\* The verdict for the final transfer in the session
GrantsFinalTransfer(p_a, c_a, g, acc) ==
  D!Decide(Session(p_a, c_a, g, acc), Policies, 2, AllValues) \* Check decision for the 2nd event

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

\* Define relevant amounts that can make the cumulative sum exceed the cap.
\* These are plain integers, as used in the `TransferEvent` helper.
PrevAmounts == {1000, 20000, 30000, 49000, 49999}
CurrAmounts == {1000, 20000, 30000, 49000, 49999}

\* Define time gaps to test scenarios both within and outside the 12-hour window.
\* Gaps are plain integers (seconds).
Gaps == {1,              \* Almost immediate (within window)
        TwelveHours - 1, \* Just under 12 hours (within window)
        TwelveHours + 1, \* Just over 12 hours (outside window)
        2 * TwelveHours  \* Well over 12 hours (outside window)
       }

\* Define account IDs. Using plain integers here.
AccountValues == {1, 2} \* As per the input domain in the vocabulary

\* One specific scenario, chosen nondeterministically, to check the property.
\* The variables hold plain integer values.
VARIABLE prev_a, curr_a, gap, account_id
Init == prev_a \in PrevAmounts /\
        curr_a \in CurrAmounts /\
        gap \in Gaps /\
        account_id \in AccountValues
Next == UNCHANGED <<prev_a, curr_a, gap, account_id>>
Spec == Init /\ [][Next]_<<prev_a, curr_a, gap, account_id>>

(***************************************************************************)
(* THE CLAIM: Block a transfer if the total amount transferred in the      *)
(* past 12 hours (including the current transfer) would exceed $50,000.   *)
(***************************************************************************)

\* Calculate the total amount that would be considered for the cap.
\* This includes the previous transfer only if it falls within the 12-hour window.
TotalAmountForCap(p_a_val, c_a_val, g_val) ==
  LET prev_amount_in_window == IF g_val < TwelveHours THEN p_a_val ELSE 0 IN
  prev_amount_in_window + c_a_val

\* The main property: If the total amount exceeds the cap, the policy must refuse the transfer.
BlockIfCumulativeCapExceeded ==
  (TotalAmountForCap(prev_a, curr_a, gap) > CapAmount)
  => ~GrantsFinalTransfer(prev_a, curr_a, gap, account_id)

=============================================================================
