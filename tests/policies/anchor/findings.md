# firewall.dw

**Stated intention.** SSH from the local range is permitted, and every external source is denied.

## What was checked

`Intent.tla`, drafted from the intention above and kept only because it caught 2 broken version(s) of this policy.

## Verdicts

```
Policy: firewall.dw
Property: Intent

The stated property HOLDS.

Derived findings: 0
```

## Reported

Original Task: State and check the intention for firewall.dw.

Inputs from previous nodes:

From answer:
  - Agent: Here is the verification report for your `firewall.dw` policy:

**Verification Report for `firewall.dw` Policy**

We checked the property named `Intent` within your `firewall.dw` policy. This property is designed to formally specify the intended behavior or purpose of the policy.

**Results:**

The property `Intent` **HOLDS**.

**Meaning of the Result:**

This means that for all possible requests and scenarios, your `firewall.dw` policy is guaranteed to behave in a way that is consistent with the formal `Intent` property. No situations were found where the policy's actions would violate its stated intent.

**Counterexamples:**

No counterexamples were found, as the property holds for all observed behaviors of the policy. Your policy, as written, fulfills the requirements specified by the `Intent` property.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*
