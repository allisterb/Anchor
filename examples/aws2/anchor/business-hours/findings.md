# agent-policy.dw

**Stated intention.** Refunds might be issued only during business hours, defined as 9:00 AM-5:00 PM UTC, and only for amounts of $2,500 or less.

*Drafted in 3 of 3 attempt(s).*

## What was checked

`BusinessHours.tla`, drafted from the intention above and kept because it caught 1 broken version(s) of this policy.

### Does it say what you asked for?

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: agent-policy.dw
Property: BusinessHours

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

BusinessHours

  3 claims will be checked, over 64 states.
  req = [account |-> 1, amount |-> 2500, charge_id |-> 1, systemNowTime |-> 32399999], req =
  [account |-> 1, amount |-> 2500, charge_id |-> 1, systemNowTime |-> 32400000], req = [account
  |-> 1, amount |-> 2500, charge_id |-> 1, systemNowTime |-> 61200000], req = [account |-> 1,
  amount |-> 2500, charge_id |-> 1, systemNowTime |-> 61200001], req = [account |-> 1, amount
  |-> 2500, charge_id |-> 2, systemNowTime |-> 32399999], req = [account |-> 1, amount |->
  2500, charge_id |-> 2, systemNowTime |-> 32400000], req = [account |-> 1, amount |-> 2500,
  charge_id |-> 2, systemNowTime |-> 61200000], req = [account |-> 1, amount |-> 2500,
  charge_id |-> 2, systemNowTime |-> 61200001], and 56 more

  RefundsOnlyDuringBusinessHoursAndWithinLimit
      says      whenever the policy GRANTS it (GrantsRefund(req)), then req.systemNowTime is
                one of BusinessHoursValues and req.amount is one of AllowedAmounts
      forbids   the policy GRANTS it (GrantsRefund(req)), and yet req.systemNowTime is not one
                of BusinessHoursValues or req.amount is not one of AllowedAmounts
      applies   unknown -- `GrantsRefund(req)` could not be worked out here for 64 of the 64 states

  OutsideBusinessHoursRefused
      says      whenever req.systemNowTime is not one of BusinessHoursValues, then the policy
                REFUSES it (GrantsRefund(req))
      forbids   req.systemNowTime is not one of BusinessHoursValues, and yet the policy GRANTS
                it (GrantsRefund(req))
      applies   to 32 of the 64: req = [account |-> 1, amount |-> 2500, charge_id |-> 1,
                systemNowTime |-> 32399999], req = [account |-> 1, amount |-> 2500, charge_id
                |-> 1, systemNowTime |-> 61200001], req = [account |-> 1, amount |-> 2500,
                charge_id |-> 2, systemNowTime |-> 32399999], req = [account |-> 1, amount |->
                2500, charge_id |-> 2, systemNowTime |-> 61200001], req = [account |-> 1,
                amount |-> 2501, charge_id |-> 1, systemNowTime |-> 32399999], req = [account
                |-> 1, amount |-> 2501, charge_id |-> 1, systemNowTime |-> 61200001], and 26
                more

  OverLimitRefused
      says      whenever req.amount is not one of AllowedAmounts, then the policy REFUSES it
                (GrantsRefund(req))
      forbids   req.amount is not one of AllowedAmounts, and yet the policy GRANTS it
                (GrantsRefund(req))
      applies   to 16 of the 64: req = [account |-> 1, amount |-> 2501, charge_id |-> 1,
                systemNowTime |-> 32399999], req = [account |-> 1, amount |-> 2501, charge_id
                |-> 1, systemNowTime |-> 32400000], req = [account |-> 1, amount |-> 2501,
                charge_id |-> 1, systemNowTime |-> 61200000], req = [account |-> 1, amount |->
                2501, charge_id |-> 1, systemNowTime |-> 61200001], req = [account |-> 1,
                amount |-> 2501, charge_id |-> 2, systemNowTime |-> 32399999], req = [account
                |-> 1, amount |-> 2501, charge_id |-> 2, systemNowTime |-> 32400000], and 10
                more

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

The property **BusinessHours** **HELD** over the **64 specific request states** evaluated.

No counterexamples were found within this tested set.

---

### Bound and Evaluated States

The model checker evaluated exactly **64 concrete request states** formed from combinations of:
- **`systemNowTime`**: `32399999`, `32400000`, `61200000`, `61200001`
- **`amount`**: `2500`, `2501` (and other values within the 64-state set)
- **`charge_id`**: `1`, `2`
- **`account`**: `1` (and associated values within the 64-state set)

This verification applies **only** to these 64 specific combinations. It does not establish behavior for any other timestamps, amounts, charge IDs, accounts, or request parameters not explicitly enumerated.

---

### Claims Checked

1. **`RefundsOnlyDuringBusinessHoursAndWithinLimit`**
   - **What it checked**: Forbade granting a refund (`GrantsRefund(req)`) when `req.systemNowTime` is outside `BusinessHoursValues` or `req.amount` is outside `AllowedAmounts`.
   - **Verdict**: Held across the evaluated states.

2. **`OutsideBusinessHoursRefused`**
   - **What it checked**: Forbade granting a refund when `req.systemNowTime` is outside `BusinessHoursValues`.
   - **Scope**: Applied to **32 of the 64 states** (specifically requests with timestamps `32399999` and `61200001`).
   - **Verdict**: Held across all 32 applicable states.

3. **`OverLimitRefused`**
   - **What it checked**: Forbade granting a refund when `req.amount` is not in `AllowedAmounts`.
   - **Scope**: Applied to **16 of the 64 states** (specifically requests with `amount = 2501`).
   - **Verdict**: Held across all 16 applicable states.

---

### What Was Not Checked

- **Derived / Automated Questions**: Not attempted. The policy reads 6 input/output fields, which exceeds the automated checker's limit of 4 fields.
- **Unchecked Input Domains**: Any request with different timestamps, amounts, accounts, charge IDs, or additional input fields not present in the 64 concrete states remains unverified.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,419 | 2,775 | 9,194 | 17.0 |
| draft round 2 | 15,681 | 4,239 | 19,920 | 338.5 |
| draft round 3 | 26,462 | 10,048 | 36,510 | 56.8 |
| the review | 1,506 | 349 | 1,855 | 3.5 |
| the report | 1,641 | 1,204 | 2,845 | 9.8 |
| **5 model call(s)** | **51,709** | **18,615** | **70,324** | **425.6** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft           432.3s
  preflight         0.0s
  score            20.8s
  review            3.5s
  check             3.2s
  answer            9.8s
  report            0.0s
  total           469.8s
```

Of which 425.6s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
