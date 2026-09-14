# 01-workflow-sequencing.dw

**Stated intention.** The profile a trade is executed against must be the one this trajectory actually loaded — not merely that some profile was loaded at some point.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
> - draft round 2 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## What was checked

`Intent02OutputToInput.tla`, drafted from the intention above and kept because it does not hold on the policy as written -- it has already shown it can tell one policy from another, so it was not scored against mutants.

### Does it say what you asked for?

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: 01-workflow-sequencing.dw
Property: Intent02OutputToInput

The stated property is BROKEN.
  ProfileMustMatchLoaded is violated at {'requestedProfile': '"profile_2"', 'loadedProfile': '"profile_1"'}

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent02OutputToInput

  1 claim will be checked, over 4 states.
  loadedProfile = "profile_1", requestedProfile = "profile_1", loadedProfile = "profile_1",
  requestedProfile = "profile_2", loadedProfile = "profile_2", requestedProfile = "profile_1",
  loadedProfile = "profile_2", requestedProfile = "profile_2"

  ProfileMustMatchLoaded
      says      whenever requestedProfile is not loadedProfile, then the policy REFUSES it
                (RebalanceAllowed(loadedProfile, requestedProfile))
      forbids   requestedProfile is not loadedProfile, and yet the policy GRANTS it
                (RebalanceAllowed(loadedProfile, requestedProfile))
      applies   to 2 of the 4: loadedProfile = "profile_1", requestedProfile = "profile_2",
                loadedProfile = "profile_2", requestedProfile = "profile_1"

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 2
  rule 1 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
  rule 2 (permit): VACUOUS -- no session of up to 3 attempts makes it grant
```

## Reported

### Verification Result: Broken

The property **`Intent02OutputToInput`** did not hold for policy **`01-workflow-sequencing.dw`**.

---

### What Was Checked and the Concrete Bounds

The verification checked **1 claim** (`ProfileMustMatchLoaded`) across exactly **4 distinct state combinations**:
* `loadedProfile` $\in$ `{ "profile_1", "profile_2" }`
* `requestedProfile` $\in$ `{ "profile_1", "profile_2" }`

The claim's condition (that mismatched profiles must be refused) applied to **2 of those 4 states**:
1. `loadedProfile` = `"profile_1"`, `requestedProfile` = `"profile_2"`
2. `loadedProfile` = `"profile_2"`, `requestedProfile` = `"profile_1"`

*Note: This check tested only these two profiles (`"profile_1"` and `"profile_2"`). It did not test any other profile names, inputs, or execution paths.*

---

### Counterexample

The claim **`ProfileMustMatchLoaded`** failed:

* **Scenario:** A rebalance request is evaluated where the currently loaded profile is **`"profile_1"`** and the requested profile is **`"profile_2"`**.
* **Result:** The policy granted permission (`RebalanceAllowed`), despite the requested profile differing from the loaded profile.

---

### Additional Findings

* **Vacuous Rules:** 
  * **Rule 1 (permit)**: Vacuous — no session of up to 3 attempts resulted in this rule granting access.
  * **Rule 2 (permit)**: Vacuous — no session of up to 3 attempts resulted in this rule granting access.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 28,453 | 11,911 | 1,135 | 29,588 | 53.7 |
| draft round 2 (cut off) | 39,852 | 23,748 | 2,428 | 42,280 | 39.3 |
| draft round 3 | 11,948 | 7,909 | 333 | 12,281 | 6.5 |
| the review | 509 | 0 | 241 | 750 | 6.7 |
| the report | 658 | 0 | 995 | 1,653 | 12.5 |
| **5 model call(s)** | **81,420** | **43,568** | **5,132** | **86,552** | **118.6** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft           107.5s
  preflight         0.0s
  score             3.4s
  review            6.7s
  check             0.0s
  answer           12.5s
  report            0.0s
  total           130.0s
```

Of which 118.6s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
