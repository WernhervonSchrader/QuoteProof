# Changelog

This project follows SemVer-compatible package versioning. A release does not
imply production, legal, compliance, or professional-advice suitability.

## Unreleased

### Added

- Tenant profiles (TOML) for every customer-specific rule, with rule
  provenance; placeholder rules route to human review. Selected with
  `QUOTEPROOF_TENANT_PROFILE`; customer profiles can live outside the
  repository via `QUOTEPROOF_TENANT_PROFILE_DIR`.
- Read-only ERP layer: generic SQL adapter for any DB-API 2.0 database,
  JSON export adapter, adapter registry, and a new `erp_lookup` pipeline node.
  An unavailable or ambiguous ERP fails closed to human review.
- Deterministic controls for ERP price floor, list-price deviation, blocked
  customers and items, credit hold, ERP export flag and currency mismatch.
- Outbound check of the customer-facing document for internal pricing
  language, internal cost figures and other customers' names.
- Revision control ("margin moved"), revision numbering, and approvals bound
  to a `decision_basis_hash` that lapses on any material change.
- Restricted-party screening that ignores legal forms and punctuation, with
  close matches routed to review.
- `GET /profile`, `POST /review/revision` and `python -m quoteproof.check_profile`.

## 0.1.0 - 2026-08-27

### Added

- Frozen `uv.lock` for CPython 3.11-3.13 and locked build tooling.
- Pull-request and `main` CI for quality, security, dependency, secret, build,
  clean-install, SBOM, and artifact-hash gates.
- Strict request schemas, body/item/string bounds, safe CORS validation,
  allowlisted logging, kill switch, and a replaceable distributed usage guard.
- Privacy/data-flow, threat-model, contribution, release, and branch-protection
  documentation.
- Apache License 2.0, copyright attribution, scoped RIF notice, and trademark
  boundary.

### Changed

- Live OpenAI drafting is disabled and fail-closed by default.
- OpenAI client creation and secret resolution occur only after earlier gates.
- Demo data ships inside the wheel so artifact-only installation can run the
  prepared scenarios.
- Report-integrity failure is conservatively blocking.
- Documentation now describes a backend-only synthetic demonstration and a
  response-scoped, non-persistent audit trail.

### Removed

- The manual workflow that loaded `OPENAI_API_KEY` merely to test its presence.
- Claims of an included React/TypeScript frontend or durable audit persistence.
