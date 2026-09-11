(***************************************************************************)
(* VACUITY, for an arbitrary Dogwood policy file.                          *)
(*                                                                         *)
(* The question: can permit number `Target` ever actually grant anything?  *)
(* A permit that no session can make fire is not a weak control, it is     *)
(* ZERO control, and nothing about its text says so. It parses, it         *)
(* validates, it is satisfiable in isolation, and it never authorizes a    *)
(* single request. That is the cheapest useful question to ask about a     *)
(* session-aware policy, and AWS's own material says their analysis tools  *)
(* do not answer it for the temporal part of the language.                 *)
(*                                                                         *)
(* HOW IT IS ASKED. TLA+ is linear-time and has no `EF`, so reachability   *)
(* is not directly expressible. The standard move is to check the NEGATION *)
(* as an invariant and read the counterexample as the witness:             *)
(*                                                                         *)
(*     INVARIANT NeverFires        "this permit never grants anything"     *)
(*                                                                         *)
(*   TLC reports a violation  ->  a session exists that makes it grant.    *)
(*                                The trace IS that session. NOT vacuous.  *)
(*   TLC completes clean      ->  no session of up to MaxAttempts does.    *)
(*                                VACUOUS within the bound -- the finding. *)
(*                                                                         *)
(* So a "failing" run is the good outcome and a clean one is the alarm.    *)
(* `tests/strands/vacuity.py` inverts it before reporting, because that    *)
(* reading is a trap for anyone who glances at raw TLC output.             *)
(*                                                                         *)
(* WHAT IS DIFFERENT FROM TemporalPolicy.tla, which asks the same question *)
(* of one hand-written policy set. Two things, and both are the point:     *)
(*                                                                         *)
(*   - The policies come from `PolicyUnderTest`, GENERATED from `.dw` text *)
(*     by tests/strands/vacuity.py. Nobody paraphrases the policy into     *)
(*     TLA+ by hand, so nothing is lost between what was written and what  *)
(*     is checked.                                                         *)
(*   - The decision is `DogwoodSemantics!Decide`, the evaluator that       *)
(*     agrees with the real Dogwood engine on 774 recorded corpus pairs    *)
(*     and on the live `error`-event scenarios. TemporalPolicy.tla instead *)
(*     carries its own `PermitFires`, which is a second reading of the     *)
(*     same language with nothing holding the two together.                *)
(*                                                                         *)
(* Together those make the deliverable "hand us a Dogwood policy and we    *)
(* will model-check it" rather than "here is a policy we modelled".        *)
(***************************************************************************)
---------------------------------- MODULE Vacuity ----------------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

CONSTANTS
    MaxAttempts,    \* bound on session length, in attempts (two events each)
    MaxAmount,      \* bound on the numeric domain input fields range over
    Target          \* index into Policies of the permit under test

ASSUME VacuityAssumption ==
    /\ MaxAttempts \in Nat /\ MaxAttempts > 0
    /\ MaxAmount \in Nat /\ MaxAmount > 0
    /\ Target \in DOMAIN Policies
    /\ Policies[Target].effect = "permit"

\* `Cases` is only read by DogwoodSemantics!Agree, which this module never calls;
\* the evaluator's Decide takes its trace and policies as arguments.
D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(***************************************************************************)
(* Scalars carry their kind, because TLC refuses to compare a string with  *)
(* an integer and refuses `"alice" \in Int` as a type test. Every value    *)
(* the evaluator sees is tagged and compared kind-first.                   *)
(***************************************************************************)
Str(x)  == [k |-> "s", v |-> x]
Num(x)  == [k |-> "n", v |-> x]
Bool(x) == [k |-> "b", v |-> x]

\* Principal and resource are held fixed. Vacuity is a question about the
\* temporal condition; varying the scope would multiply the state space to
\* explore a dimension no temporal operator reads.
Anon == Str("caller")

Amounts == 1..MaxAmount

\* The domain a bound variable of non-Timepoint type ranges over -- what
\* `count`/`sum ... for (a: Long)` quantifies across.
Values == {Num(x) : x \in Amounts}

MaxTime == 2 * MaxAttempts

VARIABLES
    trace,      \* the session's recorded trajectory -- all the engine can see
    fired       \* indices of permits that have actually GRANTED something

vars == <<trace, fired>>

TypeOK ==
    /\ fired \subseteq DOMAIN Policies
    /\ Len(trace) \in 0..MaxTime

Init ==
    /\ trace = << >>
    /\ fired = {}

(***************************************************************************)
(* Events carry exactly the fields the evaluator reads: action, kind,      *)
(* input, output, principal, resource, time.                              *)
(*                                                                         *)
(* `InputFields` and `OutputFields` are generated from the policy text --  *)
(* only fields some condition actually reads are modelled, so a policy     *)
(* that joins on nothing costs nothing to check.                           *)
(***************************************************************************)
Input(amount)    == [f \in InputFields  |-> Num(amount)]
Output(approved) == [f \in OutputFields |-> Bool(approved)]

Event(action, kind, amount, approved, t) ==
    [time      |-> t,
     action    |-> action,
     kind      |-> kind,
     input     |-> Input(amount),
     output    |-> Output(approved),
     principal |-> Anon,
     resource  |-> Anon]

(***************************************************************************)
(* THE DECISION -- deny by default, forbid overrides permit. Cedar's       *)
(* model, which Dogwood keeps, and here it is Dogwood's own evaluator      *)
(* rather than a restatement of it.                                       *)
(***************************************************************************)
Hit(h, idx) ==
    {k \in DOMAIN Policies : D!PolicyMatches(Policies[k], h, idx, h[idx], Values)}

Allowed(h, idx) == D!Decide(h, Policies, idx, Values)

\* A permit GRANTED only when it matched and the request was allowed. A permit
\* that matches but is always overridden by a forbid authorizes nothing, and
\* counting it as fired would report an inert policy as live -- the exact
\* mistake this spec exists to catch.
Granted(h, idx) ==
    IF Allowed(h, idx)
    THEN {k \in Hit(h, idx) : Policies[k].effect = "permit"}
    ELSE {}

(***************************************************************************)
(* TRANSITIONS                                                             *)
(*                                                                         *)
(* One attempt appends two events: the decision event, then its outcome.   *)
(* The outcome kind is AgentCore's convention and is what the whole        *)
(* `::response` / `::request` finding turns on -- permitted-and-completed  *)
(* is recorded as `response`, DENIED is recorded as `error`, and the       *)
(* request event is recorded either way.                                   *)
(*                                                                         *)
(* Note the attempt is NOT conditioned on being allowed. A denied attempt  *)
(* still writes a `request` event, and a permit gated on `::request` can   *)
(* fire off nothing but refusals. Requiring the decision here would hide   *)
(* precisely the case worth finding.                                       *)
(***************************************************************************)
Attempt(action, amount, approved) ==
    /\ Len(trace) + 2 <= MaxTime
    /\ LET t       == Len(trace) + 1
           withReq == Append(trace, Event(action, DecisionKind, amount, FALSE, t))
           idx     == Len(withReq)
           ok      == Allowed(withReq, idx)
           outcome == IF ok THEN Event(action, "response", amount, approved, t + 1)
                            ELSE Event(action, "error", amount, FALSE, t + 1)
       IN /\ trace' = Append(withReq, outcome)
          /\ fired' = fired \union Granted(withReq, idx)

\* The agent may attempt anything, with any input, and an approver may return
\* either verdict. All of it is behaviour, so a VACUOUS result holds whatever
\* the agent and the approver do -- which is what makes it worth stating.
Next ==
    \E action \in Actions, amount \in Amounts, approved \in BOOLEAN :
        Attempt(action, amount, approved)

\* No fairness. Vacuity is a reachability question -- does ANY session make this
\* permit grant -- so nothing needs to be forced to happen.
Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* THE PROPERTY. Checked as an invariant and MEANT TO FAIL; see the header.*)
(***************************************************************************)
NeverFires == Target \notin fired

=============================================================================
