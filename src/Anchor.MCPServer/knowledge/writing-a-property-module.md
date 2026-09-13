---
title: Writing a property module
description: How to state what a policy is SUPPOSED to mean, and the trap that makes such a claim pass having checked nothing.
---

# Writing a property module

There are two kinds of claim about a policy, and the difference is who is able to state it.

| | |
|---|---|
| **derivable** | statable from the policy alone. `CheckPolicy` answers these already: VACUOUS, REDUNDANT/DEAD, and `against` for a diff |
| **intentional** | only the author knows it. You write it, Anchor checks it |

The three built-ins would all pass a firewall policy that let the whole internet in, because "every
rule fires and none is redundant" is true of that policy too. An intentional claim is the other
kind: *SSH from the local range is permitted, and every external source is denied.*

You state one as a TLA+ module passed to `CheckPolicy`'s `property` argument.

## Start with `DescribePolicyModule`

Do not write one from memory. The module you extend — `PolicyUnderTest` — is **generated from the
policy**, and its vocabulary is lifted from that policy's own text. Action names, field names and
domains differ per policy and cannot be guessed.

`DescribePolicyModule` returns all of it, plus a skeleton module that already elaborates and runs.
Edit the skeleton's claim rather than starting from a blank file.

## Scalars are tagged

Write `Num(22)`, never `22`. Every value carries its kind so that TLC refuses a cross-kind
comparison instead of quietly answering one.

| constructor | for |
|---|---|
| `Str(x)` | a string |
| `Num(x)` | an integer |
| `Bool(x)` | `TRUE` / `FALSE` |
| `Addr(a, b, c, d)` | an address — **four octets**, because TLC cannot hold one as a 32-bit number |

## The trap: there is deliberately no `Inputs`

`PolicyUnderTest` does not offer a set of all requests to quantify over, and that is on purpose.

A request space derived from the policy's own literals cannot test a claim about a value the policy
never mentions. Delete the `forbid` that names `"external"` and the value vanishes from the
vocabulary — so a claim like `OutsideIsRefused` would range over **nothing**, hold vacuously, and
report success having examined nothing. That is worse than failing.

So **state the requests your claim is about**, including values the policy never names:

```tla
Origins == {"local", "external"}
Ports   == {22, 2222}
Requests == {[port |-> Num(p), origin |-> Str(o)] : p \in Ports, o \in Origins}
```

The description's `plusOneValueThePolicyNeverNames` tells you the model already admits one such
value internally — but it is not writable, so it is no substitute for naming your own.

## The shape

```tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>
Grants(input) == D!Decide(<<Request("Connect", input)>>, Policies, 1, AllValues)

VARIABLE req
Init == req \in Requests
Next == UNCHANGED req
Spec == Init /\ [][Next]_req

LocalSshIsAllowed == (req.port = Num(22) /\ req.origin = Str("local")) => Grants(req)
OutsideIsRefused  == (req.origin = Str("external")) => ~Grants(req)
```

One request is chosen nondeterministically and held, so a violation's counterexample **names the
request** that breaks the claim rather than merely reporting that one exists.

There is no session in *that* example: "what does this policy decide for this request" is not a
temporal question, so there is no state machine beyond holding one request still.

## A claim about TIMING needs a session, and you build it yourself

Most Dogwood policies are temporal, and a claim like *"after fifteen minutes without an approval,
writes are refused"* cannot be stated about one request. Build the session by hand with
`Ev(action, kind, input, output, time)` and ask the evaluator about one event of it:

```
Interaction(t) == Ev("interact_advisor", "response", NoFields, NoFields, t)
Trade(t)       == Ev("execute_trade", DecisionKind, NoFields, NoFields, t)

Session(gap)      == << Interaction(1), Trade(1 + gap) >>
TradeAllowed(gap) == D!Decide(Session(gap), Policies, 2, AllValues)   \* 2 = the trade

Minute == 60
Gaps   == {1, 10 * Minute, 16 * Minute}

VARIABLE gap
Init == gap \in Gaps
Next == UNCHANGED gap
Spec == Init /\ [][Next]_gap

LosesWriteAfter15m == (gap > 15 * Minute) => ~TradeAllowed(gap)
```

**`time` IS IN SECONDS.** The evaluator compares it against a window width directly, so a claim
about a 15-minute window needs events 900 apart — not 2. This is the thing that catches people
out, because the built-in questions explore sessions whose events are one second apart: a long
window can never age out there, and only a hand-built trace can put a decision on the far side
of one.

**`Ev` takes PLAIN values for its action, kind and time**, as above — `Ev("execute_trade",
"request", NoFields, NoFields, 900)`, never `Ev(Str("execute_trade"), …, Num(900))`. The tagged
constructors (`Str`, `Num`, `Bool`, `Addr`) are for field **values inside** the input and output
records, and nowhere else. Tagging the action or the time is the commonest way to get a module
that will not compile.

The index passed to `Decide` is which event of the trace is being decided, counting from 1. It is
almost always the last.

**State the gaps you mean**, as above. The same trap applies as with requests: a set derived from
the policy's own windows would contain only the numbers it already mentions, and a claim about
"ten minutes" would then range over nothing and pass having checked nothing.

## The `.cfg` is not optional

A companion `.cfg` must name the specification and every invariant:

```
SPECIFICATION Spec
INVARIANT LocalSshIsAllowed
INVARIANT OutsideIsRefused
```

Naming them is deliberate: **a property nobody listed is a property nobody checked.**

## Read what it forbids before you check it

A property is checked against exactly what it says. If what it says is not what you meant, the run
is just as rigorous, passes just as convincingly, and establishes nothing — and no verdict
downstream can tell you that happened, because every check below the property is faithful to it.

So read the claim back before running anything:

```bash
anchor explain TrustDecay10.tla
```

```
  LosesWriteAfter10m
     says      whenever gap is greater than 10 * Minute (= 600), then the policy REFUSES it
     forbids   gap is greater than 10 * Minute (= 600), and yet the policy GRANTS it
     applies   to 3 of the 6: gap = 840, gap = 960, gap = 1800
```

**The `forbids` line is the one to disagree with.** It is the only thing the claim can catch. If it
does not describe something you would object to seeing happen, the check will pass without testing
your intention.

**The `applies` line is the size of the experiment.** A claim shaped `A => B` tests nothing at all
in any state where `A` is false, so a condition that matches two of six states is a claim about two
states. `applies to NONE` is reported as a finding — the claim would hold, TLC would say so, and it
would have examined nothing:

```
  applies   to NONE of the 2 states
  !!        NOTHING THIS CLAIM RANGES OVER CAN BREAK IT ...
```

That is the same defect as a vacuous permit, in the property instead of the policy, and it is the
commonest way a property module ends up worthless. It happens most often exactly where the trap
above describes: a claim about a value the request set never presents.

`--explain` on a check prints the same thing first, so the claim is read before its verdict is:

```bash
anchor check policy.dw --property TrustDecay10.tla --explain
```

What it will **not** catch is a tautology about the decision itself — `Grants(r) \/ ~Grants(r)`
holds whatever the policy says, and the explainer does not evaluate `Decide`, deliberately. That
one is caught by `--mutation-score`, which breaks the policy and checks that the property notices.
The two are complementary; neither replaces the other.

## Reading the result

A violation means the policy does **not** mean what your property says it means, and the state
printed is the request that breaks it. A clean run means every claim held over every request you
named — and says nothing about requests you did not name.

## Do not report a violation as `gap = 960`

That is the answer in the wrong language. The person who owns the policy wrote `.dw` and may never
have seen the module; a state naming a TLA+ variable, in units nobody wrote down, is something they
cannot check — and a finding nobody can check is a finding nobody acts on.

Pass `witness` and the same finding comes back in theirs:

```
  LosesWriteAfter10m
      TLC found      gap = 960
      which is       @1 interact_advisor::response  @961 execute_trade::request
      dogwood says   ALLOW at t=961  -- confirms the finding
      so             with gap = 960, the Dogwood engine ALLOWS this session at t=961, where
                     `LosesWriteAfter10m` says your policy must REFUSE it
```

It works out which session the counterexample stands for — from your module's own `Session(gap)` —
renders it as a Dogwood trace, and puts it to `dogwood replay`. **That verdict is the reference
engine's, not ours.** Quote it in preference to the TLA+ state: it names a concrete value the
author can try against their own policy, and it does not ask them to trust our reading of Dogwood.

If the two ever disagree, say so plainly. A disagreement is a defect in Anchor, not a finding about
the policy, and reporting it as the latter would be wrong.
