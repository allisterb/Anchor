-------------------------- MODULE DogwoodSemantics --------------------------
(***************************************************************************)
(* Our reading of Dogwood's `formerly within` semantics, written so it can *)
(* be held against the reference implementation's own regression corpus.   *)
(*                                                                         *)
(* TemporalPolicy.tla asks what a policy set could do over ALL sessions.   *)
(* This module asks a narrower and more checkable question: on THESE       *)
(* recorded sessions, does our evaluator return what Dogwood returned? The *)
(* corpus supplies both halves -- policies plus a trace, and the verdicts  *)
(* their engine produced -- so a misreading of the semantics shows up as a *)
(* disagreement naming the exact case and decision point.                  *)
(*                                                                         *)
(* Same arrangement as CedarSemantics.tla: the semantics are hand-written  *)
(* and reviewed once here, the case data is generated, and TLC compares.   *)
(*                                                                         *)
(* EVERY CASE IS CHECKED IN ONE RUN. The trace and policies are operator   *)
(* arguments rather than module constants, so `Cases` can hold the whole   *)
(* corpus subset. One TLC invocation instead of one per case: the same     *)
(* work took over five minutes when each case paid for its own JVM.        *)
(*                                                                         *)
(* WHAT THE CORPUS PINNED DOWN, and none of it is obvious from the prose:  *)
(*                                                                         *)
(*   - `@N` in a trace is SECONDS, and `within 10s` means 10 of them. On   *)
(*     case 0127 a read 12s after a login is denied and one 8s after is    *)
(*     allowed, which fixes both the unit and the comparison.              *)
(*   - The window is INCLUSIVE: `t - eventTime <= window`.                 *)
(*   - A decision is made at each event carrying `request_context(...)`,   *)
(*     and the verdict is reported against that event's index.            *)
(*   - The decision sees the trace UP TO AND INCLUDING its own event,      *)
(*     which is what AgentCore documents for self-referential conditions.  *)
(*   - Deny by default: where no permit matches, the verdict is false even *)
(*     though nothing forbade it.                                          *)
(***************************************************************************)
EXTENDS Naturals, Sequences, TLC

(***************************************************************************)
(* SUPPLIED BY THE GENERATED MODULE                                        *)
(*                                                                         *)
(*   Cases   Seq of [name, trace, policies, oracle]                        *)
(*     trace     Seq of [time, action, kind, input, output, isDecision]    *)
(*               `input`/`output` are functions from field name to value;  *)
(*               a field absent from the domain is simply not there.       *)
(*     policies  Seq of [effect, action, terms]                            *)
(*               terms: Seq of [action, kind, window, binds]               *)
(*               binds: Seq of [side, field, kind, name, value]            *)
(*     oracle    function from decision index to BOOLEAN -- what Dogwood   *)
(*               actually returned                                         *)
(***************************************************************************)
CONSTANT Cases

(***************************************************************************)
(* A BIND is the first-order half of the logic: it joins a field of a past *)
(* event to a field of the request being authorized, or to a literal.      *)
(*                                                                         *)
(*   input.user: context.input.approver   ->  side "input", kind "ctx"     *)
(*   output.approved: true                ->  side "output", kind "lit"    *)
(*                                                                         *)
(* Presence is checked structurally, through DOMAIN, rather than against a *)
(* sentinel value. A sentinel would have to be comparable with every field *)
(* type, and `output.result: true` puts a BOOLEAN on one side of that.     *)
(***************************************************************************)
BindHolds(b, ev, ctx) ==
    LET rec == IF b.side = "input" THEN ev.input ELSE ev.output
    IN /\ b.field \in DOMAIN rec
       /\ IF b.kind = "ctx"
          THEN /\ b.name \in DOMAIN ctx
               /\ rec[b.field] = ctx[b.name]
          ELSE rec[b.field] = b.value

(***************************************************************************)
(* `formerly within W A::k{ binds }` -- a past-time metric operator.       *)
(*                                                                         *)
(* Past-time is not a simplification: an authorizer decides now, from what *)
(* has already happened, so `upto` is the index of the decision itself.    *)
(***************************************************************************)
TermHolds(trace, term, upto, ctx, t) ==
    \E i \in 1..upto :
        /\ trace[i].action = term.action
        /\ trace[i].kind = term.kind
        /\ trace[i].time <= t
        /\ t - trace[i].time <= term.window
        /\ \A j \in DOMAIN term.binds : BindHolds(term.binds[j], trace[i], ctx)

\* A policy matches when its action scope matches and every temporal term holds.
\* Empty `terms` is an unconditional rule -- a scope-only policy.
PolicyMatches(trace, p, upto, ctx, t, action) ==
    /\ p.action = action
    /\ \A k \in DOMAIN p.terms : TermHolds(trace, p.terms[k], upto, ctx, t)

(***************************************************************************)
(* THE DECISION -- Cedar's model, which Dogwood keeps: deny by default,    *)
(* forbid overrides permit.                                                *)
(***************************************************************************)
Decide(trace, policies, idx) ==
    LET ev  == trace[idx]
        hit == {k \in DOMAIN policies :
                    PolicyMatches(trace, policies[k], idx, ev.input, ev.time, ev.action)}
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
