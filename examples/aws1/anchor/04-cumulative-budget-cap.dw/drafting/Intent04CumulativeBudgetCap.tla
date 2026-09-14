---------------------------- MODULE Intent04CumulativeBudgetCap ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

Amounts == {20000, 35000, 40000, 70000}
Gaps    == {10, 400}

TradeReq(a, t) == Ev("rebalance_portfolio", "request", [amount |-> Num(a)], NoFields, t)
TradeResp(a, t) == Ev("rebalance_portfolio", "response", [amount |-> Num(a)], NoFields, t)
ProfileResp(t) == Ev("get_client_profile", "response", NoFields, NoFields, t)
PortfolioResp(t) == Ev("load_portfolio", "response", NoFields, NoFields, t)

Session(a1, a2, gap) == <<
  ProfileResp(1),
  PortfolioResp(10),
  TradeReq(a1, 20),
  TradeResp(a1, 21),
  PortfolioResp(30),
  TradeReq(a2, 30 + gap)
>>

TradeAllowed(a1, a2, gap) == D!Decide(Session(a1, a2, gap), Policies, 6, AllValues)

VARIABLES a1, a2, gap
Init == /\ a1 \in Amounts
        /\ a2 \in Amounts
        /\ gap \in Gaps
Next == UNCHANGED <<a1, a2, gap>>
Spec == Init /\ [][Next]_<<a1, a2, gap>>

NoExceedBudgetCap == (a1 + a2 > 60000) => ~TradeAllowed(a1, a2, gap)

=============================================================================
