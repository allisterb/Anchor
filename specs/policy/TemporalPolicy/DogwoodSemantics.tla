-------------------------- MODULE DogwoodSemantics --------------------------
(***************************************************************************)
(* Our reading of Dogwood's temporal operators, written so it can be held  *)
(* against the reference implementation's own regression corpus.           *)
(*                                                                         *)
(* TemporalPolicy.tla asks what a policy set could do over ALL sessions.   *)
(* This module asks a narrower and more checkable question: on THESE       *)
(* recorded sessions, does our evaluator return what Dogwood returned? The *)
(* corpus supplies both halves -- policies plus traces, and the verdicts   *)
(* their engine produced -- so a misreading shows up as a disagreement     *)
(* naming the exact case and decision point.                              *)
(*                                                                         *)
(* Every case is checked in one run: per-case JVM startup dominated        *)
(* everything else when each paid for its own.                             *)
(*                                                                         *)
(* WHAT THE CORPUS PINNED DOWN, none of it obvious from the prose:         *)
(*                                                                         *)
(*   - `@N` in a trace is SECONDS, and the window is inclusive. Case 0127  *)
(*     fixes it: under `within 10s` a read 12s after a login is denied and *)
(*     one 8s after is allowed.                                            *)
(*   - The decision sees the trace UP TO AND INCLUDING its own event,      *)
(*     which is what AgentCore documents for self-referential conditions.  *)
(*   - Deny by default: where no permit matches, the verdict is false.     *)
(*   - `count` counts DISTINCT ASSIGNMENTS to the bound variables, not     *)
(*     matching events. Case 0254 is the Rosetta stone: four identical     *)
(*     transfers, `count for (t: Timepoint)` over a `tp(t)`-bound          *)
(*     predicate, forbidden at `n >= 3` -- and the verdicts flip on the    *)
(*     third, which only works if the current request counts itself.       *)
(*                                                                         *)
(* THE SEMANTICS OF `since`, `previous` AND THE AGGREGATIONS ARE INFERRED, *)
(* not documented. They are written as standard past-time MFOTL and then   *)
(* checked against the corpus, which is the only reason to believe them.   *)
(***************************************************************************)
\* Integers rather than Naturals: SumOver guards on `\in Int`, because a bound variable's
\* domain is every scalar the trace contains and only some of them are numbers.
EXTENDS Integers, Sequences, FiniteSets, TLC

(***************************************************************************)
(* SUPPLIED BY THE GENERATED MODULE                                        *)
(*                                                                         *)
(*   Cases   Seq of [name, trace, policies, oracle, values]                *)
(*     trace     Seq of [time, action, kind, input, output,                *)
(*                       principal, resource, isDecision]                  *)
(*     policies  Seq of [effect, action, cond]                             *)
(*     oracle    function from decision index to BOOLEAN                   *)
(*     values    every scalar appearing in the trace -- the domain a bound *)
(*               variable of non-Timepoint type ranges over                *)
(***************************************************************************)
CONSTANT Cases

(***************************************************************************)
(* BINDS -- the first-order half of the logic. A bind joins a field of a   *)
(* past event to the request's input, to a scope entity, to a literal, to  *)
(* a bound variable, or to nothing at all (`_`).                           *)
(*                                                                         *)
(* Presence is checked structurally, through DOMAIN, rather than against a *)
(* sentinel value. A sentinel would have to be comparable with every field *)
(* type, and `output.result: true` puts a BOOLEAN on one side of that.     *)
(***************************************************************************)
(***************************************************************************)
(* Equality that survives comparing values of different kinds.             *)
(*                                                                         *)
(* A bound variable ranges over every scalar the trace contains, so a      *)
(* Timepoint binder gets offered strings and a String binder gets offered  *)
(* integers. TLC refuses `=` across kinds outright, and refuses `\in Int`   *)
(* for a non-integer as well, so neither the comparison nor a type test in *)
(* front of it is available.                                               *)
(*                                                                         *)
(* So every scalar is TAGGED at generation time -- [k |-> "s"|"n"|"b"|"t", *)
(* v |-> ...] -- and comparison checks the kind first. `/\` short-circuits, *)
(* so the values are only compared once the kinds agree.                   *)
(***************************************************************************)
SameVal(x, y) == x.k = y.k /\ x.v = y.v

\* A trace index, in the same tagged shape as a field value.
TP(i) == [k |-> "t", v |-> i]

BindHolds(b, ev, dec, asg) ==
    LET rec == CASE b.side = "input"  -> ev.input
                 [] b.side = "output" -> ev.output
                 [] OTHER             -> [caller |-> ev.principal, callerRes |-> ev.resource]
        fld == IF b.side \in {"input", "output"} THEN b.field
               ELSE IF b.field = "callerPrincipal" THEN "caller" ELSE "callerRes"
    IN /\ fld \in DOMAIN rec
       /\ CASE b.kind = "any"   -> TRUE
            [] b.kind = "lit"   -> SameVal(rec[fld], b.value)
            [] b.kind = "var"   -> /\ b.name \in DOMAIN asg
                                   /\ SameVal(rec[fld], asg[b.name])
            [] b.kind = "scope" -> SameVal(rec[fld], IF b.name = "principal" THEN dec.principal
                                                                            ELSE dec.resource)
            [] OTHER            -> /\ b.name \in DOMAIN dec.input
                                   /\ SameVal(rec[fld], dec.input[b.name])

Matches(pred, ev, dec, asg) ==
    /\ ev.action = pred.action
    /\ ev.kind = pred.kind
    /\ \A j \in DOMAIN pred.binds : BindHolds(pred.binds[j], ev, dec, asg)

(***************************************************************************)
(* ATOMS are evaluated AT A CANDIDATE EVENT, not at the decision point.    *)
(*                                                                         *)
(* `formerly within 1h (P && tp(t))` searches for an event matching P and  *)
(* binds `t` to THAT event's index. So the group's meaning depends on      *)
(* which candidate is under consideration, which is why this is a separate *)
(* evaluation indexed by `i` rather than part of CondHolds.                *)
(***************************************************************************)
(***************************************************************************)
(* A comparison on the DECISION event's own context, e.g.                  *)
(*                                                                         *)
(*     formerly within 1h (Login::request{..} && context.input.amount > 100) *)
(*                                                                         *)
(* Note what it does NOT read: the candidate event. `i` is not mentioned    *)
(* below, so a comparison evaluates identically at every candidate index -- *)
(* it filters the REQUEST, not the history, and sits inside the group only  *)
(* because that is where the author wrote it.                              *)
(*                                                                         *)
(* Kind is compared before value, as everywhere else here, because TLC      *)
(* refuses `=` across a string and an integer rather than returning FALSE.  *)
(* A field the decision event does not carry makes the comparison FALSE.    *)
(***************************************************************************)
CmpHolds(a, dec) ==
    /\ a.field \in DOMAIN dec.input
    /\ LET v == dec.input[a.field] IN
       /\ v.k = a.value.k
       /\ CASE a.cmp = "==" -> v.v = a.value.v
            [] a.cmp = "!=" -> v.v # a.value.v
            \* Ordering is only defined on numbers. The parser refuses `<` and friends on a
            \* non-numeric literal, so the guard here is belt and braces rather than a branch
            \* the corpus reaches.
            [] a.cmp = ">"  -> v.k = "n" /\ v.v > a.value.v
            [] a.cmp = "<"  -> v.k = "n" /\ v.v < a.value.v
            [] a.cmp = ">=" -> v.k = "n" /\ v.v >= a.value.v
            [] a.cmp = "<=" -> v.k = "n" /\ v.v <= a.value.v
            [] OTHER        -> FALSE

RECURSIVE AtomHolds(_, _, _, _, _)
AtomHolds(a, i, trace, dec, asg) ==
    CASE a.op = "pred" -> Matches(a.pred, trace[i], dec, asg)
      [] a.op = "tp"   -> /\ a.var \in DOMAIN asg
                          /\ SameVal(asg[a.var], TP(i))
      [] a.op = "cmp"  -> CmpHolds(a, dec)
      [] OTHER         -> \A k \in DOMAIN a.args : AtomHolds(a.args[k], i, trace, dec, asg)

(***************************************************************************)
(* THE TEMPORAL OPERATORS -- all past-time, because an authorizer decides  *)
(* now, from what has already happened.                                    *)
(***************************************************************************)
TermHolds(term, trace, upto, dec, asg) ==
    LET t == dec.time
        InWindow(i) == trace[i].time <= t /\ t - trace[i].time <= term.window
    IN CASE
        \* `formerly within W A` -- A held at some point in the window.
        term.op = "formerly" ->
            \E i \in 1..upto : InWindow(i) /\ AtomHolds(term.atom, i, trace, dec, asg)

        \* `previous within W A` -- the immediately preceding time point.
        [] term.op = "previous" ->
            /\ upto > 1
            /\ InWindow(upto - 1)
            /\ AtomHolds(term.atom, upto - 1, trace, dec, asg)

        \* `A since within W B` -- B held in the window and A has held at every
        \* point after it; with `!A`, at none of them. Standard MFOTL Since.
        [] OTHER ->
            \E i \in 1..upto :
                /\ InWindow(i)
                /\ AtomHolds(term.atom, i, trace, dec, asg)
                /\ \A k \in (i + 1)..upto :
                      IF term.leftNeg THEN ~AtomHolds(term.left, k, trace, dec, asg)
                                      ELSE AtomHolds(term.left, k, trace, dec, asg)

(***************************************************************************)
(* AGGREGATION                                                             *)
(*                                                                         *)
(* `count for (t: Timepoint), (x: String). where (phi)` is the number of   *)
(* DISTINCT ASSIGNMENTS to t and x under which phi holds -- not the number *)
(* of matching events. The two coincide when the only binder is a `tp`,    *)
(* which is the common idiom, and diverge as soon as a second variable is  *)
(* bound to a field that repeats.                                          *)
(*                                                                         *)
(* A binder's domain is its declared type: Timepoint ranges over the trace *)
(* indices visible at the decision, anything else over the scalars the     *)
(* trace actually contains. That is finite, so TLC can enumerate it.       *)
(***************************************************************************)
RECURSIVE SumOver(_, _)
SumOver(S, k) ==
    IF S = {} THEN 0
    ELSE LET x == CHOOSE y \in S : TRUE
         IN (IF k \in DOMAIN x /\ x[k].k = "n" THEN x[k].v ELSE 0) + SumOver(S \ {x}, k)

Merge(outer, inner) ==
    [x \in (DOMAIN outer) \union (DOMAIN inner) |->
        IF x \in DOMAIN inner THEN inner[x] ELSE outer[x]]

RECURSIVE CondHolds(_, _, _, _, _, _)

Satisfying(agg, trace, upto, dec, asg, values) ==
    LET names  == {b.name : b \in {agg.binders[i] : i \in DOMAIN agg.binders}}
        Dom(n) == LET b == CHOOSE x \in {agg.binders[i] : i \in DOMAIN agg.binders} : x.name = n
                  IN IF b.type = "Timepoint" THEN {TP(i) : i \in 1..upto} ELSE values
    IN { inner \in [names -> values \union {TP(i) : i \in 1..upto}] :
            /\ \A n \in names : inner[n] \in Dom(n)
            /\ CondHolds(agg.cond, trace, upto, dec, Merge(asg, inner), values) }

AggValue(agg, trace, upto, dec, asg, values) ==
    LET sats == Satisfying(agg, trace, upto, dec, asg, values)
    IN IF agg.kind = "count" THEN Cardinality(sats) ELSE SumOver(sats, agg.over)

Compare(lhs, op, rhs) ==
    CASE op = "==" -> lhs = rhs
      [] op = "!=" -> lhs # rhs
      [] op = ">=" -> lhs >= rhs
      [] op = "<=" -> lhs <= rhs
      [] op = ">"  -> lhs > rhs
      [] OTHER     -> lhs < rhs

CondHolds(c, trace, upto, dec, asg, values) ==
    CASE c.op = "true" -> TRUE
      [] c.op = "term" -> TermHolds(c.term, trace, upto, dec, asg)
      [] c.op = "not"  -> ~CondHolds(c.args[1], trace, upto, dec, asg, values)
      [] c.op = "and"  -> \A i \in DOMAIN c.args :
                              CondHolds(c.args[i], trace, upto, dec, asg, values)
      \* `exists (n: T). (AGG == n && n CMP k)` is the idiom the corpus uses for every
      \* aggregation; it says nothing more than `AGG CMP k`, and the parser recognises
      \* exactly that shape rather than implementing general existential quantification.
      [] OTHER         -> Compare(AggValue(c.agg, trace, upto, dec, asg, values),
                                  c.cmp, c.value)

(***************************************************************************)
(* THE DECISION -- Cedar's model, which Dogwood keeps: deny by default,    *)
(* forbid overrides permit.                                                *)
(***************************************************************************)
PolicyMatches(p, trace, upto, dec, values) ==
    /\ p.action = dec.action
    /\ CondHolds(p.cond, trace, upto, dec, << >>, values)

Decide(trace, policies, idx, values) ==
    LET dec == trace[idx]
        hit == {k \in DOMAIN policies : PolicyMatches(policies[k], trace, idx, dec, values)}
    IN /\ \E k \in hit : policies[k].effect = "permit"
       /\ ~\E k \in hit : policies[k].effect = "forbid"

CaseAgrees(c) ==
    \A d \in DOMAIN c.oracle :
        \/ Decide(c.trace, c.policies, d, c.values) = c.oracle[d]
        \/ Print(<<"DISAGREEMENT", c.name, "at decision index", d,
                   "model says", Decide(c.trace, c.policies, d, c.values),
                   "dogwood says", c.oracle[d]>>, FALSE)

Agree == \A i \in DOMAIN Cases : CaseAgrees(Cases[i])

=============================================================================
