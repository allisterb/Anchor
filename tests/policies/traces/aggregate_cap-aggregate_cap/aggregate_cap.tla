---------------------------- MODULE aggregate_cap ----------------------------
\* What `aggregate_cap.dw` means for a session carrying values the policy never names.
\*
\* THE REGRESSION THIS PINS. An aggregate binder must range over the scalars the TRACE carries as
\* well as the generated domain. `Num(500)` is in neither the policy's literals nor the default
\* numeric domain {1, 2}, so before the fix the sum skipped it entirely: the total came out 0, the
\* cap of 100 was never reached, and the transfer was reported ALLOWED. A total that omits a term
\* is not reported as uncertain -- it is reported as a smaller number, which is a wrong verdict
\* with no symptom.
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Transfer(amt, t) == Ev("transfer", "request", [amount |-> Num(amt)], NoFields, t)

Amounts == {5, 500}
Session(amt) == << Transfer(amt, 1) >>
Allowed(amt) == D!Decide(Session(amt), Policies, 1, AllValues)

VARIABLE amount
Init == amount \in Amounts
Next == UNCHANGED amount
Spec == Init /\ [][Next]_amount

\* Over the cap is refused, under it is allowed. Both halves, because a model that summed nothing
\* would pass the second and fail the first, and one that summed everything into a huge number
\* would do the reverse.
OverTheCapIsRefused == (amount > 100) => ~Allowed(amount)
UnderTheCapIsAllowed == (amount <= 100) => Allowed(amount)

=============================================================================
