# Changelog

This project follows SemVer-compatible package versioning. A release does not
imply production, legal, compliance, or professional-advice suitability.

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
