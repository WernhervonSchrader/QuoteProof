# QuoteProof

QuoteProof is a backend-only Python demonstration of governed quotation review.
It separates optional model-assisted drafting and advisory reasoning from the
deterministic controls that own the result.

The repository is an Apache-2.0-licensed technical release candidate. It is not
production-approved, legal or compliance advice, professionally certified, or
a deployment authorization. No React or TypeScript frontend is included here.
Any separately hosted frontend is an external component with its own source and
deployment evidence.

## Safe demonstration path

The three packaged scenarios are synthetic, deterministic, and make no OpenAI
request:

```text
POST /review/pass     -> PASS
POST /review/review   -> REQUIRES_HUMAN_REVIEW
POST /review/blocked  -> BLOCKED
```

`PASS` means only that the supplied synthetic quotation passed the configured
demo rules. The restricted-party, export, and quality data are fixtures. They
cannot provide sanctions clearance, export authorization, supplier evidence,
legal advice, certification, or human approval.

Every pipeline node emits an audit event into the API response. QuoteProof does
not persist that response, provide append-only storage, or make the audit trail
tamper-evident.

## Decision boundary

| Stage | Owner | Authority |
| --- | --- | --- |
| Structured draft | optional OpenAI model | proposal only |
| Evidence-linked reasoning brief | optional OpenAI model | advisory only |
| Schema and reasoning validation | deterministic Python | may add review/block findings |
| Commercial fixture controls | deterministic Python | sole gate authority |
| Human acceptance | authorized person outside QuoteProof | not represented by model output |

Gate priority is deterministic: `BLOCKED > REQUIRES_HUMAN_REVIEW > PASS`.
A report-integrity failure is conservatively converted to `BLOCKED`. Model text
cannot remove a finding, grant `PASS`, or impersonate a human decision.

## Live OpenAI path

`POST /draft-and-review` is disabled by default. Adding an API key does not
enable it. Request-time order is:

```text
configuration -> enabled -> kill switch -> access -> distributed usage guard
-> input validation -> OpenAI secret resolution -> bounded provider call
-> sanitized response
```

This release candidate provides a deny-all usage guard because no persistent,
distributed rate/quota/budget service has been selected. An in-memory limiter
would not protect a multi-instance serverless deployment. The route remains
fail-closed until an approved adapter and deployment evidence exist.

No regular test or CI job uses OpenAI credentials or makes a live provider
call. Live smoke tests are separately authorized operator work and are not a
release-readiness prerequisite.

## Install from the lockfile

Supported versions are CPython 3.11, 3.12, and 3.13. Install `uv` 0.12.6, then:

```bash
uv sync --frozen --dev
uv run pytest -q --cov=quoteproof --cov-branch --cov-report=term-missing
uv run uvicorn quoteproof.api:app --reload
```

Open `http://127.0.0.1:8000/docs`. To use a local HTTP browser origin, set the
explicit development profile and origin; production configuration rejects HTTP,
wildcards, credentials in origins, paths, queries, and fragments.

```bash
QUOTEPROOF_PROFILE=development \
QUOTEPROOF_ALLOWED_ORIGINS=http://127.0.0.1:3000 \
uv run uvicorn quoteproof.api:app --reload
```

Example deterministic requests:

```bash
curl -X POST http://127.0.0.1:8000/review/pass
curl -X POST http://127.0.0.1:8000/review/review
curl -X POST http://127.0.0.1:8000/review/blocked
```

Or review a synthetic structured payload:

```bash
curl -X POST http://127.0.0.1:8000/review \
  -H 'Content-Type: application/json' \
  --data-binary @src/quoteproof/data/demo_cases/pass.json
```

## Build and verification

The CI contract in `.github/workflows/release-ci.yml` runs on pull requests and
`main`. It checks lock consistency, formatting, lint, strict typing, tests,
branch coverage (minimum 85%), Bandit, dependency vulnerabilities, tracked
credential files, Detect-secrets, full-history Gitleaks, wheel/sdist build,
clean installation from locked dependencies, CycloneDX SBOM generation, and
SHA-256 hashes. Mandatory jobs have no `continue-on-error` path.

Repository checks are not production, security, privacy, legal, regulatory, or
organizational approval. See:

- [Security boundary](SECURITY.md)
- [Privacy and data flow](docs/PRIVACY_AND_DATA_FLOW.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Branch-protection recommendation](docs/BRANCH_PROTECTION.md)
- [Manual release decisions](docs/MANUAL_RELEASE_DECISIONS.md)
- [Remote-ref cleanup plan](docs/REF_CLEANUP_PLAN.md)
- [Release-readiness design](docs/RELEASE_READINESS_DESIGN.md)
- [RIF demonstration scope](docs/RIF_GOVERNANCE.md)

## Version and release status

`0.1.0` is the prepared initial open-source release version. The remote branch name
`snapshot/hackathon-submission-v1.0` is historical and is not a SemVer release,
tag, or proof that version 1.0 was published. See [CHANGELOG.md](CHANGELOG.md).

Publication remains conditional on the exact-SHA release gates. Existing history,
author email addresses, and remote branches are accepted for this release; no
history or ref cleanup is implied.

## License, RIF scope, and marks

QuoteProof is licensed under the [Apache License 2.0](LICENSE). The license covers
the materials contained in this repository, including its concrete
QuoteProof-specific RIF implementation and documentation. It does not license
the complete Reliable Intelligence Framework, Context Assurance, or any other
private project or material. See [NOTICE](NOTICE) and the
[RIF scope](docs/RIF_GOVERNANCE.md).

As stated in Apache License 2.0 section 6, the license does not grant trademark
rights in the names `QuoteProof` or `Reliable Intelligence Framework` or their
branding, except for customary attribution and origin descriptions.

## Human and AI contribution

QuoteProof was built during OpenAI Build Week with Codex assisting implementation,
testing, hardening, and documentation. GPT-5.6 is the configured optional runtime
model for structured drafting and an advisory reasoning brief. Human-owned
contracts remain: deterministic gates own the result; synthetic compliance data
must be labeled; models cannot approve their own work; and publication requires
separate human authorization.
