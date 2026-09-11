"""Where the harnesses find the TLA+ tools jar.

The version lives in exactly one place -- `tlatools_version` in `build.sh`, next to the sha256 that
is checked on every run. Four harnesses used to spell `tla2tools-1.7.4.jar` themselves, so bumping
that pin would have left them looking for a jar that no longer existed. The failure would have been
a `FileNotFoundError` naming a path, in six harnesses at once, locally and in CI, with nothing
pointing at the version bump that caused it.

Resolved by glob instead, so whatever `build.sh` installed is what gets used.

Resolved WHEN TLC IS RUN, not at import. `dw_to_tla.py` imports from `dogwood_differential` for the
translator and never starts a JVM -- `--check` is a text comparison -- so it must keep working in a
tree that has no jar yet.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "lib"


@lru_cache(maxsize=1)
def find_jar() -> Path:
    """The tla2tools jar `build.sh` installed.

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
