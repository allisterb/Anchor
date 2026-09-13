# 06-supervisor-approval.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught None broken version(s) of this policy.

## Verdicts

```
Policy: 06-supervisor-approval.dw
Property: Intent

The stated property is BROKEN.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  3 claims will be checked, over 36 states.
  charge = 1, refundAmount = 499, gap = 0, charge = 1, refundAmount = 499, gap = 60, charge =
  1, refundAmount = 499, gap = 900, charge = 1, refundAmount = 499, gap = 1800, charge = 1,
  refundAmount = 499, gap = 1801, charge = 1, refundAmount = 499, gap = 2700, charge = 1,
  refundAmount = 500, gap = 0, charge = 1, refundAmount = 500, gap = 60, and 28 more

  SmallRefundsAlwaysAllowed
      says      whenever refundAmount is at most 500, then the policy GRANTS it
                (RefundAllowed(charge, refundAmount, gap))
      forbids   refundAmount is at most 500, and yet the policy REFUSES it
                (RefundAllowed(charge, refundAmount, gap))
      applies   unknown -- `refundAmount <= Num(500)` could not be worked out here for 36 of the 36 states

  LargeRefundsWithinTimeWindowAreAllowed
      says      whenever refundAmount is greater than 500 and gap is at most ThirtyMinutes,
                then the policy GRANTS it (RefundAllowed(charge, refundAmount, gap))
      forbids   refundAmount is greater than 500 and gap is at most ThirtyMinutes, and yet the
                policy REFUSES it (RefundAllowed(charge, refundAmount, gap))
      applies   unknown -- `refundAmount > Num(500) /\ gap <= ThirtyMinutes` could not be worked out here for 24 of the 36 states

  LargeRefundsAfterTimeWindowAreRefused
      says      whenever refundAmount is greater than 500 and gap is greater than
                ThirtyMinutes, then the policy REFUSES it (RefundAllowed(charge, refundAmount,
                gap))
      forbids   refundAmount is greater than 500 and gap is greater than ThirtyMinutes, and yet
                the policy GRANTS it (RefundAllowed(charge, refundAmount, gap))
      applies   unknown -- `refundAmount > Num(500) /\ gap > ThirtyMinutes` could not be worked out here for 12 of the 36 states

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 0
```

## Reported

The policy `06-supervisor-approval.dw` was checked against the property `Intent`.

The property `Intent` is **BROKEN**.

The model checker attempted to evaluate 3 claims over a set of **36 states**. These states represented combinations of `charge` values of `1`; `refundAmount` values of `499` and `500`; and `gap` values of `0`, `60`, `900`, `1800`, `1801`, and `2700`.

However, the property could not determine whether its conditions applied to any of these states. This means that none of the stated intentions could be verified or falsified by this check for these inputs.

Here's a breakdown of each claim:

1.  **SmallRefundsAlwaysAllowed**
    *   This claim says that whenever `refundAmount` is at most `500`, the policy GRANTS the refund request.
    *   It forbids a situation where `refundAmount` is at most `500`, and yet the policy REFUSES the refund request.
    *   **Finding:** The condition `refundAmount <= Num(500)` **could not be worked out** for any of the 36 checked states. Therefore, the property could not determine whether this claim applied to any of the scenarios. No verification was performed for this claim over the checked states.

2.  **LargeRefundsWithinTimeWindowAreAllowed**
    *   This claim says that whenever `refundAmount` is greater than `500` AND `gap` is at most `ThirtyMinutes`, the policy GRANTS the refund request.
    *   It forbids a situation where `refundAmount` is greater than `500` AND `gap` is at most `ThirtyMinutes`, and yet the policy REFUSES the refund request.
    *   **Finding:** The condition `refundAmount > Num(500) /\ gap <= ThirtyMinutes` **could not be worked out** for 24 of the 36 checked states. No verification was performed for this claim over the checked states where its condition was relevant.

3.  **LargeRefundsAfterTimeWindowAreRefused**
    *   This claim says that whenever `refundAmount` is greater than `500` AND `gap` is greater than `ThirtyMinutes`, the policy REFUSES the refund request.
    *   It forbids a situation where `refundAmount` is greater than `500` AND `gap` is greater than `ThirtyMinutes`, and yet the policy GRANTS the refund request.
    *   **Finding:** The condition `refundAmount > Num(500) /\ gap > ThirtyMinutes` **could not be worked out** for 12 of the 36 checked states. No verification was performed for this claim over the checked states where its condition was relevant.

**Conclusion on Intention:**

The property `Intent`, as drafted, **did not achieve its stated intention** during this check. Its conditions for `SmallRefundsAlwaysAllowed`, `LargeRefundsWithinTimeWindowAreAllowed`, and `LargeRefundsAfterTimeWindowAreRefused` could not be evaluated for any of the 36 concrete input scenarios tested. This means that none of the claims were actually applied or tested against the policy for the given input ranges. The property effectively failed to check anything meaningful about the policy's behavior for these specific `charge`, `refundAmount`, and `gap` values. No counterexamples could be produced because the conditions for triggering a check were never met.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 4,988 | 4,794 | 9,782 | 20.8 |
| the report | 937 | 1,795 | 2,732 | 9.2 |
| **2 model call(s)** | **5,925** | **6,589** | **12,514** | **30.1** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            21.6s
  preflight         0.0s
  score             2.0s
  check             7.6s
  answer            9.2s
  report            0.0s
  total            40.7s
```

Of which 30.1s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
