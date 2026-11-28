# Privacy and data flow

Status: technical boundary for a synthetic demonstration; not legal or privacy
approval.

## Data-flow modes

```text
Prepared scenario caller -> QuoteProof API -> packaged synthetic fixtures
                                      -> response to caller

Live caller -> QuoteProof API -> request-time access/usage/input gates
                            -> OpenAI (only if separately enabled and allowed)
                            -> sanitized response to caller
```

Hosting sits around the API and may produce platform telemetry. No browser
frontend source is included in this repository.

## Purpose and data categories

The only approved purpose is demonstrating quotation-control routing with
synthetic data. Prepared cases contain invented company/item information. The
optional live request accepts a quote ID, a free-text sales request, and a
default currency. If live processing is separately enabled, that content and
the structured quote/policy context needed for reasoning are transmitted to
OpenAI.

Do not enter customer, employee, supplier, personal, confidential, export-
controlled, regulated, credential, or production quotation data. A consuming
frontend must show the synthetic-only and OpenAI-transfer notice before any
free-text input; API users receive the same contract here and in the OpenAPI
description.

## Application logging

QuoteProof emits an allowlist only:

- component;
- status;
- duration in milliseconds;
- server-generated correlation ID;
- sanitized error code.

It does not intentionally log headers, access codes, API keys, request/response
bodies, quote/customer text, or provider exception text. Canary tests enforce
this repository contract. Hosting, reverse-proxy, OpenAI, and operator logging
are separate systems and are not evidenced by local tests.

## Storage, retention, deletion, and contact

QuoteProof has no database. The review/audit structure exists in the response
and process memory only; the application does not persist or delete a durable
record. Network clients, hosting, OpenAI, and operator tooling may have their own
retention and deletion controls. Their current configuration, region, terms,
retention, and deletion execution are `ASSUMPTION_OR_RISK` until an authorized
operator supplies deployment evidence and privacy acceptance.

Use the private contact boundary in [SECURITY.md](../SECURITY.md) for security
concerns without sending sensitive values. A public release or live deployment
requires a named privacy owner to approve purpose, lawful basis as applicable,
provider/hosting terms, regions, notices, retention, deletion, and contact.
