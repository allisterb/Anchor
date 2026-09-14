# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 2 of 3 attempt(s).*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

IF EVERY CLAIM YOU WROTE SAYS SOMETHING MUST BE REFUSED, THAT IS WHY. Every mutation tried removes or narrows a permission, and a policy that refuses more still refuses everything you said must be refused. Add at least one claim saying what the policy MUST ALLOW -- the request that has met every condition and has to go through. That is the claim a deleted or inverted permit breaks.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 72,007 | 31,713 | 1,980 | 73,987 | 52.8 |
| draft round 2 | 68,133 | 47,451 | 2,819 | 70,952 | 35.8 |
| **2 model call(s)** | **140,140** | **79,164** | **4,799** | **144,939** | **88.6** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            96.7s
  preflight         0.0s
  score            19.5s
  report            0.0s
  total           116.4s
```

Of which 88.6s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
