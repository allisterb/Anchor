# 01-workflow-sequencing.dw

**Stated intention.** A rebalance requires a portfolio load, which in turn requires a client profile to have been fetched, in that order.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 2 of 3 attempt(s).*

## What was checked

`Intent01WorkflowSequencing.tla`, drafted from the intention above and kept because it caught 2 broken version(s) of this policy.

### Does it say what you asked for?

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: 01-workflow-sequencing.dw
Property: Intent01WorkflowSequencing

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent01WorkflowSequencing

  2 claims will be checked, over 4 states.
  hasProfile = FALSE, hasLoad = FALSE, hasProfile = FALSE, hasLoad = TRUE, hasProfile = TRUE,
  hasLoad = FALSE, hasProfile = TRUE, hasLoad = TRUE

  LoadRequiresProfile
      says      whenever LoadAllowed holds, then hasProfile holds
      forbids   LoadAllowed holds, and yet hasProfile does not hold
      applies   unknown -- `LoadAllowed` could not be worked out here for 4 of the 4 states

  RebalanceRequiresLoad
      says      whenever RebalanceAllowed holds, then hasLoad holds
      forbids   RebalanceAllowed holds, and yet hasLoad does not hold
      applies   unknown -- `RebalanceAllowed` could not be worked out here for 4 of the 4 states

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 2
  rule 1 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
  rule 2 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
```

## Reported

### Verification Summary: `01-workflow-sequencing.dw`

**Result:** The property `Intent01WorkflowSequencing` **passed**, but the result is **vacuous**.

---

### What Was Checked and the Bounds

The verification examined **2 claims** across exactly **4 states**, formed by the combinations of:
* `hasProfile` ∈ {`TRUE`, `FALSE`}
* `hasLoad` ∈ {`TRUE`, `FALSE`}

The claims checked:
1. **`LoadRequiresProfile`**: Forbids `LoadAllowed` being true when `hasProfile` is false.
2. **`RebalanceRequiresLoad`**: Forbids `RebalanceAllowed` being true when `hasLoad` is false.

The analysis also evaluated request sequences bounded at **up to 3 attempts**.

---

### Findings on the Policy and Property

While the property technically held over the 4 states, it did so without testing real policy behavior:

* **Vacuous Rules:** Neither Rule 1 (permit) nor Rule 2 (permit) ever granted access across any session of up to 3 attempts.
* **Unexercised Claims:** Because `LoadAllowed` and `RebalanceAllowed` never evaluated to true, the check never had to evaluate whether `hasProfile` or `hasLoad` were correctly present during an allowed action.

The check passed solely because the forbidden condition (granting without the required prerequisite) could not occur when grants never happen at all.

---

### What Was Not Checked

* **Sessions longer than 3 attempts:** Behavior beyond 3 sequential requests was not evaluated.
* **Unlisted attributes and operations:** No requests, parameters, or attributes outside of the 4 boolean combinations of `hasProfile` and `hasLoad` were checked.
* **Valid permit paths:** Because neither permit rule triggered, whether the workflow correctly allows valid requests remains untested.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 31,106 | 7,955 | 1,616 | 32,722 | 28.7 |
| draft round 2 | 41,541 | 27,711 | 2,384 | 43,925 | 28.8 |
| the review | 486 | 0 | 214 | 700 | 12.3 |
| the report | 609 | 0 | 1,176 | 1,785 | 9.3 |
| **4 model call(s)** | **73,742** | **35,666** | **5,390** | **79,132** | **79.1** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            64.2s
  preflight         0.0s
  score            12.7s
  review           12.3s
  check            14.6s
  answer            9.3s
  report            0.0s
  total           113.3s
```

Of which 79.1s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
