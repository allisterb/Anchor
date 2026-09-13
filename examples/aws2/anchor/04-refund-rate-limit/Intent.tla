---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Constants for time and policy limits *)
Minute == 60
Hour == 60 * Minute

(* Helper to create a refund event *)
RefundEvent(time, acc) ==
    Ev("issue_refund", "request", [account |-> acc], NoFields, time)

(*
  A session tracing four refund attempts for a given account.
  The first three refunds happen quickly at t=0, t=1, t=2.
  The fourth refund happens at t=2+timeGap.
  The 'timeGap' variable represents the duration between the third and fourth event.
  The total span from the first event (t=0) to the fourth event is (2 + timeGap).
*)
TestTrace(acc, timeGap) ==
    << RefundEvent(0, acc),
       RefundEvent(1, acc),
       RefundEvent(2, acc),
       RefundEvent(2 + timeGap, acc) >>

(* Get the verdict for a specific event index in the trace *)
VerdictForEvent(acc, timeGap, eventIdx) ==
    D!Decide(TestTrace(acc, timeGap), Policies, eventIdx, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
(***************************************************************************)
accountValues == {Num(1), Num(2)} (* From the policy's vocabulary *)

(*
  Test time gaps. The critical threshold for the 4th event is 'Hour' from the first event (at t=0).
  We test scenarios where the 4th event occurs:
  - At t=3 (timeGap=1): Clearly within the 1-hour window.
  - At t=Hour-1 (timeGap=Hour-3): Just before the 1-hour mark.
  - At t=Hour (timeGap=Hour-2): Exactly at the 1-hour mark.
  - At t=Hour+1 (timeGap=Hour-1): Just after the 1-hour mark.
  - At t=Hour+2 (timeGap=Hour): Further after the 1-hour mark.
  - At t=Hour*2+2 (timeGap=Hour*2): Well after the 1-hour mark.
*)
TimeGapsToTest == {1, Hour - 3, Hour - 2, Hour - 1, Hour, Hour * 2}

VARIABLE currentAccount
VARIABLE currentTimeGap

Init == currentAccount \in accountValues /\ currentTimeGap \in TimeGapsToTest
Next == UNCHANGED currentAccount /\ UNCHANGED currentTimeGap
Spec == Init /\ [][Next]_<<currentAccount, currentTimeGap>>

(***************************************************************************)
(* THE CLAIMS.                                                             *)
(* "The agent might attempt no more than three refunds against the same    *)
(* account within one hour."                                               *)
(* This means:                                                             *)
(* 1. The first three refunds in any sequence for an account should always *)
(*    be ALLOWED, provided they occur at distinct times.                   *)
(* 2. The fourth refund in a sequence for an account should be DENIED if   *)
(*    it occurs within one hour of the *first* refund in that sequence.   *)
(* 3. The fourth refund should be ALLOWED if it occurs *after* one hour    *)
(*    from the *first* refund in that sequence. This implies the rate-    *)
(*    limit window has passed or reset.                                   *)
(***************************************************************************)

(* Claim 1: First three refunds are always allowed *)
FirstRefundForAccountAllowed ==
    VerdictForEvent(currentAccount, currentTimeGap, 1)

SecondRefundForAccountAllowed ==
    VerdictForEvent(currentAccount, currentTimeGap, 2)

ThirdRefundForAccountAllowed ==
    VerdictForEvent(currentAccount, currentTimeGap, 3)

(* Calculate the total time elapsed from the first event (t=0) to the fourth event *)
TotalSpanToFourthEvent(gap) == 2 + gap

(* Claim 2: Fourth refund is denied if its total span from the first event is within the 1-hour window *)
FourthRefundDeniedIfWithinWindow ==
    (TotalSpanToFourthEvent(currentTimeGap) <= Hour) => ~VerdictForEvent(currentAccount, currentTimeGap, 4)

(* Claim 3: Fourth refund is allowed if its total span from the first event is outside the 1-hour window *)
FourthRefundAllowedIfOutsideWindow ==
    (TotalSpanToFourthEvent(currentTimeGap) > Hour) => VerdictForEvent(currentAccount, currentTimeGap, 4)

=============================================================================
