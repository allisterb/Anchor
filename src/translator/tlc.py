"""Finding the TLA+ tools jar, and running TLC with the flags that stop it eating itself.

The jar version lives in exactly one place -- `tlatools_version` in `build.sh`, next to the sha256
checked on every run. Harnesses used to spell `tla2tools-1.7.4.jar` themselves, so bumping that pin
would have left six of them looking for a jar that no longer existed: a `FileNotFoundError` naming
a path, locally and in CI at once, with nothing pointing at the version bump that caused it.
Resolved by glob instead, so whatever the build installed is what runs.

Resolved WHEN TLC IS RUN, not at import: `dw_to_tla.py` translates without ever starting a JVM
(`--check` is a text comparison), so it has to keep working in a tree with no jar yet.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "lib"


@lru_cache(maxsize=1)
def find_jar() -> Path:
    """The tla2tools jar the build installed.

    Raises rather than returning a path that does not exist: the alternative is java reporting
    `Could not find or load main class tlc2.TLC`, which describes neither the problem nor the fix.
    """
    jars = sorted(LIB.glob("tla2tools-*.jar"))
    if not jars:
        raise SystemExit(
            f"no tla2tools jar in {LIB.relative_to(REPO)}/\n"
            "It is downloaded and sha256-checked by the build, not committed. Run:\n"
            "    ./build.sh        (or ./build.ps1 on Windows)")

    # Newest last, so a lib/ holding two after a bump uses the later one. The build installs only
    # ever one, so this is a tie-break that should not come up.
    return jars[-1]


def run_tlc(module: str, cwd: Path, scratch: Path | None = None,
            extra: list[str] | None = None) -> tuple[bool, str]:
    """Run TLC on `module` in `cwd`, returning (it passed, everything it printed).

    `extra` goes in front of `-config`, which is where TLC wants mode flags such as
    `-simulate num=N`. Passed through rather than enumerated here: this module knows how to start a
    JVM safely, not what any particular check is asking.

    THE `-Djava.io.tmpdir` IS NOT OPTIONAL, and it is why this function exists. TLC unpacks the
    standard modules into java's temp directory; runs sharing one leave a half-written
    `Naturals.tla` behind, and SANY reports that as a NullPointerException plus a "Module-Table
    lookup failure" naming whichever *unrelated* spec lost the race. About one run in four, and the
    error points at a perfectly good file.

    `TLCProcess.cs` carried the fix for the C# runner while all five Python harnesses spawned TLC
    without it, which is what a copy-pasted command line costs: xunit runs tests in parallel, so
    two harnesses racing was the ordinary case rather than bad luck. One shared entry point makes
    that impossible to get wrong again.
    """
    with (tempfile.TemporaryDirectory(prefix="anchor-tlc-") if scratch is None
          else nullcontext(str(scratch))) as tmp:
        proc = subprocess.run(
            ["java", f"-Djava.io.tmpdir={tmp}",
             "-cp", str(find_jar()), "tlc2.TLC", "-cleanup",
             "-metadir", str(Path(tmp) / "states"),
             *(extra or []),
             "-config", f"{module}.cfg", f"{module}.tla"],
            cwd=cwd, capture_output=True, text=True)
        return proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------- reading a trace back
#
# TLC prints a counterexample as a sequence of states in TLA+ value syntax. `witness()` in the
# checker reduces one to a single line for a person to read; this reads the whole thing back into
# Python, for the two readers a sentence does not serve:
#
#   a person who knows TLA+   and wants the actual states, not a paraphrase of them
#   an AGENT                  which has to act on the trace -- and cannot act on English
#
# The second is the one that makes this worth a parser rather than a regex. A repair loop reads
# the witness, changes the policy, and re-checks; that loop needs the input values that reached
# the bad decision, and "ApproveSale -> SellShares" does not carry them.

# TLA+ values, as TLC prints them. A small grammar and all of it is here:
#
#   record    [ name |-> value, ... ]        -- also how Anchor tags scalars
#   sequence  << value, ... >>               -- and << >> for empty
#   set       { value, ... }
#   string    "..."          number  123     boolean  TRUE / FALSE
#
# Deliberately NOT a general TLA+ parser. It reads what TLC emits for THIS spec's state, and
# anything else raises rather than guessing -- a trace that silently parsed wrong would be worse
# than no trace at all, because it would be acted on.
class TLAParseError(ValueError):
    """TLC printed something this reader does not model. Never swallowed: see the note above."""


def _skip(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def parse_tla_value(s: str, i: int = 0):
    """One TLA+ value from `s` at `i`. Returns (value, index just past it)."""
    i = _skip(s, i)
    if i >= len(s):
        raise TLAParseError("ran out of input")

    if s.startswith("<<", i):                                     # sequence
        i = _skip(s, i + 2)
        out = []
        if s.startswith(">>", i):
            return out, i + 2
        while True:
            v, i = parse_tla_value(s, i)
            out.append(v)
            i = _skip(s, i)
            if s.startswith(",", i):
                i = _skip(s, i + 1)
                continue
            if s.startswith(">>", i):
                return out, i + 2
            raise TLAParseError(f"expected , or >> at {i}: {s[i:i + 30]!r}")

    if s[i] == "[":                                               # record
        i = _skip(s, i + 1)
        rec = {}
        if s.startswith("]", i):
            return rec, i + 1
        while True:
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] in "_"):
                j += 1
            if j == i:
                raise TLAParseError(f"expected a field name at {i}: {s[i:i + 30]!r}")
            name = s[i:j]
            j = _skip(s, j)
            if not s.startswith("|->", j):
                raise TLAParseError(f"expected |-> after {name!r} at {j}")
            v, i = parse_tla_value(s, j + 3)
            rec[name] = v
            i = _skip(s, i)
            if s.startswith(",", i):
                i = _skip(s, i + 1)
                continue
            if s.startswith("]", i):
                return rec, i + 1
            raise TLAParseError(f"expected , or ] at {i}: {s[i:i + 30]!r}")

    if s[i] == "{":                                               # set
        i = _skip(s, i + 1)
        out = []
        if s.startswith("}", i):
            return out, i + 1
        while True:
            v, i = parse_tla_value(s, i)
            out.append(v)
            i = _skip(s, i)
            if s.startswith(",", i):
                i = _skip(s, i + 1)
                continue
            if s.startswith("}", i):
                return out, i + 1
            raise TLAParseError(f"expected , or }} at {i}: {s[i:i + 30]!r}")

    if s[i] == '"':                                               # string
        j = i + 1
        buf = []
        while j < len(s):
            if s[j] == "\\" and j + 1 < len(s):
                buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(s[j + 1], s[j + 1]))
                j += 2
                continue
            if s[j] == '"':
                return "".join(buf), j + 1
            buf.append(s[j])
            j += 1
        raise TLAParseError("unterminated string")

    if s.startswith("TRUE", i):
        return True, i + 4
    if s.startswith("FALSE", i):
        return False, i + 5

    j = i + 1 if s[i] == "-" else i                                # number
    while j < len(s) and s[j].isdigit():
        j += 1
    if j > i and s[i:j] not in ("-", ""):
        return int(s[i:j]), j

    raise TLAParseError(f"unrecognised value at {i}: {s[i:i + 30]!r}")


# The generated module tags every scalar with its kind so TLC refuses a cross-kind comparison --
# `[k |-> "n", v |-> 1]` rather than `1`. That tagging is for the model checker's benefit and is
# noise to every reader here, so it is undone on the way out. The kind is not discarded silently:
# an address stays a list of four octets, which is visibly not a number.
_TAGGED = {"k", "v"}


def untag(value):
    """Strip Anchor's scalar tags from a parsed value, recursively."""
    if isinstance(value, dict):
        if set(value) == _TAGGED and isinstance(value.get("k"), str):
            return untag(value["v"])
        return {k: untag(v) for k, v in value.items()}
    if isinstance(value, list):
        return [untag(v) for v in value]
    return value


def trace_states(out: str) -> list[dict]:
    """Every state of TLC's counterexample, as dicts of variable name to value.

    Returns [] when the output carries no counterexample -- which is not an error: a run that
    completed without violating its invariant has no trace to show, and that is the answer.
    """
    states = []
    for block in re.split(r"^[ \t]*State \d+: ", out, flags=re.MULTILINE)[1:]:
        # A state block runs to the first blank line; what follows is the next state or TLC's
        # summary. Conjuncts are `/\ name = value`, one per (possibly wrapped) line.
        body = re.split(r"\n[ \t]*\n", block, maxsplit=1)[0]
        state = {}
        for chunk in re.split(r"^[ \t]*/\\ ", body, flags=re.MULTILINE)[1:]:
            name, _, rest = chunk.partition("=")
            try:
                value, _ = parse_tla_value(rest)
            except TLAParseError:
                # One unreadable variable must not cost the whole trace. Recorded as raw text so
                # it is visibly unparsed rather than missing.
                value = {"unparsed": rest.strip()}
            state[name.strip()] = untag(value)
        if state:
            states.append(state)
    return states


def witness_events(out: str) -> list[dict]:
    """The counterexample's session: the events of the final state's `trace`, in order.

    This is the sequence that reached the decision being reported -- the answer to "show me what
    actually happened", for a reader who wants more than the one-line summary.
    """
    states = trace_states(out)
    if not states:
        return []
    events = states[-1].get("trace") or []
    if not isinstance(events, list):
        return []

    # TLC prints an EMPTY FUNCTION as `<< >>`, which is indistinguishable from an empty sequence
    # at this level and parses as []. `output` and `pins` are always functions in this spec, so an
    # empty one is normalised to {} -- otherwise a consumer sees a list on the events that have no
    # output and an object on the ones that do, and has to handle both for no reason.
    for event in events:
        if isinstance(event, dict):
            for field in ("output", "input", "pins"):
                if event.get(field) == []:
                    event[field] = {}
    return events
