# 01-workflow-sequencing.dw

**Stated intention.** A rebalance requires a portfolio load, which in turn requires a client profile to have been fetched, in that order.

## What was checked

`Intent.tla`, drafted from the intention above and kept because it does not hold on the policy as written -- it has already shown it can tell one policy from another, so it was not scored against mutants.

### Does it say what you asked for?

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: 01-workflow-sequencing.dw
Property: Intent

The stated property is BROKEN.
  RebalanceRequiresOrderedWorkflow is violated at {'scenario': '"load_only"'}

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  1 claim will be checked, over 5 states.
  scenario = "load_only", scenario = "load_then_profile", scenario = "none", scenario =
  "profile_only", scenario = "profile_then_load"

  RebalanceRequiresOrderedWorkflow
      says      whenever RebalanceAllowed holds, then scenario is "profile_then_load"
      forbids   RebalanceAllowed holds, and yet scenario is not "profile_then_load"
      applies   unknown -- `RebalanceAllowed` could not be worked out here for 5 of the 5 states

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 2
  rule 1 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
  rule 2 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
```

## Reported

### Summary of Results

The property **Intent** is **BROKEN**. 

The verification checked 1 claim across exactly **5 scenario states**:
* `scenario = "load_only"`
* `scenario = "load_then_profile"`
* `scenario = "none"`
* `scenario = "profile_only"`
* `scenario = "profile_then_load"`

Nothing was checked for scenarios or request values outside of these 5 named states.

---

### What Was Checked and What Failed

#### 1. `RebalanceRequiresOrderedWorkflow` — **VIOLATED**
* **Stated Claim:** Whenever rebalancing is allowed (`RebalanceAllowed`), the workflow scenario must be `"profile_then_load"`.
* **What it Forbids:** Rebalancing being permitted under any workflow scenario other than `"profile_then_load"`.
* **Counterexample:** 
  * Running the scenario **`"load_only"`** permitted a rebalance action, violating the requirement that rebalancing only occur after both profiling and loading in sequence (`"profile_then_load"`).

---

### Additional Findings: Rule Vacuity

The model checker also evaluated rule firing across sessions of **up to 3 attempts**:
* **Rule 1 (permit):** **VACUOUS** — No session of up to 3 attempts was able to trigger this rule to grant permission.
* **Rule 2 (permit):** **VACUOUS** — No session of up to 3 attempts was able to trigger this rule to grant permission.

Because neither rule granted access within 3 attempts, these rules were not actively exercised during testing at this session depth.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 | 158,217 | 99,088 | 7,717 | 165,934 | 121.9 |
| the review | 431 | 0 | 246 | 677 | 3.5 |
| the report | 569 | 0 | 743 | 1,312 | 8.0 |
| **3 model call(s)** | **159,217** | **99,088** | **8,706** | **167,923** | **133.4** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft           129.4s
  preflight         0.0s
  score             3.0s
  review            3.5s
  check            15.6s
  answer            8.0s
  report            0.0s
  total           159.6s
```

Of which 133.4s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
