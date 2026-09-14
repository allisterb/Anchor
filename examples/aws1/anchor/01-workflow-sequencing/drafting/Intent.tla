"""
---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(* Helper to decide a trace *)
DecideTrace(trace, index) == D!Decide(trace, Policies, index, AllValues)

(* Define event types for clarity *)
GetClientProfile(t) == Ev("get_client_profile", "request", NoFields, NoFields, t)
LoadPortfolio(t)    == Ev("load_portfolio", "request", NoFields, NoFields, t)
RebalancePortfolio(t) == Ev("rebalance_portfolio", "request", NoFields, NoFields, t)

(* Define the 'good' sequence session: Get -> Load -> Rebalance *)
GoodSequenceSession(t_start, g1, g2) ==
    << GetClientProfile(t_start),
       LoadPortfolio(t_start + g1),
       RebalancePortfolio(t_start + g1 + g2) >>

(* Define 'bad' sequence sessions based on missing or out-of-order prerequisites *)

(* Bad Sequence 1: Rebalance after only Load (missing GetClientProfile) *)
BadSequence_LoadRebalance(t_start, g1) ==
    << LoadPortfolio(t_start),
       RebalancePortfolio(t_start + g1) >>

(* Bad Sequence 2: Rebalance after only Get (missing LoadPortfolio) *)
BadSequence_GetRebalance(t_start, g1) ==
    << GetClientProfile(t_start),
       RebalancePortfolio(t_start + g1) >>

(* Bad Sequence 3: Rebalance alone *)
BadSequence_RebalanceAlone(t_start) ==
    << RebalancePortfolio(t_start) >>

(* Bad Sequence 4: Load -> Get -> Rebalance (wrong order) *)
BadSequence_LoadGetRebalance(t_start, g1, g2) ==
    << LoadPortfolio(t_start),
       GetClientProfile(t_start + g1),
       RebalancePortfolio(t_start + g1 + g2) >>

(* Gaps and time ranges for non-determinism *)
TimeOffsets == {1} (* Start all sessions at time 1 *)
Gaps        == {1, 60} (* 1 second, 1 minute gaps to test distinctness and small time windows *)

(* Variables for the model checker to explore different session timings *)
VARIABLE time_offset, gap1, gap2

Init == /\ time_offset \in TimeOffsets
        /\ gap1 \in Gaps
        /\ gap2 \in Gaps
Next == UNCHANGED <<time_offset, gap1, gap2>>
Spec == Init /\ [][Next]_<<time_offset, gap1, gap2>>

(* Invariants stating the policy's intended behavior *)

(* Claim 1: The full, correct sequence should permit the rebalance *)
CorrectSequencePermitsRebalance ==
    DecideTrace(GoodSequenceSession(time_offset, gap1, gap2), 3)

(* Claim 2: Rebalance after only Load should be refused *)
RebalanceAfterLoadRefused ==
    ~DecideTrace(BadSequence_LoadRebalance(time_offset, gap1), 2)

(* Claim 3: Rebalance after only Get should be refused *)
RebalanceAfterGetRefused ==
    ~DecideTrace(BadSequence_GetRebalance(time_offset, gap1), 2)

(* Claim 4: Rebalance alone should be refused *)
RebalanceAloneRefused ==
    ~DecideTrace(BadSequence_RebalanceAlone(time_offset), 1)

(* Claim 5: Rebalance after Load -> Get (wrong order) should be refused *)
RebalanceWrongOrderRefused ==
    ~DecideTrace(BadSequence_LoadGetRebalance(time_offset, gap1, gap2), 3)

=============================================================================
""