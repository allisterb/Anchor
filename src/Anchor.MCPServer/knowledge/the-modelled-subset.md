---
title: The modelled subset, and why a refusal is not a failure
description: What Anchor will and will not translate, and why it refuses rather than approximating.
---

# The modelled subset

Anchor translates Dogwood policy text into TLA+ records that a validated evaluator checks. It
models a **subset** of the language. When a policy uses something outside it, the checker refuses:

```
REFUSED: like_impossible.dw is outside the modelled subset
  input.stock is constrained by 2 `like` patterns at once and no value satisfying all of
  them could be constructed; deciding that needs glob intersection, which is not modelled
```

**A refusal is a deliberate answer, not a breakdown.** The alternative — translating approximately
and reporting a verdict anyway — produces a verdict nobody can attribute: you could not tell whether
`VACUOUS` described the policy or the approximation. So the house rule is to refuse rather than
approximate, and refusals name the construct so they are actionable.

`Answered: false` with an empty finding list therefore means **no verdict was produced**. It does
not mean "no problems found". Never summarise it as a clean result.

## What is modelled

- `permit` / `forbid`, with forbid-overriding-permit and default-deny
- action sets and scope binds, including wildcard (`_`) and fresh variables
- Cedar-level conditions: comparison, `&&`, `||`, `!`, parentheses
- temporal terms: `formerly within <duration>`, aggregates, `exists` with an entity-typed binder
- `like` patterns (glob), `ip()` and `isInRange` over IPv4, decimals, macros
- event schemas: universal and partial pins, `max_window`

## Common reasons for a refusal

| refusal | why |
|---|---|
| window exceeds `max_window` | the gateway's validator would reject the policy — see `event-schemas-and-pins` |
| two `like` patterns on one field with no constructible joint witness | deciding it needs glob intersection |
| ordering compared against a non-integer | ordering is modelled for **integers only**; the engine denies on decimals |
| IPv6 address | not modelled |
| more than `maxFields` input/output fields | the request space is the product of their domains, so it would explode |
| event kinds outside AgentCore's convention | the model only knows `request` / `response` / `error` |
| mixed value kinds on one field | scalars are tagged, and a cross-kind comparison is refused rather than silently answered |

## What to do with a refusal

Read the reason — it names the construct. Then either simplify the policy to stay inside the subset,
or tell the user plainly that this policy cannot be checked and which construct is responsible. Do
not retry the same call, and do not fall back to reasoning about the policy yourself and presenting
it as a checked result.

## Two limits worth knowing separately

- **Integers only for ordering.** `>`, `<`, `>=`, `<=` are modelled for integers. Decimals are
  excluded deliberately, because the reference engine denies on them.
- **Addresses are four octets, never a 32-bit number.** TLC works in Java ints and stops at
  2,147,483,647, so an address above 127.255.255.255 is not a value it can hold as an integer.
