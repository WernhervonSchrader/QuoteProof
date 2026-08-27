# Remote ref cleanup plan

No remote ref has been changed. This plan requires a separate explicit decision
and authorization after independent review.

| Remote ref | Observed relation to `main` | Recommended publication treatment |
| --- | --- | --- |
| `main` | authoritative baseline | keep |
| `snapshot/hackathon-submission-v1.0` | identical to `main` at audit | remove or archive; name is not a release |
| `agent/fix-live-drafting` | merged/divergent work ref | remove after confirming no unique approved material |
| `agent/jury-access-code` | merged/divergent work ref | remove after confirming no unique approved material |
| `agent/openai-draft-adapter` | merged/divergent work ref | remove after confirming no unique approved material |
| `agent/secure-openai-secret` | merged/divergent work ref | remove after confirming no unique approved material |
| `agent/vercel-backend` | merged/divergent work ref | remove after confirming no unique approved material |
| `feat/rif-reasoning-governance` | merged/divergent work ref | remove unless RIF/IP owner explicitly approves it |
| `fix/deterministic-net-total` | merged/divergent work ref | remove after confirming no unique approved material |
| `benchmark-edition` | six unique commits, 681 added lines | keep private or separate; do not publish without methodology, data, cost, privacy, and IP review |

At the 27 August 2026 mirror scan, `benchmark-edition` added
`benchmarks/README.md`, `benchmarks/pilot-suite.json`,
`src/quoteproof/benchmark.py`, and `tests/test_benchmark.py`. Its unique commits
must not be silently merged or deleted.

After the maintainer decides each row, an authorized operator may perform the
approved remote changes. Then create a new mirror, enumerate all refs again,
rerun both full-history scanners, recheck author emails and RIF/private-project
references, and bind the result to the final public ref set.
