# Dependency pins

One directory per toolchain. Both follow the same rule, which is the one that matters: **pin exact
versions, verify them by hash, and fail rather than silently re-resolve.**

| | |
|---|---|
| [`strands/`](strands) | Python. `requirements.in` → compiled lock with hashes → installed by hand. Has [its own README](strands/README.md) for the procedure. |
| `dogwood/` | `Cargo.lock` for the Dogwood policy language, kept here rather than in the tree it describes. |
| [`dotnet/`](dotnet) | NuGet. `Packages.props` — every package version in the repository, in one file. |

Nothing in the build or in any agent installs the **Python or Rust** pins. They are run by a person,
deliberately.

**`dotnet/` is the exception, and the difference matters.** Restore is part of every build, so these
versions are consumed automatically rather than by hand. That is not a relaxation: the enforcement
is stronger here than in either of the others, because it is the build itself that fails.

## Why the .NET versions live here but the lock files do not

`requirements/dotnet/Packages.props` holds the versions. The **hashes** live in a
`packages.lock.json` beside each `.csproj`, and they have to: NuGet writes one per project and finds
it by convention, so there is nowhere else to put them. The split is not arbitrary —

| | what it pins | where |
|---|---|---|
| `Packages.props` | which version is **asked for** | here, with the other toolchains |
| `packages.lock.json` | that what **arrives** is what arrived last time, by `contentHash` | beside each project |

**`dotnet restore` does not recompute a lock; it updates one.** That distinction cost 47 entries to
discover. The committed locks were carrying packages that .NET 10 now PRUNES as framework-provided
(`Microsoft.NETCore.Platforms`, `System.Collections`, `System.Memory` and the rest of the
netstandard shim graph) — pinned in the file, never restored in practice. `dotnet restore
--force-evaluate` recomputes from the project files and drops them, and locked-mode restore then
still passes, which is what says the smaller graph is the real one.

So: after changing target frameworks, the SDK, or anything about how the graph is built, run

```bash
dotnet restore Anchor.sln --force-evaluate
```

and review the diff. An ordinary restore will happily leave a lock describing a graph that no longer
exists.

Changing a version here is expected to change a lock file. That diff is the thing to review.

A `Directory.Packages.props` still sits at the repository root, because NuGet discovers central
package management by walking up from each project and will not look anywhere else. It is a shim:
three lines importing this directory's file. See its comment for why a shim rather than the
`DirectoryPackagesPropsPath` override, which works for restore but not for the tools that write
versions.

What it enforces, each verified by trying it:

| | |
|---|---|
| a project that re-declares a version | **NU1008** |
| a package with no version here | **NU1010** |
| a package whose bytes differ from the lock | **NU1403**, on every restore |
| the dependency graph changing under CI | **NU1004** |

## Why the Cargo.lock lives here

`reference/` is gitignored, so a lockfile generated in place would evaporate on a fresh clone and
would pin nobody else's build. Keeping the copy here is the same move `build.sh` makes for z3 and
tla2tools: the version and hash live in a **tracked** file, while the artifacts they describe do
not.

Build against it with `--locked`, so a resolution drift fails instead of proceeding:

```bash
cargo build --locked          # or --frozen, which adds --offline
```

## What the Rust lock actually pins

Cargo's lockfile is a hash lock, and unlike pip's the verification is **always on** — there is no
`--require-hashes` equivalent to forget:

```toml
name = "serde"
version = "1.0.228"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9a8e94ea7f378bd32cbbd37198a4a91436180c5bb472411e48b5ec2e2124ae9e"
```

For Dogwood that is **271 packages, 268 from crates.io, every one checksummed, none from git** — so
a later build gets byte-identical crates or fails.

## Audit status

`cargo audit` against this lock, and an independent OSV query at the same pinned versions, agree:

```
Crate:     smartstring
Version:   1.0.1
Warning:   unmaintained
ID:        RUSTSEC-2026-0249      (published 2026-05-03)

warning: 1 allowed warning found
```

**No vulnerabilities.** The one hit is RustSec's *informational* `unmaintained` category — no CVE, no
severity, no fix — on a crate pulled in by `rhai`, the scripting engine Dogwood uses for information
providers. Its suggested replacements are `compact_str` and `smol_str`, and Dogwood already depends
on `smol_str` directly, so a future rhai migration costs nothing here.

Two things that scan cannot tell you, worth remembering when re-reading this:

- **It only finds what has been reported.** A supply-chain compromise is normally discovered after
  the fact, and the database is silent until then. What protects a build here is the pinning itself,
  not the audit.
- **It ages.** Re-run it rather than treating this section as a clearance; the advisory above was
  three weeks old when it was recorded.
