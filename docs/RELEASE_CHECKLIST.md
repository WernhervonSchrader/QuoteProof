# Public-release checklist

Every item is evaluated against the exact candidate SHA. Missing, stale, or
non-reproducible evidence is `FAIL` or `UNCLEAR`, never `PASS`.

## Automated repository gates

- [ ] clean frozen sync for Python 3.11, 3.12, and 3.13;
- [ ] Ruff format/lint and Mypy strict;
- [ ] deterministic tests and at least 85% branch coverage;
- [ ] Bandit, dependency audit, tracked-credential check, Detect-secrets, and
  full-history Gitleaks;
- [ ] wheel and sdist from the locked build backend;
- [ ] clean install from artifact plus hashed runtime lock;
- [ ] validated reproducible CycloneDX SBOM and SHA-256 artifact hashes;
- [ ] final full-ref/history scan with counts, authors, RIF/Context Assurance
  references, findings, false positives, and `benchmark-edition` diff;
- [ ] evidence report records full SHA, worktree, tool versions, commands,
  results, artifacts, hashes, risks, and decisions.

## Owner decisions and operational blockers

- [x] Apache-2.0 license and IP authorization for contained QuoteProof
  fixtures/docs/code;
- [x] release scope limited to the concrete QuoteProof RIF subset;
- [x] public exposure of historical commit author email accepted; no rewrite;
- [x] existing remote branches and reachable history accepted; no ref deletion;
- [x] QuoteProof retained for this release without a trademark grant;
- [x] synthetic-only, no-deployment privacy/data-flow boundary accepted by the
  repository owner;
- [x] runtime secret rotation/revocation evidence is not applicable because
  live use and deployment are outside this release;
- [x] a distributed usage guard and budget are not applicable because live use
  and deployment are outside this release;
- [ ] branch protection evidence;
- [ ] required GitHub Actions checks pass against the unchanged release head.

## Separately authorized actions

The owner authorized the gate-bound push, pull request, merge, `v0.1.0` tag and
release, and final visibility change on 27 August 2026. History rewriting,
remote-ref deletion, deployment, secret operations, and live OpenAI tests remain
unauthorized. A green check for one SHA does not authorize acting on another.
