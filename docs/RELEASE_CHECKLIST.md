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

## Manual blockers

- [ ] license and IP rights, including QuoteProof fixtures/docs/code;
- [ ] explicit release scope for the RIF subset;
- [ ] public exposure or authorized rewrite of commit author email;
- [ ] keep/remove/archive decision for every remote branch and tag;
- [ ] product-name/confusion decision for QuoteProof;
- [ ] privacy and data-flow acceptance by a named owner;
- [ ] runtime secret rotation/revocation evidence if live use is later approved;
- [ ] deployed distributed usage guard and budget evidence if live use is later
  approved;
- [ ] branch protection evidence;
- [ ] independent reviewer `PASS` bound to the unchanged final SHA.

## Separately authorized actions

Do not push, change visibility, rewrite history, delete remote refs, rotate
secrets, create tags/releases, deploy, or run live OpenAI tests without explicit
authorization. Green repository checks do not authorize any of these actions.
