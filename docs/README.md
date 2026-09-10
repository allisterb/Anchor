# Documentation

| | |
|---|---|
| [`verifying-a-strands-graph.md`](verifying-a-strands-graph.md) | the procedure for taking a Strands `Graph` and establishing what it will and will not do |
| [`agent/`](agent) | internal working notes — handoffs, task writeups, and anything else produced while doing the work rather than describing it |
| [`agent/HANDOFF.md`](agent/HANDOFF.md) | current state of the work, and findings worth not re-deriving. **Start here** if you are picking the project up |

Documentation that belongs *beside* what it describes stays there, and this index points at it
rather than copying it:

| | |
|---|---|
| [`../specs/README.md`](../specs/README.md) | the models, why each exists, and the argument for TLA+ and Dafny doing different jobs |
| [`../specs/DependencyDAG/README.md`](../specs/DependencyDAG/README.md) | **a TLA+ primer for readers new to the language**, and the full account of translating a Strands graph |
| [`../specs/StrandsGraph/README.md`](../specs/StrandsGraph/README.md) | the executor as it actually runs, and where the two models disagree |
| [`../tests/strands/README.md`](../tests/strands/README.md) | what was established against the real SDK |
| [`../requirements/README.md`](../requirements/README.md) | the pinned, hash-locked Python dependencies |
| [`../reference/README.md`](../reference/README.md) | the ledger: what third-party material has been ingested, on what terms, and its scan verdict |

## Verifying a Strands graph

[`verifying-a-strands-graph.md`](verifying-a-strands-graph.md) covers the two models and why they
disagree, the three tiers of edge condition, how to read a counterexample, the catalogue of things
that actually go wrong, and what "verified" is allowed to mean afterwards.

Every claim in it is checked by the suite, and the ones that came from probing the running SDK
rather than reading its source are marked as such.

**It is about `Graph` specifically** — the one deterministic primitive of four. Anchor's coverage of
the rest of Strands, and the large parts it does not cover at all, are tabulated in the
[root README](../README.md#which-part-of-strands-this-applies-to).
