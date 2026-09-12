---
title: Smoke versus exhaustive
description: What a random walk can and cannot settle here — and why the polarity is backwards from every other smoke test.
---

# Smoke versus exhaustive

`CheckPolicy` explores the state space exhaustively by default. Passing `smoke: N` runs TLC as a
random walk of N behaviours instead.

## The polarity is inverted here

The usual reason to run a simulation is a sound **negative**: find a counterexample and the thing is
broken; find none and you have learnt nothing.

Anchor reads TLC backwards. A violation is the **good** outcome — it is the witness session proving
a rule does something. So a random walk gives a sound **positive**, and its silence means nothing at
all.

| smoke reports | sound? | what it means |
|---|---|---|
| `live` | **yes** | a witness was found. A witness is a witness however it was reached |
| `unknown` | — | this walk did not reach a session where the rule matters. **Not a verdict** |

**A smoke run can never report VACUOUS, REDUNDANT or DEAD.** Each of those is a claim of *absence*,
a random walk cannot establish absence, and each of them tells someone to delete a rule.

## What `unknown` is not

- It is **not** "the rule is fine".
- It is **not** "the rule is inert".
- It is **never** grounds for suggesting a rule be deleted.

It means the search did not settle the question. Re-run without `smoke` for a verdict, or raise N to
search further. `PolicyCheckResult.Unsettled` carries these separately from `Inert` for exactly this
reason.

## When to use it

Not for speed on ordinary policies. Exhaustive search stops at the first violation, so a **live**
rule is found quickly either way. The slow case is a rule that is *not* live, where TLC must exhaust
the space — and simulation can never settle that one.

Use `smoke` when exhaustive **does not finish at all**, which is what raising `attempts` to gain
confidence in a VACUOUS verdict eventually produces. There it turns "no answer about anything" into
"these rules are definitely live, and the rest I could not settle".

So the order to try things in is:

1. `CheckPolicy` as it comes.
2. If a negative verdict matters, raise `attempts` and run again.
3. If that stops finishing, `smoke` — and report only the `live` results as settled.

## Reproducibility

The simulation seed is fixed, so a smoke verdict is reproducible run to run. Raising N is what
widens the search, not re-running.
