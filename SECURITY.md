# Security policy

QuoteProof is a local release candidate, not a production service. Security
reports should use GitHub's private **Report a vulnerability** / Security
Advisory channel when it is available. Otherwise contact the repository owner
through GitHub first and request a private channel. Do not put keys, tokens,
customer data, exploit payloads, or other sensitive material in an issue, pull
request, discussion, screenshot, log, or chat message.

## Supported state

Only the current `main` candidate and the exact SHA named by a release-evidence
report are eligible for review. There is no published supported release or
response-time commitment.

## Runtime boundary

- Prepared scenarios are synthetic and require no external provider.
- Live drafting is disabled by default with
  `QUOTEPROOF_LIVE_DRAFT_ENABLED=false`.
- The kill switch defaults to
  `QUOTEPROOF_LIVE_DRAFT_KILL_SWITCH=true`.
- Enabling flags and adding a key are insufficient: a persistent distributed
  usage guard must also allow the request.
- Provider secret resolution occurs only after configuration, enabled/kill,
  access, usage, and input-validation gates pass.
- Provider timeout, retry count, and output size are explicitly bounded.
- Client responses and operational logs use sanitized codes and allowlisted
  metadata only.

The disposable access code is not an OpenAI credential and is not a complete
budget control. CORS is not authentication. No in-process counter is represented
as deployment-wide protection.

## Secret handling

Never submit an OpenAI key through a browser form or commit it to this
repository. Runtime secrets belong in an operator-controlled secret store and
must never use a browser-exposed prefix. Rotation must be performed and verified
by an authorized operator immediately before any separately approved live
deployment; this repository does not contain or prove that rotation.

No regular CI job resolves `OPENAI_API_KEY`, and no regular test performs live
OpenAI I/O.

## Historical evidence and current limits

`DEPLOYMENT_EVIDENCE`: a GitHub Actions workflow run on 18 July 2026 confirmed
that a protected `OPENAI_API_KEY` existed at that time. That observation does
not prove the current secret inventory, current validity, scope, revocation
state, ownership, or Vercel runtime configuration. The verification workflow is
not part of the release-candidate tree.

For a later expressly authorized live smoke test, an authorized operator must
provide the runtime key through the approved deployment secret mechanism or test
the already configured deployment environment. A live test is not required for
this release-readiness work and cannot by itself authorize production use.

## Disclosure boundaries

The project cannot promise confidentiality through public GitHub channels.
After receiving a sanitized report, the maintainer should establish a private
channel, reproduce without real data, assign severity and scope, prepare a fix,
rerun all SHA-bound gates, and disclose only after an explicit decision.
