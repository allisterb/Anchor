"""The transcript renderer, checked without a model.

    python tests/strands/transcript_render.py

A transcript exists so somebody can check the agent's prose against what the tools actually
returned. That only works if the rendering is faithful, so the properties worth pinning are the
ones that would let it lie:

    a tool call must appear with its arguments      -- otherwise the evidence is unattributable
    a tool result must appear in full, or say it was clipped
    an answer with NO tool calls must SAY SO        -- it reads exactly like a checked one

The last is the one that matters most. A model can produce a confident paragraph about a policy it
never looked at, and in a saved log that is indistinguishable from a verdict unless the absence is
stated.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent.transcript import header, render, result_text  # noqa: E402

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def messages(*blocks):
    return [{"role": "assistant", "content": list(blocks)}]


def main() -> int:
    md = render(messages(
        {"text": "Checking that now."},
        {"toolUse": {"name": "CheckPolicy", "toolUseId": "1",
                     "input": {"policy": "a.dw", "attempts": 3}}},
    ) + [{"role": "user", "content": [
        {"toolResult": {"toolUseId": "1", "status": "success",
                        "content": [{"text": "permit #1 VACUOUS"}]}}]}]
        + messages({"text": "It is vacuous."}),
        question="is it dead?", heading="Q1")

    check("the heading and question are carried", "## Q1" in md and "> is it dead?" in md)
    check("the tool is named", "`CheckPolicy`" in md, md[:200])
    check("its ARGUMENTS are shown", '"attempts": 3' in md or '"attempts":3' in md, md[:400])
    check("the tool's reply is included", "permit #1 VACUOUS" in md)
    check("both prose turns survive", "Checking that now." in md and "It is vacuous." in md)

    # A long result is clipped, and says so rather than ending mid-sentence in silence.
    long_md = render([{"role": "user", "content": [
        {"toolResult": {"toolUseId": "1", "content": [{"text": "x" * 500}]}}]}], limit=100)
    check("a long result is clipped", "x" * 100 in long_md and "x" * 200 not in long_md)
    check("and the clipping is disclosed", "clipped" in long_md, long_md[:200])

    # THE ONE THAT MATTERS. No tool calls means the answer rests on nothing.
    bare = render(messages({"text": "Looks fine to me."}), question="is it ok?")
    check("an answer with no tool calls is flagged as such",
          "No tools were called" in bare, bare)
    check("and a real one is not flagged", "No tools were called" not in md)

    # A result shape the renderer does not model is named, not dropped -- a transcript missing
    # part of what a tool returned misleads more quietly than one that admits the gap.
    odd = result_text({"content": [{"image": {"format": "png"}}]})
    check("an unmodelled result block is named rather than dropped", "image" in odd, odd)

    check("the header carries a timestamp and the file's purpose",
          "Generated" in header("T") and "evidence" in header("T"))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("transcripts render faithfully, absent tool calls included.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
