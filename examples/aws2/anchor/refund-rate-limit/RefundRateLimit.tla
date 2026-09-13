---------------------------- MODULE RefundRateLimit ----------------------------
\* What RefundRateLimit is SUPPOSED to mean, stated by its author. The three built-in findings
\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\* other kind, and only the author can write it.
\*
\* SAVE THIS AS RefundRateLimit.tla -- TLA+ requires the file name to match the module name, and a
\* module name may not contain `-` or `.` or begin with a digit, so it is not always the policy's
\* own name.
\*
\* Check it with:  python src/checker/properties.py agent-policy.dw --property RefundRateLimit.tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(***************************************************************************)
(* CONSTANTS AND DOMAINS FOR THIS CLAIM                                    *)
(***************************************************************************)
\* The claim is about refunds on specific accounts.
AccountIDs == {Num(1), Num(2)}

\* One hour in seconds.
Hour == 3600

\* We construct sessions of 4 refund requests. The first three happen very
\* quickly at t=1, t=2, t=3. The fourth refund's time (t4_val) is varied
\* to test the rate limit boundary.
\* We test times that are:
\* - very soon after (e.g., t=4)
\* - just before the 1-hour mark (e.g., t=3599)
\* - exactly at the 1-hour mark (e.g., t=3600)
\* - just after the 1-hour mark (e.g., t=3601)
\* All t4_val must be strictly greater than t3=3.
T4_Values == {t \in {4, Hour-1, Hour, Hour+1} : t > 3}

(***************************************************************************)
(* HELPER FUNCTIONS FOR CONSTRUCTING SESSIONS                              *)
(***************************************************************************)
\* A single refund event for a given account at a given time.
\* The action and kind are plain strings, time is a plain integer.
\* Input field values are tagged (Num).
RefundEv(t, account_id) == 
  Ev("issue_refund", "request", [account |-> account_id], NoFields, t)

\* A session consisting of 4 refund requests for the same account.
\* The first three are at t=1, t=2, t=3. The fourth is at t_fourth.
Session4Refunds(account_id, t_fourth) == 
  <<RefundEv(1, account_id), RefundEv(2, account_id), RefundEv(3, account_id), RefundEv(t_fourth, account_id)>>

(***************************************************************************)
(* STATE MACHINE DEFINITION                                                *)
(*                                                                         *)
(* Variables accountID and t4_val are chosen nondeterministically and      *)
(* held constant for each model checking run.                              *)
(***************************************************************************)
VARIABLE accountID, t4_val

Init == 
  accountID \in AccountIDs /\ 
  t4_val \in T4_Values

Next == 
  UNCHANGED <<accountID, t4_val>>

Spec == 
  Init /\ [][Next]_<<accountID, t4_val>>

(***************************************************************************)
(* THE CLAIM: No more than three refunds against the same account within   *)
(* one hour. This means the 4th refund should be refused if the time span *)
(* from the 1st to the 4th is less than one hour.                          *)
(***************************************************************************)
RefundRateLimitHolds == 
  \* Condition: The time span between the first and the fourth refund is less than one hour.
  (t4_val - 1 < Hour) 
  => 
  \* Consequence: The policy must REFUSE the fourth refund in this session.
  ~D!Decide(Session4Refunds(accountID, t4_val), Policies, 4, AllValues)

=============================================================================
