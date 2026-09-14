---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

VARIABLE dummy
Init == dummy = 0
Next == UNCHANGED dummy
Spec == Init /\ [][Next]_dummy
=============================================================================
