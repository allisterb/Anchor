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

There is no session here: "what does this policy decide for this request" is not a temporal
question, so there is no state machine beyond holding one request still.

## The `.cfg` is not optional

A companion `.cfg` must name the specification and every invariant:

```
SPECIFICATION Spec
INVARIANT LocalSshIsAllowed
INVARIANT OutsideIsRefused
```

Naming them is deliberate: **a property nobody listed is a property nobody checked.**

## Reading the result

A violation means the policy does **not** mean what your property says it means, and the state
printed is the request that breaks it. A clean run means every claim held over every request you
named — and says nothing about requests you did not name.
