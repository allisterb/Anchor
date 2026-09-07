"""An informal Strands implementation of specs/SharedBudget.tla.

Informal deliberately: nothing here is generated from the spec and nothing checks that it matches.
It exists to find out what the modelled state machine looks like in real SDK code, and whether the
race TLC found is reachable in practice.

The mapping:

    TLA+                          Strands
    ----                          -------
    Agents                        several strands.Agent, invoked concurrently
    spent                         accumulated totalTokens across all of them
    reserved[a]                   tokens held for an agent whose call is in flight
    MaxCost                       the per-attempt token ceiling
    Attempt / Settle              agent.invoke_async(), then read metrics
    CanAfford                     spent + reserved + MaxCost <= Budget

Two things this exercise established.

First, the SDK confirms the load-bearing modelling assumption: cost is knowable only *after* the
call. It arrives on the result, so an implementation cannot check the actual cost before paying it.
That is exactly why the spec reserves the worst case up front rather than charging the real cost
afterwards — the reservation was not an artifact of the model.

Second, a trap. ``result.metrics.accumulated_usage`` is the running total for an agent across every
invocation, not the cost of the call just made. Charging it per call bills the first attempt again
on the second, the first two again on the third, and so on. The per-call figure is
``result.metrics.agent_invocations[-1].usage``. I wrote the wrong one first and only noticed because
the trace showed one agent settling 3000 and then 6000 for two identical calls.

Run it:  python tests/strands/shared_budget.py
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from strands import Agent
from strands.models import Model
from strands.types.content import Messages
from strands.types.event_loop import Usage
from strands.types.tools import ToolSpec

BUDGET = 10_000
MAX_COST = 3_000


# --------------------------------------------------------------------------------------------
# A model we can drive deterministically.
#
# Modelled on the SDK's own tests/fixtures/mocked_model_provider.py, written here rather than
# imported because that fixture is not part of the installed package. The event shapes below are
# the streaming protocol Model.stream is expected to yield; the trailing "metadata" event carries
# the usage the budget arithmetic reads.
# --------------------------------------------------------------------------------------------
class ScriptedModel(Model):
    """Returns a fixed reply, reporting a fixed token cost. No network, no credentials."""

    def __init__(self, cost: int, succeeds_on: int = 3) -> None:
        self.cost = cost
        self.succeeds_on = succeeds_on
        self.calls = 0

    def get_config(self) -> Any:
        return {}

    def update_config(self, **model_config: Any) -> None:
        pass

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs) -> AsyncGenerator[Any, None]:
        raise NotImplementedError

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        tool_choice: Any | None = None,
        *,
        system_prompt_content=None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        self.calls += 1
        done = self.calls >= self.succeeds_on

        # A real model call awaits on the network here; this is what lets the other agents run,
        # and therefore what makes the interleaving reachable at all.
        await asyncio.sleep(0.01)

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": "done" if done else "retry"}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}

        # Only here does the caller learn what the attempt cost.
        usage = Usage(inputTokens=self.cost // 2, outputTokens=self.cost // 2, totalTokens=self.cost)
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}


# --------------------------------------------------------------------------------------------
# The ledger: SharedBudget.tla's spent / reserved / CanAfford.
# --------------------------------------------------------------------------------------------
@dataclass
class Ledger:
    """Atomic acquire — the verified version.

    ``acquire`` is the spec's Acquire action: deciding there is room and taking it happen under one
    lock, so nothing can interleave between them.
    """

    budget: int
    max_cost: int
    spent: int = 0
    reserved: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> bool:
        async with self.lock:
            if self.spent + self.reserved + self.max_cost > self.budget:
                return False
            self.reserved += self.max_cost
            return True

    async def settle(self, cost: int) -> None:
        async with self.lock:
            self.reserved -= self.max_cost
            self.spent += cost

    @property
    def committed(self) -> int:
        return self.spent + self.reserved


@dataclass
class NaiveLedger(Ledger):
    """Bug3_CheckThenReserve.tla — what you write without having modelled it first.

    Check there is budget, make the call, charge what it cost. There is no reservation, so nothing
    accounts for calls that are already in flight: every agent checks against a budget that looks
    free precisely because the others have not been charged yet.

    Note what is *not* wrong here. The check is correctly locked. Each agent checks before it
    spends. No agent overspends on its own. The fault is only in the interleaving — which is why
    reviewing one agent's logic finds nothing, and why the model checker found it immediately.
    """

    async def acquire(self) -> bool:
        async with self.lock:
            return self.spent + self.max_cost <= self.budget

    async def settle(self, cost: int) -> None:
        async with self.lock:
            self.spent += cost


# --------------------------------------------------------------------------------------------
# The workflow: BoundedRetry, per agent, against a shared ledger.
# --------------------------------------------------------------------------------------------
async def run_agent(name: str, ledger: Ledger, cost: int, trace: list[str]) -> str:
    agent = Agent(model=ScriptedModel(cost=cost), system_prompt="You are a worker.", callback_handler=None)

    while await ledger.acquire():
        trace.append(f"{name} acquired (committed={ledger.committed})")
        result = await agent.invoke_async("do the task")

        # NOT accumulated_usage. That is the running total for this agent across every invocation,
        # so charging it per call bills the first attempt again on the second, the first two again
        # on the third, and so on — an overcharge that grows quadratically and looks plausible
        # until you check it. agent_invocations[-1].usage is the cost of the call just made.
        actual = result.metrics.agent_invocations[-1].usage["totalTokens"]

        await ledger.settle(actual)
        trace.append(f"{name} settled {actual} (spent={ledger.spent})")

        if "done" in str(result.message):
            return "done"

    return "abandoned"


async def run(ledger: Ledger, agents: int, cost: int) -> tuple[list[str], list[str]]:
    trace: list[str] = []
    outcomes = await asyncio.gather(
        *(run_agent(f"a{i + 1}", ledger, cost, trace) for i in range(agents))
    )
    return list(outcomes), trace


async def main() -> None:
    for label, factory in (("reserving ledger (SharedBudget.tla)", Ledger), ("naive ledger (Bug3)", NaiveLedger)):
        ledger = factory(budget=BUDGET, max_cost=MAX_COST)
        outcomes, trace = await run(ledger, agents=3, cost=MAX_COST)

        print(f"\n=== {label} ===")
        for line in trace:
            print(f"  {line}")
        print(f"  outcomes: {outcomes}")
        print(f"  committed at peak: spent={ledger.spent} reserved={ledger.reserved}")

        over = ledger.spent > BUDGET
        print(f"  budget {'VIOLATED' if over else 'respected'} ({ledger.spent} of {BUDGET})")

        # Assert rather than merely report, so running this file is a check and not a demo.
        if factory is Ledger:
            assert not over, f"reserving ledger overspent: {ledger.spent} of {BUDGET}"
        else:
            assert over, "the naive ledger did not race; the demonstration has stopped demonstrating"


if __name__ == "__main__":
    asyncio.run(main())
