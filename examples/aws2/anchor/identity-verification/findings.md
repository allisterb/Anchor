# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
  IdentityVerification.tla DOES NOT COMPILE. SANY says:

      ****** SANY2 Version 2.1 created 24 February 2014
      
      Parsing file C:\Users\Allister\AppData\Local\Temp\anchor-prove-047uwe08\IdentityVerification.tla
      ***Parse Error***
      Encountered "Beginning of definition" at line 48, column 71 and token "." 
      
      Residual stack trace follows:
      ExtendableExpr starting at line 48, column 5.
      Expression starting at line 48, column 5.
      Definition starting at line 47, column 1.
      Module body starting at line 16, column 1.
      Module definition starting at line 7, column 1.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,895 | 5,933 | 11,828 | 27.1 |
| draft round 2 | 12,969 | 10,790 | 23,759 | 50.4 |
| draft round 3 | 20,309 | 2,188 | 22,497 | 14.7 |
| **3 model call(s)** | **39,173** | **18,911** | **58,084** | **92.2** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft           100.4s
  preflight         0.1s
  score             0.5s
  report            0.0s
  total           101.1s
```

Of which 92.2s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
