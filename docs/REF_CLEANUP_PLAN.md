# Remote ref cleanup plan

No remote ref has been changed. The repository owner accepted public visibility
of the existing reachable history and remote branches for this release and did
not authorize deletion or rewriting.

| Remote ref | Observed relation to `main` | Recommended publication treatment |
| --- | --- | --- |
| `main` | authoritative baseline | keep |
| `snapshot/hackathon-submission-v1.0` | identical to `main` at audit | accepted as an existing historical ref; name is not a release |
| `agent/fix-live-drafting` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `agent/jury-access-code` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `agent/openai-draft-adapter` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `agent/secure-openai-secret` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `agent/vercel-backend` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `feat/rif-reasoning-governance` | merged/divergent work ref | accepted as existing history within the owner's scoped RIF authorization |
| `fix/deterministic-net-total` | merged/divergent work ref | accepted as existing history; no deletion authorized |
| `benchmark-edition` | six unique commits, 681 added lines | accepted as a visible historical branch, but excluded from `v0.1.0` artifacts and `main` |

At the 27 August 2026 mirror scan, `benchmark-edition` added
`benchmarks/README.md`, `benchmarks/pilot-suite.json`,
`src/quoteproof/benchmark.py`, and `tests/test_benchmark.py`. Its unique commits
must not be silently merged or deleted.

Before visibility changes, create a new mirror, enumerate all refs again, rerun
both full-history scanners, recheck author emails and RIF/private-project
references, and bind the result to the final public ref set. No ref cleanup is
part of `v0.1.0`.
