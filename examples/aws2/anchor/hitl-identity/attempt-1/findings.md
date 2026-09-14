# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

IF EVERY CLAIM YOU WROTE SAYS SOMETHING MUST BE REFUSED, THAT IS WHY. Every mutation tried removes or narrows a permission, and a policy that refuses more still refuses everything you said must be refused. Add at least one claim saying what the policy MUST ALLOW -- the request that has met every condition and has to go through. That is the claim a deleted or inverted permit breaks.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 | 6,405 | 0 | 3,538 | 9,943 | 30.0 |
| **1 model call(s)** | **6,405** | **0** | **3,538** | **9,943** | **30.0** |

*None of that input was served from a prompt cache.* A retry re-sends the whole prior exchange, so whether that is billed in full is the difference between a cheap round and an expensive one. Gemini caches implicitly on a matching PREFIX; Strands cannot place an explicit cache point there, because its Gemini provider skips `cachePoint` blocks (models/gemini.py:251).

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            38.6s
  preflight         0.0s
  score            20.6s
  report            0.0s
  total            59.5s
```

Of which 30.0s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
