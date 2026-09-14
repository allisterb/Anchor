# agent-policy.dw

**Stated intention.** Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
  CumulativeCap.tla DOES NOT COMPILE. SANY says:

      ****** SANY2 Version 2.1 created 24 February 2014
      
      Parsing file C:\Users\Allister\AppData\Local\Temp\anchor-prove-80vg7d4i\CumulativeCap.tla
      ***Parse Error***
      Encountered ":" at line 27, column 92 and token "}" 
      
      Residual stack trace follows:
      Some { } form starting at line 27, column 39.
      ExtendableExpr starting at line 27, column 39.
      Expression starting at line 27, column 39.
      Definition starting at line 27, column 9.
      Let Definitions starting at line 25, column 9.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,894 | 4,723 | 10,617 | 21.8 |
| draft round 2 | 12,934 | 3,337 | 16,271 | 16.9 |
| draft round 3 | 19,974 | 1,767 | 21,741 | 27.5 |
| **3 model call(s)** | **38,802** | **9,827** | **48,629** | **66.2** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            68.0s
  preflight         0.0s
  score             0.5s
  report            0.0s
  total            68.6s
```

Of which 66.2s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
