# 03-cumulative-cap.dw

**Stated intention.** Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught None broken version(s) of this policy.

## Verdicts

```
Policy: 03-cumulative-cap.dw
Property: Intent

The stated property is BROKEN.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  1 claim will be checked, over an unknown number of states -- the set `TimeGapsToTest` could not be enumerated.

  CumulativeCapIsEnforced
      says      always: LET holds
      forbids   LET does not hold

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 0
```

## Reported

**Verification Report for Policy `03-cumulative-cap.dw` and Property `Intent`**

The model checker reports that the stated property `Intent` is **BROKEN**.

This finding indicates that the verification process for the `Intent` property could not be completed. Specifically, the set `TimeGapsToTest`, which defines the scope for checking the property's claims, could not be enumerated. This issue with the property's definition prevented the claims from being effectively evaluated against the policy.

**What was checked:**

The property `Intent` contains one claim: `CumulativeCapIsEnforced`.

*   **`CumulativeCapIsEnforced`**: This claim was intended to assert that a specific condition (expressed as `LET holds`) is `always` true, forbidding situations where `LET does not hold`.
    *   **Verdict**: The verification for `CumulativeCapIsEnforced` **could not be completed**. The model checker was unable to enumerate the set `TimeGapsToTest`, meaning the check could not proceed over any specific, concrete set of states.
    *   **Bound**: The claim was intended to range over values within `TimeGapsToTest`. However, because `TimeGapsToTest` could not be enumerated, the claim was not checked over any concrete set of states.
    *   **Counterexample**: No counterexample was found or provided, as the claim could not be effectively checked. Therefore, no specific request or session can be cited as violating this claim.

**Finding regarding the property definition:**

The inability to enumerate `TimeGapsToTest` is a problem with the definition of the `Intent` property itself. Until `TimeGapsToTest` can be fully defined and enumerated, the claim `CumulativeCapIsEnforced` cannot be properly verified. This means the property as currently defined does not allow for a complete check of what it intended to state about the policy.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 4,806 | 4,106 | 8,912 | 33.0 |
| the report | 429 | 2,323 | 2,752 | 17.7 |
| **2 model call(s)** | **5,235** | **6,429** | **11,664** | **50.6** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            33.7s
  preflight         0.0s
  score             2.5s
  check             6.6s
  answer           17.7s
  report            0.0s
  total            60.6s
```

Of which 50.6s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
