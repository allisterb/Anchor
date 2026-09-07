---------------------------- MODULE Bug4_UnboundedRetry ----------------------------
(***************************************************************************)
(* TaskLifecycle with the retry budget removed: ScheduleRetry no longer    *)
(* checks `retries < MaxRetries` and no longer consumes one.               *)
(*                                                                         *)
(* This is the paper's TL14 read at its word -- "a sub-task in             *)
(* RETRY_SCHEDULED transitions to DISPATCHING if the retry policy permits" *)
(* -- with a retry policy that always permits. Nothing in Table 2 says a   *)
(* retry policy has to be bounded.                                        *)
(*                                                                         *)
(* TL1 then fails, and TLC reports it as a lasso: FAILED ->               *)
(* RETRY_SCHEDULED -> DISPATCHING -> IN_PROGRESS -> FAILED, forever.      *)
(*                                                                         *)
(* So TL1 is not a free-standing property of the lifecycle. It is a       *)
(* constraint ON the retry policy, and the paper leaves that implicit.    *)
(* Same shape as Bug2_FreeRetry: termination rests on every pass through  *)
(* the loop consuming something finite.                                   *)
(***************************************************************************)
(* The per-subtask lifecycle from Allegrini, Shreekumar & Celik,           *)
(* "Formalizing the Safety, Security, and Functional Properties of Agentic *)
(* AI Systems" (arXiv:2510.14133v2), Table 2.                              *)
(*                                                                         *)
(* The paper states TL1-TL14 in CTL and does not check them -- its own     *)
(* conclusion defers that to future work. This is that check.              *)
(*                                                                         *)
(* TRANSLATION NOTES. The paper's AG/AF/AX map onto TLA+ as [] / <> /      *)
(* [][...]_vars. Its two reachability properties use EF, which has no TLA+ *)
(* form at all -- TLA+ is linear-time and has no existential path          *)
(* quantifier -- so those are not translated here. The equivalent is to    *)
(* check []~P and read TLC's violation trace as the witness.               *)
(*                                                                         *)
(* TL7, TL8 and TL10 are stated over "previous state", so the model        *)
(* carries `prev` explicitly. That is a real cost of the paper's phrasing: *)
(* history in the state space, rather than properties over actions.        *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS
    MaxRetries,     \* how many times the retry policy will re-dispatch
    MaxFallbacks    \* how many alternative entities are available

ASSUME LifecycleAssumption ==
    /\ MaxRetries \in Nat
    /\ MaxFallbacks \in Nat

States ==
    { "CREATED", "READY", "AWAITING_DEPENDENCY", "DISPATCHING", "IN_PROGRESS",
      "COMPLETED", "FAILED", "RETRY_SCHEDULED", "FALLBACK_SELECTED", "ERROR", "CANCELED" }

Terminal == { "COMPLETED", "ERROR", "CANCELED" }

VARIABLES
    state,          \* current lifecycle state
    prev,           \* the state before it; TL7/TL8/TL10 are stated over this
    retries,        \* retries consumed so far
    fallbacks       \* alternative entities still untried

vars == <<state, prev, retries, fallbacks>>

TypeOK ==
    /\ state \in States
    /\ prev \in States
    /\ retries \in 0..MaxRetries
    /\ fallbacks \in 0..MaxFallbacks

Init ==
    /\ state = "CREATED"
    /\ prev = "CREATED"
    /\ retries = 0
    /\ fallbacks = MaxFallbacks

\* Every transition records where it came from, so the history-dependent
\* properties have something to refer to.
To(s) == /\ state' = s
         /\ prev' = state

(***************************************************************************)
(* TRANSITIONS                                                             *)
(*                                                                         *)
(* Derived from the paper's constraints rather than given by it: Table 2   *)
(* specifies which transitions are legal (TL7, TL8, TL10, TL12-TL14) but   *)
(* never draws the machine. Anywhere the paper is silent the model admits  *)
(* the nondeterminism rather than choosing, so a property that depends on  *)
(* a choice the paper did not make will fail here rather than pass by      *)
(* accident.                                                               *)
(***************************************************************************)

\* A task either needs a dependency resolved first, or is immediately runnable.
Start ==
    /\ state = "CREATED"
    /\ \E s \in {"READY", "AWAITING_DEPENDENCY"} : To(s)
    /\ UNCHANGED <<retries, fallbacks>>

\* TL6: satisfied dependencies eventually lead to READY. The dependency being
\* satisfied is the environment's choice, not the task's.
DependencyResolved ==
    /\ state = "AWAITING_DEPENDENCY"
    /\ To("READY")
    /\ UNCHANGED <<retries, fallbacks>>

\* TL2: a READY task needing an external entity eventually dispatches.
Dispatch ==
    /\ state \in {"READY", "FALLBACK_SELECTED", "RETRY_SCHEDULED"}   \* TL7
    /\ To("DISPATCHING")
    /\ UNCHANGED <<retries, fallbacks>>

\* TL4: DISPATCHING always reaches IN_PROGRESS.
Accepted ==
    /\ state = "DISPATCHING"
    /\ To("IN_PROGRESS")
    /\ UNCHANGED <<retries, fallbacks>>

\* TL8: COMPLETED is reachable only from IN_PROGRESS.
Succeed ==
    /\ state = "IN_PROGRESS"
    /\ To("COMPLETED")
    /\ UNCHANGED <<retries, fallbacks>>

Fail ==
    /\ state = "IN_PROGRESS"
    /\ To("FAILED")
    /\ UNCHANGED <<retries, fallbacks>>

(***************************************************************************)
(* What a FAILED task may do next -- TL12 and TL13.                        *)
(*                                                                         *)
(* TL14 says a RETRY_SCHEDULED task dispatches "if the retry policy        *)
(* permits", and the paper never says what a retry policy is. Modelled     *)
(* here as a budget, because that is the only reading under which TL1      *)
(* holds. See the note on TL1 below.                                       *)
(***************************************************************************)

ScheduleRetry ==
    /\ state = "FAILED"
    /\ To("RETRY_SCHEDULED")                \* TL10: only from FAILED
    /\ retries' = retries
    /\ UNCHANGED fallbacks

SelectFallback ==
    /\ state = "FAILED"
    /\ fallbacks > 0
    /\ To("FALLBACK_SELECTED")
    /\ fallbacks' = fallbacks - 1
    /\ UNCHANGED retries

\* TL3 allows FALLBACK_SELECTED to fail outright rather than dispatch.
FallbackFailed ==
    /\ state = "FALLBACK_SELECTED"
    /\ To("FAILED")
    /\ UNCHANGED <<retries, fallbacks>>

\* Only from FAILED. TL3 lists the successors of FALLBACK_SELECTED as DISPATCHING,
\* CANCELED or FAILED -- ERROR is not among them, so a task that has selected a
\* fallback must go back through FAILED to reach ERROR rather than erroring where
\* it stands. Permitting the direct edge was this model's first mistake and TL3
\* rejected it; if a real implementation does allow it, TL3 is what needs amending.
GiveUp ==
    /\ state = "FAILED"
    /\ \E s \in {"ERROR", "CANCELED"} : To(s)
    /\ UNCHANGED <<retries, fallbacks>>

\* A task may be cancelled from any non-terminal state.
Cancel ==
    /\ state \notin Terminal
    /\ To("CANCELED")
    /\ UNCHANGED <<retries, fallbacks>>

Next ==
    \/ Start
    \/ DependencyResolved
    \/ Dispatch
    \/ Accepted
    \/ Succeed
    \/ Fail
    \/ ScheduleRetry
    \/ SelectFallback
    \/ FallbackFailed
    \/ GiveUp
    \/ Cancel

\* Weak fairness on everything: no action that stays enabled is ignored forever.
\* Without it nothing below the liveness heading holds, because a task could
\* simply stop.
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(* LIVENESS (TL1-TL6)                                                      *)
(*                                                                         *)
(* TL1 is the load-bearing one and it constrains the retry policy, which    *)
(* the paper leaves implicit. FAILED -> RETRY_SCHEDULED -> DISPATCHING ->   *)
(* IN_PROGRESS -> FAILED is a legal cycle under TL10, TL7 and TL14 as       *)
(* stated; if the retry policy permits unboundedly, the task never reaches  *)
(* a terminal state and TL1 fails. Bug4_UnboundedRetry.tla is that model.   *)
(***************************************************************************)

TL1 == <>(state \in Terminal)
TL3 == [](state = "FALLBACK_SELECTED" => <>(state \in {"DISPATCHING", "CANCELED", "FAILED"}))
TL5 == [](state = "AWAITING_DEPENDENCY" => <>(state /= "AWAITING_DEPENDENCY"))

(***************************************************************************)
(* TL4 AS THE PAPER STATES IT DOES NOT HOLD, and the reason is not a       *)
(* modelling artifact.                                                     *)
(*                                                                         *)
(*   TL4 == [](state = "DISPATCHING" => <>(state = "IN_PROGRESS"))         *)
(*                                                                         *)
(* Read literally it forbids cancelling a task while it is being           *)
(* dispatched: once in DISPATCHING the task MUST reach IN_PROGRESS, so no  *)
(* cancellation, timeout or shutdown may intervene. TLC finds the two-step *)
(* counterexample immediately -- Dispatch then Cancel.                     *)
(*                                                                         *)
(* That is not a realistic constraint. Strands, for one, exposes           *)
(* agent.cancel() and a cancel_signal precisely so in-flight work can be   *)
(* abandoned. The same objection applies to the paper's TL2.               *)
(*                                                                         *)
(* Weakened below to admit cancellation. The divergence from the paper is  *)
(* deliberate and is the finding, not a fix applied quietly.               *)
(***************************************************************************)
TL4_AsPublished == [](state = "DISPATCHING" => <>(state = "IN_PROGRESS"))

TL4 == [](state = "DISPATCHING" => <>(state \in {"IN_PROGRESS", "CANCELED"}))

(***************************************************************************)
(* SAFETY (TL7-TL11). TL7, TL8 and TL10 are invariants over `prev`;        *)
(* TL9 and TL11 are AX properties, so actions rather than invariants.      *)
(***************************************************************************)

TL7 == state = "DISPATCHING" => prev \in {"READY", "FALLBACK_SELECTED", "RETRY_SCHEDULED"}
TL8 == state = "COMPLETED" => prev = "IN_PROGRESS"
TL10 == state = "RETRY_SCHEDULED" => prev = "FAILED"

TL9 == [][ state = "ERROR" => state' = "ERROR" ]_vars
TL11 == [][ state = "CANCELED" => state' = "CANCELED" ]_vars

(***************************************************************************)
(* TRANSITION CONSTRAINTS (TL12-TL14)                                      *)
(***************************************************************************)

TL12 == [][ (state = "FAILED" /\ fallbacks = 0)
              => state' \in {"RETRY_SCHEDULED", "ERROR", "CANCELED", "FAILED"} ]_vars

TL13 == [][ (state = "FAILED" /\ fallbacks > 0)
              => state' \in {"RETRY_SCHEDULED", "FALLBACK_SELECTED", "ERROR", "CANCELED", "FAILED"} ]_vars

TL14 == [][ state = "RETRY_SCHEDULED" => state' \in {"DISPATCHING", "CANCELED"} ]_vars

=============================================================================
