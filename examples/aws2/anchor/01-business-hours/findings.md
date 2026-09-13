# 01-business-hours.dw

**Stated intention.** Refunds might be issued only during business hours, defined as 9:00 AM-5:00 PM UTC, and only for amounts of $2,500 or less.

*Drafted in 2 of 3 attempt(s).*

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught None broken version(s) of this policy.

## Verdicts

```
Policy: 01-business-hours.dw
Property: Intent

The stated property is BROKEN.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  2 claims will be checked, over an unknown number of states -- .

  AmountTooHighIsDenied
      \* Claim 1: Refunds for amounts greater than $2,500 must be denied.
      says      whenever req.amount is greater than MaxRefundAmount, then the policy REFUSES it
                (Grants(req))
      forbids   req.amount is greater than MaxRefundAmount, and yet the policy GRANTS it
                (Grants(req))
      applies   to NONE of the 0 states

  OutsideBusinessHoursIsDenied
      \* Claim 2: Refunds outside business hours must be denied.
      says      whenever req.systemNowTime is less than NineAM or req.systemNowTime is greater
                than FivePM, then the policy REFUSES it (Grants(req))
      forbids   req.systemNowTime is less than NineAM or req.systemNowTime is greater than
                FivePM, and yet the policy GRANTS it (Grants(req))
      applies   to NONE of the 0 states

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 0
```

## Reported

The property `Intent` for policy `01-business-hours.dw` is BROKEN.

Two claims within the `Intent` property were defined for checking the policy, over an unknown number of states overall. However, neither claim's triggering condition was met during the model check, meaning they were effectively not tested.

1.  **Claim: Refunds for amounts greater than $2,500 must be denied.**
    *   This claim intended to verify that if a request had an amount greater than `MaxRefundAmount` (which is $2,500), the policy would refuse it.
    *   The model checker observed `NONE of the 0 states` where `req.amount` was greater than `MaxRefundAmount`.
    *   Therefore, the check could not confirm whether the policy denies requests for amounts exceeding $2,500, nor could it find any counterexample where such a request was granted. The scenario described by this claim was not encountered at the bound of this check.

2.  **Claim: Refunds outside business hours must be denied.**
    *   This claim intended to verify that if a request's `systemNowTime` was before `NineAM` or after `FivePM`, the policy would refuse it.
    *   The model checker observed `NONE of the 0 states` where `req.systemNowTime` was less than `NineAM` or greater than `FivePM`.
    *   Therefore, the check could not confirm whether the policy denies requests made outside business hours, nor could it find any counterexample where such a request was granted. The scenario described by this claim was not encountered at the bound of this check.

**Summary of Verification Results:**

At the bound of this model check (an unknown number of overall states, and specifically 0 states where the conditions for either claim were met):

*   Neither of the claims in the `Intent` property could be evaluated, as the scenarios they describe (requests with amounts over $2,500, or requests outside business hours) were not found in the explored state space.
*   No counterexamples were found for these specific conditions because the conditions themselves were not observed.
*   The overall verdict that the property `Intent` is BROKEN indicates a fundamental issue, possibly due to the model not generating states relevant to these conditions or an underlying problem with the property's execution.

**Finding regarding the property:**

Because the conditions for `AmountTooHighIsDenied` and `OutsideBusinessHoursIsDenied` were never met (`applies to NONE of the 0 states`), the property, as it ran, did not actually check the policy's behavior for high-value refunds or refunds requested outside business hours. The property failed to check what its stated intentions meant, as the necessary scenarios were not explored.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,017 | 3,407 | 8,424 | 26.0 |
| draft round 2 | 11,172 | 1,351 | 12,523 | 7.6 |
| the report | 610 | 2,456 | 3,066 | 12.4 |
| **3 model call(s)** | **16,799** | **7,214** | **24,013** | **46.0** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            34.8s
  preflight         0.0s
  score             2.4s
  check             7.0s
  answer           12.4s
  report            0.0s
  total            56.9s
```

Of which 46.0s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
