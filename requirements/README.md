# Python dependencies

Anchor's Dafny workflows are translated to Python against the Strands SDK, which lives in a venv at
`python/` — separate from the .NET build, and installed by hand rather than by the build scripts.

Everything here exists so that an install either reproduces exactly the artifacts that were
reviewed, or fails outright.

| | |
|---|---|
| `requirements.in` | what we actually want. **Edit this.** |
| `requirements.txt` | the compiled lock: every package, transitive ones included, pinned exactly and carrying the sha256 of each acceptable artifact. **Generated — never hand-edited.** |
| `pip.ini` | pip settings, copied into the venv root on every install |
| `check_python.py` | refuses a venv older than the lock was resolved for |
| `install.cmd` / `install.sh` | the installers. Run by a person, deliberately — nothing in the build or any agent invokes them |

These live here rather than in `python/`, because the venv carries a venv-generated `.gitignore`
containing `*`: anything placed inside it is invisible to git.

## First-time setup

```bash
py -3.13 -m venv python
```

Then install `uv`, which compiles the lock. This is the one unpinned install, and it is deliberate:
the tool that generates hashes cannot itself be hash-pinned until it has run once. That is also why
`require-hashes` is set on the install *command* rather than in `pip.ini` — putting it in the config
would quietly exempt this step instead of making it visible.

```bash
python/Scripts/pip install uv
```

## Compiling the lock

```bash
python/Scripts/uv.exe pip compile requirements/requirements.in --universal --python-version 3.13 --generate-hashes -o requirements/requirements.txt
```

`--universal` keeps the environment markers, so the lock installs on Linux and macOS too; without
it, the lock only works on the platform it was compiled on. `--python-version 3.13` records the
floor in the header — which is where `check_python.py` reads it from, so the version is stated once
rather than duplicated into a script that could drift from it.

## Installing

```bash
requirements\install.cmd
```

```bash
./requirements/install.sh
```

Both check the venv exists, check the lock exists, check the interpreter is new enough, copy
`pip.ini` into the venv, and then install with `--require-hashes --only-binary=:all:`.

The `pip.ini` copy happens on **every** install, not once by hand, because `python -m venv` rewrites
that directory on every rebuild — a copy made once is silently destroyed by the next rebuild, taking
the wheels-only and single-index defaults with it. Both flags are also passed explicitly on the
command line even though the copied config sets `only-binary`, because the copy is one `del` away
from being gone.

## What the settings buy

- **`--require-hashes`** — every package, transitive ones included, must match a recorded digest.
  pip demands that everything is pinned with `==` and that nothing unlisted can be pulled in. If any
  artifact fails, pip installs **nothing**; it does not partially apply.
- **`--only-binary=:all:`** — no source distributions. An sdist runs its `setup.py` during
  installation, which is arbitrary code execution on this machine before anything has been reviewed.
  A package shipping no wheel fails loudly instead of building.
- **one index, named explicitly** — dependency confusion needs two sources pip might resolve across.
  Never add `extra-index-url`.
- **`require-virtualenv`** — never installs into the system interpreter by accident.

## Upgrading

Change the version in `requirements.in`, recompile, and **read the diff** before installing. That
review is the step the whole arrangement exists to make possible: anything appearing under a `# via`
you did not expect deserves attention, and a package arriving that you thought you had excluded is
exactly what the diff is for.

Expect churn. `strands-agents` depends on `boto3` and `botocore`, which publish most weekdays, so
they will dominate every recompile. That is the cost of pinning, not a sign of a problem.

## What this does not do

Hash pinning is **trust on first use**. The hashes record what the index served at the first
compile; they do not independently establish that those artifacts are what their authors intended.
What they give you is immutability from then on — no silent substitution, no dependency-confusion
swap, no upgrade nobody reviewed.

So the review that matters is the first compile and each upgrade diff. After that the guarantee is
mechanical. `requirements.in` names each dependency alongside its project page for exactly this
reason: the name is checked against the real repository before the first install, because a wrong
name is a live typosquat risk that no amount of hashing detects.
