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


def run_tlc(module: str, cwd: Path, scratch: Path | None = None) -> tuple[bool, str]:
    """Run TLC on `module` in `cwd`, returning (it passed, everything it printed).

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
             "-config", f"{module}.cfg", f"{module}.tla"],
            cwd=cwd, capture_output=True, text=True)
        return proc.returncode == 0, proc.stdout + proc.stderr
