"""The Python side of the boundary declared by BoundedRetryExtern.dfy.

Translating that file emits an EMPTY anchor_model.py placeholder alongside the generated code.
This is what replaces it.

Nothing here is verified. Dafny assumed

    ensures 1 <= cost <= maxCost

and cannot check Python, so that clause is a promise this file makes and the audit records as an
assumption. It is the only thing the proof asks of this file — and the only thing that, if broken
here, invalidates the budget guarantee proved on the other side.

Which is why `cost` is clamped below rather than trusted: the real cost comes from a token counter
that has its own failure modes, and the boundary is the place to enforce what the proof assumed.
"""

from typing import Tuple


class Model:
    """Named `Model` because BoundedRetryExtern.dfy says {:extern "Model"}; the method is
    `attempt` for the same reason. Change either and the generated call stops resolving."""

    @staticmethod
    def attempt(maxCost: int) -> Tuple[bool, int]:
        """Make one attempt against the model.

        Returns (ok, cost). The Dafny caller destructures this as two out-parameters.

        Replace the body with a real Strands invocation. What must not change is the clamp: the
        proof on the other side is only sound if `1 <= cost <= maxCost` actually holds.
        """
        ok, cost = _invoke(maxCost)

        # Enforce here what Dafny assumed. A model that reports zero cost would break termination;
        # one that reports more than maxCost would break the budget bound. Neither is hypothetical
        # — a miscounted or missing usage field gives you the first.
        return ok, max(1, min(int(cost), maxCost))


def _invoke(maxCost: int) -> Tuple[bool, int]:
    """Stand-in for the Strands call. Deterministic so the round-trip test is repeatable."""
    _invoke.calls = getattr(_invoke, "calls", 0) + 1
    return (_invoke.calls >= 3, min(2, maxCost))
