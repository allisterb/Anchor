---
title: Reading a verdict
description: What VACUOUS, REDUNDANT, DEAD, live and unknown mean, and what each one does not mean.
---

# Reading a verdict

`CheckPolicy` reports one verdict per rule. They are not style notes. Each answers the same
underlying question — *does deleting or changing this rule change what the policy decides?* — and
every answer is either **a witness session** or **a bounded no**.

| verdict | means | what to do |
|---|---|---|
| `live` | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |
| `VACUOUS` | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |
| `REDUNDANT` | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |
| `DEAD` | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |
| `unknown` | only from a smoke run: no witness found by a random walk | **not a verdict**. See `smoke-vs-exhaustive` |

## VACUOUS is the serious one

A vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though
it authorizes something — it parses, it validates, and `dogwood validate` accepts it. Nothing in the
policy text says so. If you report one, say plainly that the rule grants nothing, not that it is
"possibly redundant".

## Every negative answer is bounded, and the bound is printed

`VACUOUS` means *no session of up to `attempts` attempts makes it grant*. It does not mean "never".
The same applies to `REDUNDANT`, `DEAD`, and to `EQUIVALENT` from an `against` comparison.

So when you report one of these, report the bound with it. "Vacuous within 3 attempts" is true;
"vacuous" alone overstates what was checked. Raising `attempts` trades runtime for confidence.

A `live` verdict has no such caveat: a witness exists, and it was exhibited.

## The witness

For a `live` rule the note carries the session that proves it, as the actions attempted in order —
`Approve -> Trade`. That is the shortest thing to quote when explaining why a rule matters.

## Comparing an edit: report the DIRECTION, never just "they differ"

Given `against`, the checker answers a different question — not "is each rule doing something" but
**what did this edit change**. Four verdicts:

| | |
|---|---|
| `MORE PERMISSIVE` | the new set allows sessions the old one denied — **it added permissions** |
| `LESS PERMISSIVE` | the new set denies sessions the old one allowed |
| `EQUIVALENT` | no session within the bound tells them apart |
| `INCOMPARABLE` | both at once, which is usually a mistake rather than an intention |

**`MORE PERMISSIVE` is the one to lead with, even when the person asked about the other
direction.** Someone editing a policy usually wants to know what they took away, because that is
what generates complaints. What they need to know is what they added: a permission removed is a
support ticket, a permission silently added is an incident. Quote the `ADDED` witness session.

Do not soften `INCOMPARABLE` into "some changes". It means the edit moved in both directions at
once — almost always a condition that was rewritten rather than extended, and worth asking about.

`EQUIVALENT` is a claim of absence, so it carries the bound like every other one. It licenses "no
session of up to N attempts tells them apart", not "the edit is safe".

## A refusal is not a pass

If `Answered` is false the checker produced **no verdict at all** — the policy uses something
outside the modelled subset, or the file is missing. An empty finding list in that case does not
mean "no problems found". See `the-modelled-subset`.

## Before you trust any of it, check the reading

Every verdict is computed under one interpretation of history, and the tool tells you which in its
`Reading` field. Without an event schema that interpretation is the **unpinned** one, which is *not*
the shipped default. A rule reported `live` under the unpinned reading may never fire in deployment.
See `event-schemas-and-pins`.
