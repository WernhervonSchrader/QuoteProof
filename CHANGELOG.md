# Changelog

This project follows a SemVer-compatible package version, but no public release
or stability promise exists yet.

## Unreleased

### Added

- Frozen `uv.lock` for CPython 3.11-3.13 and locked build tooling.
- Pull-request and `main` CI for quality, security, dependency, secret, build,
  clean-install, SBOM, and artifact-hash gates.
- Strict request schemas, body/item/string bounds, safe CORS validation,
  allowlisted logging, kill switch, and a replaceable distributed usage guard.
- Privacy/data-flow, threat-model, contribution, release, and branch-protection
  documentation.

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

## 0.1.0

Existing internal MVP package version. It has no corresponding public tag or
GitHub Release. The historical branch name `snapshot/hackathon-submission-v1.0`
does not change the package version.
