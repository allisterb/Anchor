# 02-identity-verification.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
  Intent.tla DOES NOT COMPILE. SANY says:

      ****** SANY2 Version 2.1 created 24 February 2014
      
      Parsing file C:\Users\Allister\AppData\Local\Temp\anchor-prove-fo_q698r\Intent.tla
      ***Parse Error***
      Encountered "verifyEv" at line 80, column 9 and token "LET" 
      
      Residual stack trace follows:
      Let Definitions starting at line 80, column 9.
      Case Other Arm starting at line 79, column 5.
      Expression starting at line 79, column 5.
      Definition starting at line 78, column 1.
      Module body starting at line 9, column 1.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 4,878 | 3,305 | 8,183 | 25.7 |
| draft round 2 | 11,064 | 4,323 | 15,387 | 20.5 |
| draft round 3 | 17,309 | 2,609 | 19,918 | 16.7 |
| **3 model call(s)** | **33,251** | **10,237** | **43,488** | **62.9** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            64.3s
  preflight         0.0s
  score             0.5s
  report            0.0s
  total            65.0s
```

Of which 62.9s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
