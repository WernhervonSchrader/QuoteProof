# Public-release readiness design

Status: local release-candidate design; no publication authorization.

## Scope and evidence classes

- `PROJECT_CONTRACT`: QuoteProof is a backend-only synthetic demonstration. Its
  deterministic controls own the gate; model output is advisory and cannot
  impersonate human acceptance.
- `PROJECT_CONTRACT`: the live OpenAI path is disabled by default and fails
  closed unless every request-time gate passes.
- `DEPLOYMENT_EVIDENCE`: repository checks and local artifacts are observations
  bound to one exact commit. They are not production, privacy, legal, or
  regulatory approval.
- `ASSUMPTION_OR_RISK`: license/IP, public author metadata, public refs, the RIF
  subset, product naming, runtime secrets, and deployment controls require
  explicit human decisions or evidence.
- `EXTERNAL_NORM`: no legal or regulatory conclusion is introduced by this
  change. Tool findings retain their own published definitions and limits.

Context Assurance and every other private project are outside scope.

## Trust boundaries

Actors are an anonymous synthetic-scenario caller, a holder of the disposable
demo access code, the API operator, OpenAI, and a human reviewer. Assets are the
runtime API key, demo access code, provider budget, synthetic quote payloads,
policy fixtures, and SHA-bound release evidence. QuoteProof has no tenant or
durable data store in this MVP.

The browser-to-API and API-to-OpenAI connections are separate trust boundaries.
CORS restricts supported browsers but is not authentication. The audit trail is
returned in the response only; it is neither persistent nor tamper-evident.

## Live-path approaches

1. **Disable the route for this release candidate (selected).** Prepared local
   scenarios remain usable. This is the smallest safe option while no approved
   distributed usage-control service exists.
2. Add an in-process limiter. Rejected because serverless instances do not
   share counters, so it cannot establish a deployment-wide quota or budget.
3. Integrate a persistent distributed rate/quota/budget service. Viable later,
   but it requires a provider, ownership, retention, availability, and cost
   decision that is not authorized here.

The application therefore exposes a replaceable usage-guard interface and uses
a deny-all implementation by default. An operator cannot enable live drafting
merely by adding an OpenAI key.

## Required request-time order

`configuration -> live enabled -> kill switch -> access -> distributed usage guard -> input validation -> OpenAI secret resolution -> bounded provider call -> safe response`

A transport-level body-size guard may reject an oversized request before this
sequence to avoid reading an abusive body. Every rejection before provider use
must prove zero OpenAI client construction and zero external I/O.

Provider construction uses an explicitly supplied secret, finite timeout,
bounded SDK retries, and bounded model output. Client-facing errors contain only
stable sanitized codes. Operational logs use only component, status, duration,
server-generated correlation ID, and sanitized error code.

## Acceptance matrix

| Requirement | Class | Objective acceptance |
| --- | --- | --- |
| Live route off by default | `PROJECT_CONTRACT` | Request returns a sanitized 503 before access, secret, client, or I/O |
| Kill switch | `PROJECT_CONTRACT` | Enabled switch returns 503 before downstream gates |
| Usage protection | `PROJECT_CONTRACT` | Missing/invalid guard fails closed; rate, quota, and budget denials return stable errors |
| Input bounds | `PROJECT_CONTRACT` | Unknown, malformed, oversized, invalid country/currency/date, and excessive item input fail before provider construction |
| Governance precedence | `PROJECT_CONTRACT` | `BLOCKED > REQUIRES_HUMAN_REVIEW > PASS`; report-integrity failure becomes `BLOCKED` |
| Human authority | `PROJECT_CONTRACT` | Model/advisory text cannot assert human approval or real compliance clearance |
| Telemetry boundary | `PROJECT_CONTRACT` | Canary secrets and quote text do not appear in logs, errors, or artifacts |
| Reproducibility | `DEPLOYMENT_EVIDENCE` | Frozen lock sync, wheel/sdist build, clean install, hashes, and SBOM succeed at exact SHA |
| Release gate | `DEPLOYMENT_EVIDENCE` | Format, lint, typing, tests, coverage, SAST, dependency audit, secret scan, and build all pass |
| Publication authorization | `ASSUMPTION_OR_RISK` | License/IP, author email, refs, RIF, name, privacy, and independent review decisions are recorded separately |

Unavailable, stale, non-reproducible, or SHA-mismatched mandatory evidence is
`FAIL` or `UNCLEAR`, never `PASS`. Green CI proves repository checks only.
