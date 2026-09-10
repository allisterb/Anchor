--------------------------- MODULE SessionRotation ---------------------------
(***************************************************************************)
(* What a caller who controls the session ID can do to a temporal policy.  *)
(*                                                                         *)
(* AgentCore scopes temporal history to a POLICY SESSION, and the session  *)
(* id travels in a caller-supplied header. AWS says what follows, in their *)
(* own security considerations:                                            *)
(*                                                                         *)
(*   "Because temporal history is scoped to a session and the session ID   *)
(*    is supplied by the caller, a count-based limit such as 'at most N    *)
(*    calls per session' counts only the events recorded for that session. *)
(*    Starting a new session begins a new count, so a temporal rate limit  *)
(*    constrains activity within a session rather than across all of a     *)
(*    caller's sessions."                                                  *)
(*                                                                         *)
(* So this is not a discovery. What is not written down is which policy    *)
(* SHAPES survive it, and that turns out to split cleanly -- in opposite   *)
(* directions, from the same cause.                                        *)
(*                                                                         *)
(* THE ASYMMETRY. On a fresh trajectory the history is empty, so:          *)
(*                                                                         *)
(*   a PERMIT gated on a prior event   does not fire -> default deny       *)
(*                                     -> FAILS CLOSED. Rotation costs the *)
(*                                        caller the capability.           *)
(*                                                                         *)
(*   a FORBID on an aggregate          sees sum/count = 0, does not fire   *)
(*                                     -> FAILS OPEN. Rotation hands the   *)
(*                                        caller a fresh allowance.        *)
(*                                                                         *)
(* Budget caps, rate limits and mutual-exclusion rules are all the second  *)
(* shape. Approval gates are the first.                                    *)
(*                                                                         *)
(* THE DECISION IS NOT MODELLED HERE. It comes from DogwoodSemantics,      *)
(* whose reading of `formerly`, `sum` and `tp` agrees with the reference   *)
(* implementation on 654 recorded cases. An earlier version of this spec   *)
(* hand-rolled its own `SumTrades`, which meant the headline finding rested*)
(* on an aggregate nothing had checked. The policies below are written as  *)
(* Dogwood policy DATA and handed to that evaluator, so the only thing     *)
(* this module still asserts on its own is the adversary.                  *)
(*                                                                         *)
(* THE CONTROL MATTERS. `NoRotation_CapHolds.cfg` runs the same policy and *)
(* the same adversary with rotation disabled, and the cap holds. Without   *)
(* that config the violation would not be attributable to rotation.        *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    Limit,          \* the total the policy author means to allow
    MaxAmount,      \* the largest single trade
    MaxSteps,       \* bound on the run
    Gate,           \* "aggregate" (forbid on a sum) or "approval" (permit on a prior event)
    MayRotate       \* whether the caller may start a fresh session

ASSUME RotationAssumption ==
    /\ Limit \in Nat /\ Limit > 0
    /\ MaxAmount \in Nat /\ MaxAmount > 0
    /\ MaxSteps \in Nat /\ MaxSteps > 0
    /\ Gate \in {"aggregate", "approval"}
    /\ MayRotate \in BOOLEAN

Amounts == 1..MaxAmount

\* `Cases` is only read by DogwoodSemantics!Agree, which this module never calls; the
\* evaluator's Decide takes its trace and policies as arguments.
D == INSTANCE DogwoodSemantics WITH Cases <- << >>

(***************************************************************************)
(* THE POLICY SET, as Dogwood policy data                                  *)
(*                                                                         *)
(* aggregate:                                                              *)
(*   permit (principal, action == "Trade", resource);                      *)
(*   forbid (principal, action == "Trade", resource)                       *)
(*   when temporal {                                                       *)
(*     exists (n: Long).                                                   *)
(*       ((sum a for (a: Long), (t: Timepoint).                            *)
(*           where (formerly within W (Trade::request{input.amount: a}     *)
(*                                     && tp(t)))) == n && n > Limit)      *)
(*   };                                                                    *)
(*                                                                         *)
(* approval:                                                               *)
(*   permit (principal, action == "Trade", resource)                       *)
(*   when temporal { formerly within W Approve::request{} };               *)
(*                                                                         *)
(* The `tp(t)` binder is what makes the sum per-EVENT: t is unique to each *)
(* matching event, so two trades of the same amount contribute twice.      *)
(* Without it the sum would range over distinct amounts.                   *)
(***************************************************************************)
Str(x) == [k |-> "s", v |-> x]
Num(x) == [k |-> "n", v |-> x]

EmptyRec == [f \in {} |-> Str("")]
Anon == Str("caller")

\* A window wide enough to cover any run of this length, so the finding is about
\* session scope rather than about the metric bound.
Window == 1000

DummyPred == [action |-> "", kind |-> "", binds |-> << >>]
DummyAtom == [op |-> "pred", pred |-> DummyPred, var |-> "", args |-> << >>]
DummyTerm == [op |-> "formerly", window |-> 0, atom |-> DummyAtom,
              left |-> DummyAtom, leftNeg |-> FALSE]

PredAtom(a, k, bs) == [op |-> "pred", pred |-> [action |-> a, kind |-> k, binds |-> bs],
                       var |-> "", args |-> << >>]
TpAtom(v)          == [op |-> "tp", pred |-> DummyPred, var |-> v, args |-> << >>]
AndAtom(xs)        == [op |-> "and", pred |-> DummyPred, var |-> "", args |-> xs]

Formerly(atom)     == [op |-> "term", args |-> << >>,
                       term |-> [op |-> "formerly", window |-> Window, atom |-> atom,
                                 left |-> atom, leftNeg |-> FALSE]]
TrueCond           == [op |-> "true", args |-> << >>, term |-> DummyTerm]

\* input.amount: a   -- a bind to a variable the aggregation binds
AmountVar == [side |-> "input", field |-> "amount", kind |-> "var", name |-> "a",
              value |-> Str("")]

SumOverTrades ==
    [op |-> "agg", args |-> << >>, term |-> DummyTerm,
     agg |-> [kind |-> "sum", over |-> "a",
              binders |-> <<[name |-> "a", type |-> "Long"],
                            [name |-> "t", type |-> "Timepoint"]>>,
              cond |-> Formerly(AndAtom(<<PredAtom("Trade", "request", <<AmountVar>>),
                                          TpAtom("t")>>))],
     cmp |-> ">", value |-> Limit]

Policies ==
    IF Gate = "aggregate"
    THEN << [effect |-> "permit", action |-> "Trade",   cond |-> TrueCond],
            [effect |-> "permit", action |-> "Approve", cond |-> TrueCond],
            [effect |-> "forbid", action |-> "Trade",   cond |-> SumOverTrades] >>
    ELSE << [effect |-> "permit", action |-> "Approve", cond |-> TrueCond],
            [effect |-> "permit", action |-> "Trade",
             cond |-> Formerly(PredAtom("Approve", "request", << >>))] >>

\* The domain a bound variable of non-Timepoint type ranges over.
Values == {Num(x) : x \in Amounts}

VARIABLES
    trace,      \* the CURRENT session's trajectory -- all the policy engine can see
    traded,     \* the true total across every session -- what the author meant to bound
    unapproved, \* TRUE once a trade was allowed with no approval in its own session
    steps

vars == <<trace, traded, unapproved, steps>>

TypeOK ==
    /\ traded \in 0..(MaxSteps * MaxAmount)
    /\ unapproved \in BOOLEAN
    /\ steps \in 0..MaxSteps
    /\ Len(trace) \in 0..MaxSteps

Init ==
    /\ trace = << >>
    /\ traded = 0
    /\ unapproved = FALSE
    /\ steps = 0

SessionApproved == \E i \in DOMAIN trace : trace[i].action = "Approve"

Event(action, amount) ==
    [time     |-> Len(trace) + 1,
     action   |-> action,
     kind     |-> "request",
     input    |-> IF action = "Trade" THEN [amount |-> Num(amount)] ELSE EmptyRec,
     output   |-> EmptyRec,
     principal |-> Anon,
     resource  |-> Anon,
     isDecision |-> TRUE]

(***************************************************************************)
(* TRANSITIONS                                                             *)
(*                                                                         *)
(* The request event is appended BEFORE the decision, because AgentCore    *)
(* documents that a self-referential condition sees the current request --  *)
(* which is what makes the cap bite on the trade that would breach it      *)
(* rather than one trade late.                                             *)
(***************************************************************************)
Attempt(action, amount) ==
    /\ steps < MaxSteps
    /\ LET withReq == Append(trace, Event(action, amount))
           idx     == Len(withReq)
       IN /\ D!Decide(withReq, Policies, idx, Values)
          /\ trace' = withReq
          /\ traded' = IF action = "Trade" THEN traded + amount ELSE traded
          \* Parenthesised deliberately: `\/` binds looser than `=`, so without them this
          \* reads as a disjunction rather than an assignment and TLC reports the variable
          \* as unassigned the moment the right-hand side holds.
          /\ unapproved' = (unapproved \/ (action = "Trade" /\ ~SessionApproved))
    /\ steps' = steps + 1

\* The caller supplies the session id, so this needs no cooperation from anyone: send the
\* next request under a new one and the engine sees an empty trajectory. The global total
\* is untouched, because the world does not reset.
Rotate ==
    /\ MayRotate
    /\ steps < MaxSteps
    /\ trace # << >>
    /\ trace' = << >>
    /\ steps' = steps + 1
    /\ UNCHANGED <<traded, unapproved>>

Next ==
    \/ \E amount \in Amounts : Attempt("Trade", amount)
    \/ Attempt("Approve", 0)
    \/ Rotate

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* PROPERTIES                                                              *)
(*                                                                         *)
(* Each shape is checked against the thing it is supposed to give you.     *)
(* They are different properties on purpose: an aggregate forbid is a      *)
(* volume control and an approval gate is an authorization control, and    *)
(* the point is that rotation defeats one and not the other.               *)
(***************************************************************************)

\* What the author of the aggregate policy meant: never more than Limit in total.
\* The engine only ever enforces it per session.
GlobalCapHolds == traded <= Limit

\* What the author of the approval policy meant: no trade without an approval.
\* Rotation cannot manufacture one -- an empty trajectory denies.
EveryTradeApproved == ~unapproved

=============================================================================
