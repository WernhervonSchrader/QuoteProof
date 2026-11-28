# Threat model

Status: repository threat model for the local release candidate.

## Assets, actors, and boundaries

Assets are provider budget, runtime secrets, the disposable access code,
synthetic request data, deterministic policy fixtures, gate integrity, and
SHA-bound release evidence. Actors are an anonymous scenario caller, an access-
code holder, an abusive client, the API operator, OpenAI, hosting providers,
contributors, and an independent human reviewer.

Trust boundaries are caller-to-API, API-to-OpenAI, repository-to-CI, and
operator-to-hosting/secret store. The MVP has no user identity, tenancy, or
durable database.

## Principal threats and controls

| Threat | Control | Residual risk / release rule |
| --- | --- | --- |
| Provider-cost abuse | Live disabled, kill switch, access gate, deny-all distributed usage interface | No approved adapter exists; live stays disabled |
| Oversized or ambiguous input | Body, string, identifier, item, Decimal, currency, country, date, and unknown-field bounds | Hosting must also enforce transport limits |
| Secret exposure | Late provider-secret resolution, no regular CI secrets, allowlisted logs, two secret scanners | Runtime store/rotation remain operator evidence |
| Provider failure/data leak | Finite timeout/retries/output, sanitized errors, no exception detail logging | Provider/hosting telemetry is not locally evidenced |
| Model grants approval | Advisory schema, deterministic validation, prohibited authority claims, fixed gate priority | Human acceptance occurs outside the model |
| Simulated compliance appears real | Response disclaimer and fixture labels | UI must display notice before input |
| Report contradicts gate | Deterministic rendering and blocking integrity check | Response audit is not persistent or tamper-evident |
| Unsafe browser origin | Production HTTPS origin validation, explicit development profile | CORS is not authentication |
| Dependency/build compromise | Lockfile, frozen sync, audits, locked build backend, SBOM and hashes | Registry/action provenance and signing remain residual risks |
| History/ref disclosure | Full-ref scan and cleanup plan only | Author email, branches, RIF/IP, name require decisions |

## Abuse-case acceptance tests

Tests must prove zero provider-client construction and zero external I/O for a
disabled route, kill switch, invalid access, rate/quota/budget denial, invalid
or oversized input, and missing provider secret. Provider timeouts must return a
stable sanitized code. Logs and errors must not contain canary request or
credential values. Missing gate state or report integrity must become blocking.

## Exclusions

This model does not establish hosting hardening, WAF behavior, DDoS resistance,
regional processing, secret rotation, incident response staffing, production
monitoring, legal compliance, or Context Assurance. Those require separate
deployment and organizational evidence.
