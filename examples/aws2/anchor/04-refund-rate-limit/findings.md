# 04-refund-rate-limit.dw

**Stated intention.** The agent might attempt no more than three refunds against the same account within one hour.

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught None broken version(s) of this policy.

## Verdicts

```
Policy: 04-refund-rate-limit.dw
Property: Intent

The stated property is BROKEN.
  FirstRefundForAccountAllowed is violated at {'currentAccount': '[k |-> "n", v |-> 1]', 'currentTimeGap': '1'}

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  5 claims will be checked, over 12 states.
  currentAccount = 1, currentTimeGap = 1, currentAccount = 1, currentTimeGap = 3597,
  currentAccount = 1, currentTimeGap = 3598, currentAccount = 1, currentTimeGap = 3599,
  currentAccount = 1, currentTimeGap = 3600, currentAccount = 1, currentTimeGap = 7200,
  currentAccount = 2, currentTimeGap = 1, currentAccount = 2, currentTimeGap = 3597, and 4 more

  FirstRefundForAccountAllowed
      says      always: the policy GRANTS it (VerdictForEvent(currentAccount, currentTimeGap,
                1))
      forbids   the policy REFUSES it (VerdictForEvent(currentAccount, currentTimeGap, 1))
      applies   to all 12 states -- it has no condition

  SecondRefundForAccountAllowed
      says      always: the policy GRANTS it (VerdictForEvent(currentAccount, currentTimeGap,
                2))
      forbids   the policy REFUSES it (VerdictForEvent(currentAccount, currentTimeGap, 2))
      applies   to all 12 states -- it has no condition

  ThirdRefundForAccountAllowed
      says      always: the policy GRANTS it (VerdictForEvent(currentAccount, currentTimeGap,
                3))
      forbids   the policy REFUSES it (VerdictForEvent(currentAccount, currentTimeGap, 3))
      applies   to all 12 states -- it has no condition

  FourthRefundDeniedIfWithinWindow
      says      whenever TotalSpanToFourthEvent(currentTimeGap) is at most Hour, then the
                policy REFUSES it (VerdictForEvent(currentAccount, currentTimeGap, 4))
      forbids   TotalSpanToFourthEvent(currentTimeGap) is at most Hour, and yet the policy
                GRANTS it (VerdictForEvent(currentAccount, currentTimeGap, 4))
      applies   to 6 of the 12: currentAccount = 1, currentTimeGap = 1, currentAccount = 1,
                currentTimeGap = 3597, currentAccount = 1, currentTimeGap = 3598,
                currentAccount = 2, currentTimeGap = 1, currentAccount = 2, currentTimeGap =
                3597, currentAccount = 2, currentTimeGap = 3598

  FourthRefundAllowedIfOutsideWindow
      says      whenever TotalSpanToFourthEvent(currentTimeGap) is greater than Hour, then the
                policy GRANTS it (VerdictForEvent(currentAccount, currentTimeGap, 4))
      forbids   TotalSpanToFourthEvent(currentTimeGap) is greater than Hour, and yet the policy
                REFUSES it (VerdictForEvent(currentAccount, currentTimeGap, 4))
      applies   to 6 of the 12: currentAccount = 1, currentTimeGap = 3599, currentAccount = 1,
                currentTimeGap = 3600, currentAccount = 1, currentTimeGap = 7200,
                currentAccount = 2, currentTimeGap = 3599, currentAccount = 2, currentTimeGap =
                3600, currentAccount = 2, currentTimeGap = 7200

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 0
```

## Reported

The `Intent` property was checked against policy `04-refund-rate-limit.dw`.

The stated property is **BROKEN**.

The check involved 5 claims across 12 specific combinations of `currentAccount` and `currentTimeGap`.
Specifically, it covered `currentAccount` values of `1` and `2`, combined with `currentTimeGap` values of `1`, `3597`, `3598`, `3599`, `3600`, and `7200`.

**What Held:**

*   **SecondRefundForAccountAllowed** held for all 12 states. For `currentAccount` values `1` and `2`, and `currentTimeGap` values `1`, `3597`, `3598`, `3599`, `3600`, and `7200`, the policy consistently **granted** the second refund request.
*   **ThirdRefundForAccountAllowed** held for all 12 states. For `currentAccount` values `1` and `2`, and `currentTimeGap` values `1`, `3597`, `3598`, `3599`, `3600`, and `7200`, the policy consistently **granted** the third refund request.
*   **FourthRefundDeniedIfWithinWindow** held for the 6 states it applied to: `currentAccount = 1, currentTimeGap = 1`, `currentAccount = 1, currentTimeGap = 3597`, `currentAccount = 1, currentTimeGap = 3598`, `currentAccount = 2, currentTimeGap = 1`, `currentAccount = 2, currentTimeGap = 3597`, and `currentAccount = 2, currentTimeGap = 3598`. For these specific scenarios, where the total time span to the fourth event was at most one hour, the policy correctly **refused** the fourth refund request.
*   **FourthRefundAllowedIfOutsideWindow** held for the 6 states it applied to: `currentAccount = 1, currentTimeGap = 3599`, `currentAccount = 1, currentTimeGap = 3600`, `currentAccount = 1, currentTimeGap = 7200`, `currentAccount = 2, currentTimeGap = 3599`, `currentAccount = 2, currentTimeGap = 3600`, and `currentAccount = 2, currentTimeGap = 7200`. For these specific scenarios, where the total time span to the fourth event was greater than one hour, the policy correctly **granted** the fourth refund request.

**What Did Not Hold:**

*   **FirstRefundForAccountAllowed** did not hold.
    *   This property claimed that the policy would always **grant** the first refund request for any of the 12 checked states (`currentAccount` values `1` and `2`, and `currentTimeGap` values `1`, `3597`, `3598`, `3599`, `3600`, `7200`).
    *   The model checker found a counterexample:
        The policy **refused the first refund request** when `currentAccount` was `1` and `currentTimeGap` was `1`. This means if account `1` makes its very first refund request (or a request with a `currentTimeGap` of `1`), the policy denies it, which contradicts the stated intention that the first refund should always be granted.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 4,809 | 5,412 | 10,221 | 23.4 |
| the report | 1,167 | 2,358 | 3,525 | 10.8 |
| **2 model call(s)** | **5,976** | **7,770** | **13,746** | **34.2** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            24.1s
  preflight         0.0s
  score             2.5s
  check             6.3s
  answer           10.8s
  report            0.0s
  total            43.9s
```

Of which 34.2s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
