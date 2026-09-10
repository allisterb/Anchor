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
(* naming the exact case and decision point.                               *)
(*                                                                         *)
(* Same arrangement as CedarSemantics.tla: the semantics are hand-written  *)
(* and reviewed once here, the case data is generated, and TLC compares.   *)
(* Every case is checked in one run -- per-case JVM startup dominated      *)
(* everything else when each paid for its own.                             *)
(*                                                                         *)
(* WHAT THE CORPUS PINNED DOWN, none of it obvious from the prose:         *)
(*                                                                         *)
(*   - `@N` in a trace is SECONDS, and `within 10s` means 10 of them. Case *)
(*     0127 fixes it: under a 10s window a read 12s after a login is       *)
(*     denied and one 8s after is allowed.                                 *)
(*   - The window is INCLUSIVE: `t - eventTime <= window`.                 *)
(*   - A decision is made at each event carrying `request_context(...)`.   *)
(*   - The decision sees the trace UP TO AND INCLUDING its own event,      *)
(*     which is what AgentCore documents for self-referential conditions.  *)
(*   - Deny by default: where no permit matches, the verdict is false.     *)
(*                                                                         *)
(* THE SEMANTICS OF `since` AND `previous` ARE INFERRED, NOT DOCUMENTED.   *)
(* They are written here as standard past-time MFOTL and then checked      *)
(* against the corpus, which is the only reason to believe them. If a      *)
(* future widening disagrees, suspect these first.                         *)
(***************************************************************************)
EXTENDS Naturals, Sequences, TLC

(***************************************************************************)
(* SUPPLIED BY THE GENERATED MODULE                                        *)
(*                                                                         *)
(*   Cases   Seq of [name, trace, policies, oracle]                        *)
(*     trace     Seq of [time, action, kind, input, output,                *)
(*                       principal, resource, isDecision]                  *)
(*     policies  Seq of [effect, action, cond]                             *)
(*     oracle    function from decision index to BOOLEAN                   *)
(*                                                                         *)
(* A `cond` is a tree, uniform so that every node carries every field and  *)
(* nothing depends on lazy evaluation of a CASE arm:                       *)
(*                                                                         *)
(* [op |-> "true",     args |-> <<>>,          term |-> ...]  no condition *)
(* [op |-> "term",     args |-> <<>>,          term |-> <term>]           *)
(* [op |-> "not",      args |-> <<child>>,     term |-> ...]              *)
(* [op |-> "and",      args |-> <<c1, c2..>>,  term |-> ...]              *)
(*                                                                         *)
(* A <term> is [op, window, pred, left, leftNeg] where `op` is "formerly", *)
(* "previous" or "since"; `pred` is the matched event and `left` the       *)
(* left operand of a since. A <pred> is [action, kind, binds].             *)
(***************************************************************************)
CONSTANT Cases

(***************************************************************************)
(* A BIND is the first-order half of the logic: it joins a field of a past *)
(* event to a field of the request being authorized, to one of the request *)
(* scope entities, or to a literal.                                        *)
(*                                                                         *)
(*   input.user: context.input.approver   kind "ctx"                       *)
(*   output.approved: true                kind "lit"                       *)
(*   callerPrincipal: principal           kind "scope"                     *)
(* input.amount: _                      kind "any" -- present, unconstrained *)
(*                                                                         *)
(* Presence is checked structurally, through DOMAIN, rather than against a *)
(* sentinel value. A sentinel would have to be comparable with every field *)
(* type, and `output.result: true` puts a BOOLEAN on one side of that.     *)
(***************************************************************************)
BindHolds(b, ev, dec) ==
    LET rec == CASE b.side = "input"  -> ev.input
                 [] b.side = "output" -> ev.output
                 [] OTHER             -> [caller |-> ev.principal, callerRes |-> ev.resource]
        fld == IF b.side \in {"input", "output"} THEN b.field
               ELSE IF b.field = "callerPrincipal" THEN "caller" ELSE "callerRes"
    IN /\ fld \in DOMAIN rec
       /\ CASE b.kind = "any"   -> TRUE
            [] b.kind = "lit"   -> rec[fld] = b.value
            [] b.kind = "scope" -> rec[fld] = (IF b.name = "principal" THEN dec.principal
                                                                      ELSE dec.resource)
            [] OTHER            -> /\ b.name \in DOMAIN dec.input
                                   /\ rec[fld] = dec.input[b.name]

\* Does one recorded event match an event predicate?
Matches(pred, ev, dec) ==
    /\ ev.action = pred.action
    /\ ev.kind = pred.kind
    /\ \A j \in DOMAIN pred.binds : BindHolds(pred.binds[j], ev, dec)

(***************************************************************************)
(* THE TEMPORAL OPERATORS -- all past-time, because an authorizer decides  *)
(* now, from what has already happened.                                    *)
(***************************************************************************)
TermHolds(term, trace, upto, dec) ==
    LET t == dec.time
        InWindow(i) == trace[i].time <= t /\ t - trace[i].time <= term.window
    IN CASE
        \* `formerly within W P` -- P happened at some point in the window.
        term.op = "formerly" ->
            \E i \in 1..upto : InWindow(i) /\ Matches(term.pred, trace[i], dec)

        \* `previous within W P` -- the immediately preceding time point matched.
        [] term.op = "previous" ->
            /\ upto > 1
            /\ InWindow(upto - 1)
            /\ Matches(term.pred, trace[upto - 1], dec)

        \* `A since within W B` -- B happened in the window, and A has held at
        \* every point after it. With `!A`, A has held at none of them. This is
        \* standard MFOTL Since; it is inferred rather than documented.
        [] OTHER ->
            \E i \in 1..upto :
                /\ InWindow(i)
                /\ Matches(term.pred, trace[i], dec)
                /\ \A k \in (i + 1)..upto :
                      IF term.leftNeg THEN ~Matches(term.left, trace[k], dec)
                                      ELSE Matches(term.left, trace[k], dec)

RECURSIVE CondHolds(_, _, _, _)
CondHolds(c, trace, upto, dec) ==
    CASE c.op = "true" -> TRUE
      [] c.op = "term" -> TermHolds(c.term, trace, upto, dec)
      [] c.op = "not"  -> ~CondHolds(c.args[1], trace, upto, dec)
      [] OTHER         -> \A i \in DOMAIN c.args : CondHolds(c.args[i], trace, upto, dec)

(***************************************************************************)
(* THE DECISION -- Cedar's model, which Dogwood keeps: deny by default,    *)
(* forbid overrides permit.                                                *)
(***************************************************************************)
PolicyMatches(p, trace, upto, dec) ==
    /\ p.action = dec.action
    /\ CondHolds(p.cond, trace, upto, dec)

Decide(trace, policies, idx) ==
    LET dec == trace[idx]
        hit == {k \in DOMAIN policies : PolicyMatches(policies[k], trace, idx, dec)}
    IN /\ \E k \in hit : policies[k].effect = "permit"
       /\ ~\E k \in hit : policies[k].effect = "forbid"

\* Every decision point of one case against the verdict Dogwood produced. A
\* disagreement prints the case name and index, so the offending line of the
\* trace and of the expected output can be found directly.
CaseAgrees(c) ==
    \A d \in DOMAIN c.oracle :
        \/ Decide(c.trace, c.policies, d) = c.oracle[d]
        \/ Print(<<"DISAGREEMENT", c.name, "at decision index", d,
                   "model says", Decide(c.trace, c.policies, d),
                   "dogwood says", c.oracle[d]>>, FALSE)

Agree == \A i \in DOMAIN Cases : CaseAgrees(Cases[i])

=============================================================================
