# agent-policy.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

The person was then asked about this requirement, and said:

  Q: Name one thing this policy must NEVER allow. If somebody broke it, what would you see go wrong?
  A: An issue_refund of 2500 on charge_id 1 must be refused when there is no approved request_approval for that same charge_id in the previous 30 minutes. It must still be refused if the approval was for a different charge_id, or if it happened more than 30 minutes before the refund.

**A person was asked about this requirement 1 time(s), and the answers are part of it:**

- *Name one thing this policy must NEVER allow. If somebody broke it, what would you see go wrong?* — An issue_refund of 2500 on charge_id 1 must be refused when there is no approved request_approval for that same charge_id in the previous 30 minutes. It must still be refused if the approval was for a different charge_id, or if it happened more than 30 minutes before the refund.

## What was checked

`Intent.tla`, drafted from the intention above and kept because it caught 2 broken version(s) of this policy.

### Does it say what you asked for?

**A person was shown, in plain English, what this claim forbids, and confirmed it is what they meant — before anything was checked.** They did not read the formal claim, so what they confirmed is the reading of it; the two are generated from the same module and the reading is the part a person can audit.

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: agent-policy.dw
Property: Intent

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  6 claims will be checked, over an unknown number of states -- no readable Init.

  RefundOver500WithoutApprovalRefused
      says      whenever amount is 2500 and hasApproval does not hold, then RefundDecided does
                not hold
      forbids   amount is 2500 and hasApproval does not hold, and yet RefundDecided holds
      applies   to NONE of the 0 states

  RefundOver500WithUnapprovedResponseRefused
      says      whenever amount is 2500 and hasApproval holds and isApproved does not hold,
                then RefundDecided does not hold
      forbids   amount is 2500 and hasApproval holds and isApproved does not hold, and yet
                RefundDecided holds
      applies   to NONE of the 0 states

  RefundOver500WithMismatchedChargeRefused
      says      whenever amount is 2500 and hasApproval holds and approvalCharge is not
                refundCharge, then RefundDecided does not hold
      forbids   amount is 2500 and hasApproval holds and approvalCharge is not refundCharge,
                and yet RefundDecided holds
      applies   to NONE of the 0 states

  RefundOver500WithExpiredApprovalRefused
      says      whenever amount is 2500 and hasApproval holds and gap is greater than 30 *
                Minute (= 1800), then RefundDecided does not hold
      forbids   amount is 2500 and hasApproval holds and gap is greater than 30 * Minute (=
                1800), and yet RefundDecided holds
      applies   to NONE of the 0 states

  RefundOver500WithValidApprovalGranted
      says      whenever amount is 2500 and hasApproval holds and isApproved holds and
                approvalCharge is refundCharge and gap is at most 30 * Minute (= 1800), then
                RefundDecided holds
      forbids   amount is 2500 and hasApproval holds and isApproved holds and approvalCharge is
                refundCharge and gap is at most 30 * Minute (= 1800), and yet RefundDecided
                does not hold
      applies   to NONE of the 0 states

  RefundAtOrBelow500Granted
      says      whenever amount is 500, then RefundDecided holds
      forbids   amount is 500, and yet RefundDecided does not hold
      applies   to NONE of the 0 states

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

The derived questions were NOT attempted: this policy is outside the subset they can range over.
  REFUSED: agent-policy.dw is outside the modelled subset
  policy reads 6 input/output fields; the request space is the product of their domains, so this would explode (limit 4, raise with --max-fields)
That is a limit of those questions, not a verdict about the policy.
```

## Reported

### Verification Summary

The property module **`Intent`** returned a passing verdict (**HOLDS**), but **this result is vacuous**: exactly **0 states were evaluated** across all 6 claims. 

Because the model checker found no readable initial state (`Init`), the claims applied to no requests, meaning the policy was not actively tested against any scenarios.

---

### Key Findings About the Property

* **Zero States Evaluated:** Each of the 6 claims applied to **NONE of the 0 states**. The check passed solely because there were no states generated to violate the conditions, not because the policy was proven correct.
* **Narrow Concrete Values:** The claims in `Intent` only drafted checks for:
  * `amount = 2500` (for refunds over $500)
  * `amount = 500` (for refunds at or below $500)
  * A time gap threshold of `1800` seconds (30 minutes)
* **Untested Values:** Even if states had been generated, the property does not cover any other amounts (such as $0–$499, $501–$2,499, or amounts above $2,500), nor does it evaluate any scenarios outside these exact values.

---

### Detailed Claim Results

All claims below were evaluated over **0 states**:

1. **`RefundOver500WithoutApprovalRefused`**
   * *Claim:* When `amount = 2500` and `hasApproval` is false, refund is refused.
   * *Verdict:* Held vacuously (applied to 0 states).

2. **`RefundOver500WithUnapprovedResponseRefused`**
   * *Claim:* When `amount = 2500`, `hasApproval` is true, but `isApproved` is false, refund is refused.
   * *Verdict:* Held vacuously (applied to 0 states).

3. **`RefundOver500WithMismatchedChargeRefused`**
   * *Claim:* When `amount = 2500`, `hasApproval` is true, but `approvalCharge` does not match `refundCharge`, refund is refused.
   * *Verdict:* Held vacuously (applied to 0 states).

4. **`RefundOver500WithExpiredApprovalRefused`**
   * *Claim:* When `amount = 2500`, `hasApproval` is true, but `gap > 1800` seconds, refund is refused.
   * *Verdict:* Held vacuously (applied to 0 states).

5. **`RefundOver500WithValidApprovalGranted`**
   * *Claim:* When `amount = 2500`, `hasApproval` is true, `isApproved` is true, charges match, and `gap <= 1800` seconds, refund is granted.
   * *Verdict:* Held vacuously (applied to 0 states).

6. **`RefundAtOrBelow500Granted`**
   * *Claim:* When `amount = 500`, refund is granted.
   * *Verdict:* Held vacuously (applied to 0 states).

---

### Omitted Checks

* **Derived Questions:** Were **not attempted**. The policy reads 6 input/output fields, exceeding the default tool limit of 4 fields. This is an analysis limit, not a policy defect.

---

*A property drafted by a model and gated by Anchor. A person stated the requirement and confirmed a plain-English reading of the claim, which is better evidence than an unattended run and is still not a person having written the property.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 | 6,602 | 0 | 6,422 | 13,024 | 42.4 |
| the review | 987 | 0 | 649 | 1,636 | 6.2 |
| the report | 1,026 | 0 | 1,663 | 2,689 | 13.5 |
| **3 model call(s)** | **8,615** | **0** | **8,734** | **17,349** | **62.1** |

*None of that input was served from a prompt cache.* A retry re-sends the whole prior exchange, so whether that is billed in full is the difference between a cheap round and an expensive one. Gemini caches implicitly on a matching PREFIX; Strands cannot place an explicit cache point there, because its Gemini provider skips `cachePoint` blocks (models/gemini.py:251).

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft            50.7s
  preflight         0.0s
  score            20.9s
  review            6.2s
  confirm         295.9s
  check             0.9s
  answer           13.5s
  report            0.0s
  total           388.1s
```

Of which 62.1s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
