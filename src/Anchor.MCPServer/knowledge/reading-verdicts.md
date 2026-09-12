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
The same applies to `REDUNDANT`, `DEAD`, and to `no difference` from an `against` comparison.

So when you report one of these, report the bound with it. "Vacuous within 3 attempts" is true;
"vacuous" alone overstates what was checked. Raising `attempts` trades runtime for confidence.

A `live` verdict has no such caveat: a witness exists, and it was exhibited.

## The witness

For a `live` rule the note carries the session that proves it, as the actions attempted in order —
`Approve -> Trade`. That is the shortest thing to quote when explaining why a rule matters.

## A refusal is not a pass

If `Answered` is false the checker produced **no verdict at all** — the policy uses something
outside the modelled subset, or the file is missing. An empty finding list in that case does not
mean "no problems found". See `the-modelled-subset`.

## Before you trust any of it, check the reading

Every verdict is computed under one interpretation of history, and the tool tells you which in its
`Reading` field. Without an event schema that interpretation is the **unpinned** one, which is *not*
the shipped default. A rule reported `live` under the unpinned reading may never fire in deployment.
See `event-schemas-and-pins`.
