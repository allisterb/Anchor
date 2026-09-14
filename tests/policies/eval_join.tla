---------------------------- MODULE eval_join ----------------------------
\* Sessions for tests/policies/eval_join.dw. Exists to be EVALUATED, not to be checked -- see the
\* policy's header for what broke.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Verify(t)   == Ev("verify_identity", "response", [account |-> Str("a1")],
                  [verified |-> Bool(TRUE)], t)
Transfer(t) == Ev("initiate_transfer", "request",
                  [account |-> Str("a1"), amount |-> Num(1000)], NoFields, t)

Session(gap) == << Verify(1), Transfer(1 + gap) >>
Allowed(gap) == D!Decide(Session(gap), Policies, 2, AllValues)

VARIABLE gap
Init == gap \in {60, 3600}
Next == UNCHANGED gap
Spec == Init /\ [][Next]_gap

WithinWindowIsAllowed == (gap = 60) => Allowed(gap)
=============================================================================
