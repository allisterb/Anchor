# 03-cumulative-cap.dw

**Stated intention.** Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
> - draft round 2 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## What was checked

`Intent.tla`, drafted from the intention above and kept because it caught 1 broken version(s) of this policy.

### Does it say what you asked for?

**A person was shown, in plain English, what this claim forbids, and confirmed it is what they meant — before anything was checked.** They did not read the formal claim, so what they confirmed is the reading of it; the two are generated from the same module and the reading is the part a person can audit.

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: 03-cumulative-cap.dw
Property: Intent

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  1 claim will be checked, over 18 states.
  prevAmount = 20000, curAmount = 20000, gap = 3600, prevAmount = 20000, curAmount = 20000, gap
  = 46800, prevAmount = 20000, curAmount = 30000, gap = 3600, prevAmount = 20000, curAmount =
  30000, gap = 46800, prevAmount = 20000, curAmount = 40000, gap = 3600, prevAmount = 20000,
  curAmount = 40000, gap = 46800, prevAmount = 30000, curAmount = 20000, gap = 3600, prevAmount
  = 30000, curAmount = 20000, gap = 46800, and 10 more

  BlockOverCap
      says      whenever gap is at most 12 * Hour (= 43200) and prevAmount + curAmount is
                greater than 50000, then Allowed does not hold
      forbids   gap is at most 12 * Hour (= 43200) and prevAmount + curAmount is greater than
                50000, and yet Allowed holds
      applies   to 6 of the 18: prevAmount = 20000, curAmount = 40000, gap = 3600, prevAmount =
                30000, curAmount = 30000, gap = 3600, prevAmount = 30000, curAmount = 40000,
                gap = 3600, prevAmount = 40000, curAmount = 20000, gap = 3600, prevAmount =
                40000, curAmount = 30000, gap = 3600, prevAmount = 40000, curAmount = 40000,
                gap = 3600

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 1
  rule 1 (forbid): DEAD -- deleting it changes no verdict in any session
```

## Reported

### Verification Summary

The property **Intent** **held** across the 18 states tested.

---

### What Was Checked

The property checked 1 claim, **`BlockOverCap`**, across a bounded test space of **18 states**:
* **`prevAmount`**: 20000, 30000, 40000
* **`curAmount`**: 20000, 30000, 40000
* **`gap`**: 3600 seconds (1 hour), 46800 seconds (13 hours)

#### Claim Details:
* **`BlockOverCap`**: Asserts that whenever the time gap between requests is at most 12 hours (43,200 seconds) and the cumulative amount (`prevAmount + curAmount`) exceeds 50,000, the request is not allowed (`Allowed` does not hold).
* **States where the condition applied**: Exactly **6 of the 18 states** met the condition (the 6 combinations where `gap = 3600` and `prevAmount + curAmount > 50000`):
  1. `prevAmount = 20000, curAmount = 40000, gap = 3600`
  2. `prevAmount = 30000, curAmount = 30000, gap = 3600`
  3. `prevAmount = 30000, curAmount = 40000, gap = 3600`
  4. `prevAmount = 40000, curAmount = 20000, gap = 3600`
  5. `prevAmount = 40000, curAmount = 30000, gap = 3600`
  6. `prevAmount = 40000, curAmount = 40000, gap = 3600`

In all 6 states, the policy denied the request as required.

---

### Policy Finding: Dead Rule

* **Rule 1 (`forbid`) is dead code**: Removing Rule 1 does not change the verdict in any session evaluated. Another rule is already intercepting or overriding these cases, making Rule 1 redundant.

---

### Scope & Limitations

This check established results **only** for the 18 explicit combinations of amounts (20000, 30000, 40000) and time gaps (3600, 46800 seconds) listed above. 

It did **not** evaluate:
* Any other values for `prevAmount` or `curAmount` (e.g., amounts under 20000 or above 40000).
* Intermediate time gaps (e.g., exactly at the 12-hour boundary of 43,200 seconds, or any gap between 1 hour and 13 hours).
* Sessions spanning more than two consecutive transactions.

---

*A property drafted by a model and gated by Anchor. A person stated the requirement and confirmed a plain-English reading of the claim, which is better evidence than an unattended run and is still not a person having written the property.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 29,261 | 7,945 | 807 | 30,068 | 25.0 |
| draft round 2 (cut off) | 38,094 | 19,745 | 1,228 | 39,322 | 26.3 |
| draft round 3 | 44,839 | 31,409 | 1,244 | 46,083 | 20.0 |
| the review | 839 | 0 | 271 | 1,110 | 3.8 |
| the report | 930 | 0 | 1,685 | 2,615 | 12.0 |
| **5 model call(s)** | **113,963** | **59,099** | **5,235** | **119,198** | **87.2** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            82.3s
  preflight         0.0s
  score             6.3s
  review            3.8s
  confirm          12.0s
  check             3.6s
  answer           12.0s
  report            0.0s
  total           120.3s
```

Of which 87.2s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
