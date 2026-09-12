"""Everything the agent depends on except the model, checked without spending anything.

    python tests/strands/agent_wiring.py

WHY THIS IS A SEPARATE HARNESS. A review needs a live model: credentials, a network call and a bill.
Everything underneath it does not, and that "everything" is where the mistakes actually live -- a
server that fails to launch, a tool that is not advertised, a knowledge article the agent cannot
reach, a path that escapes containment. Isolating the model means all of that is verifiable on every
run rather than on the runs someone is willing to pay for.

It launches the real `anchor` binary over stdio, which is the wiring an MCP host uses, and asks it
the questions the agent will ask.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent import anchor_server, find_cli  # noqa: E402

# The tools a review cannot proceed without, and the articles the system prompt sends the agent to.
REQUIRED_TOOLS = {"CheckPolicy", "DescribePolicyModule", "ListKnowledge", "ReadKnowledge"}
REQUIRED_ARTICLES = {"reading-verdicts", "event-schemas-and-pins", "the-modelled-subset",
                     "writing-a-property-module", "smoke-vs-exhaustive", "what-anchor-does-not-check"}

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    print(f"anchor CLI: {find_cli()}\n")

    client = anchor_server()
    with client:
        # --- the tools a review needs ------------------------------------------------------------
        tools = client.list_tools_sync()
        names = {t.tool_name for t in tools}
        print(f"tools advertised: {', '.join(sorted(names))}\n")
        for tool in sorted(REQUIRED_TOOLS):
            check(f"tool `{tool}` is advertised", tool in names)

        # --- the knowledge base, both ways it is offered -----------------------------------------
        listed = client.call_tool_sync("wiring-list", "ListKnowledge", {})
        listed_text = str(listed)
        for article in sorted(REQUIRED_ARTICLES):
            check(f"article `{article}` is listed", article in listed_text)

        resources = client.list_resources_sync()
        uris = {str(r.uri) for r in resources.resources}
        check("articles are also served as MCP resources",
              all(f"anchor://knowledge/{a}" in uris for a in REQUIRED_ARTICLES),
              f"saw {sorted(uris)}")

        # The one the system prompt leans on hardest: it is what stops a bounded verdict being
        # reported as a proof.
        verdicts = client.read_resource_sync("anchor://knowledge/reading-verdicts")
        verdicts_text = str(verdicts)
        for phrase in ("VACUOUS", "bound", "unpinned"):
            check(f"reading-verdicts carries `{phrase}`", phrase.lower() in verdicts_text.lower())

        # --- a real check, so the whole tool path is exercised ------------------------------------
        result = client.call_tool_sync("wiring-check", "CheckPolicy",
                                       {"policy": "tests/policies/dead_forbid.dw"})
        text = str(result)
        check("CheckPolicy reports the DEAD forbid", "DEAD" in text)
        check("CheckPolicy carries the unpinned caveat", "UNPINNED" in text.upper())

        # --- containment, which exists for exactly this caller ------------------------------------
        escaped = str(client.call_tool_sync("wiring-escape", "CheckPolicy",
                                            {"policy": "../../CLAUDE.md"}))
        check("a path escaping the project is refused",
              "outside this project" in escaped or "error" in escaped.lower(),
              escaped[:120])

        # --- a refusal is not a pass ---------------------------------------------------------------
        refused = str(client.call_tool_sync("wiring-refuse", "CheckPolicy",
                                            {"policy": "tests/policies/like_impossible.dw"}))
        check("a policy outside the subset is REFUSED, not empty", "REFUSED" in refused)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1

    print("the agent's MCP wiring is sound; only the model call is untested here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
