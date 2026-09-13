# firewall.dw

**Stated intention.** SSH from the local range is permitted, and every external source is denied.

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught 2 broken version(s) of this policy.

## Verdicts

```
Policy: firewall.dw
Property: Intent

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

Intent

  2 claims will be checked, over 6 states.
  req = [origin |-> "external", port |-> 21], req = [origin |-> "external", port |-> 22], req =
  [origin |-> "external", port |-> 23], req = [origin |-> "local", port |-> 21], req = [origin
  |-> "local", port |-> 22], req = [origin |-> "local", port |-> 23]

  LocalSshIsPermitted
      \* SSH from the local range is permitted.
      says      whenever req.port is 22 and req.origin is "local", then the policy GRANTS it
                (Grants(req))
      forbids   req.port is 22 and req.origin is "local", and yet the policy REFUSES it
                (Grants(req))
      applies   to 1 of the 6: req = [origin |-> "local", port |-> 22]

  ExternalIsDenied
      \* Every external source is denied.
      says      whenever req.origin is "external", then the policy REFUSES it (Grants(req))
      forbids   req.origin is "external", and yet the policy GRANTS it (Grants(req))
      applies   to 3 of the 6: req = [origin |-> "external", port |-> 21], req = [origin |->
                "external", port |-> 22], req = [origin |-> "external", port |-> 23]

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

Derived findings: 0
```

## Reported

Here is the report on the `Intent` property for your `firewall.dw` policy.

The `Intent` property **HOLDS**.

---

**What was checked:**

The `Intent` property consists of 2 claims that were checked for 6 specific request states:
*   `[origin |-> "external", port |-> 21]`
*   `[origin |-> "external", port |-> 22]`
*   `[origin |-> "external", port |-> 23]`
*   `[origin |-> "local", port |-> 21]`
*   `[origin |-> "local", port |-> 22]`
*   `[origin |-> "local", port |-> 23]`

**Findings for each claim:**

1.  **LocalSshIsPermitted**
    *   **Stated intention:** "SSH from the local range is permitted."
    *   **What was actually forbidden:** The policy refusing a request where the origin is `"local"` AND the port is `22`.
    *   **Verdict:** This claim **HOLDS** for the request `[origin |-> "local", port |-> 22]`.
    *   **What this means:** When a request originates from `"local"` and targets port `22`, your policy grants it, as checked for this specific request.

2.  **ExternalIsDenied**
    *   **Stated intention:** "Every external source is denied."
    *   **What was actually forbidden:** The policy granting a request where the origin is `"external"`.
    *   **Verdict:** This claim **HOLDS** for the following 3 requests:
        *   `[origin |-> "external", port |-> 21]`
        *   `[origin |-> "external", port |-> 22]`
        *   `[origin |-> "external", port |-> 23]`
    *   **What this means:** For requests originating from `"external"` with ports `21`, `22`, or `23`, your policy refuses them, as checked for these specific requests.

---

**Important Note:** This verification report applies only to the specific requests and ports that were explicitly named in the property and listed above. It does not make any statements or guarantees about requests with different origins, ports, or other attributes not included in this bounded check.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 4,914 | 2,430 | 7,344 | 16.4 |
| the report | 728 | 841 | 1,569 | 6.9 |
| **2 model call(s)** | **5,642** | **3,271** | **8,913** | **23.3** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            17.2s
  preflight         0.0s
  score             6.0s
  check            12.4s
  answer            6.9s
  report            0.0s
  total            42.7s
```

Of which 23.3s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
