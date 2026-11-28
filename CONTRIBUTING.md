# Contributing

QuoteProof is licensed under Apache License 2.0. Unless explicitly marked
otherwise in writing, an intentionally submitted and accepted contribution is
provided under the same license, consistent with section 5. Submission does not
guarantee acceptance or release.

## Local checks

Use CPython 3.11-3.13 and install only from the frozen environment:

```bash
uv sync --frozen --dev
uv lock --check
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run mypy src
uv run pytest -q --cov=quoteproof --cov-branch --cov-report=term-missing
uv run bandit -q -r src
uv run python scripts/check_tracked_credentials.py
```

Do not add live-provider calls to the regular test suite. Use deterministic
fakes and assert that rejected paths stop before secret resolution, client
construction, or network I/O. Do not weaken a gate, exclusion, or coverage
threshold merely to make CI pass.

## Changes and review

Keep commits small and describe security or governance effects. Update tests and
documentation with behavior changes. Do not include secrets, customer data,
private-project material, generated provider responses, or unapproved RIF
content. Security findings follow [SECURITY.md](SECURITY.md), not public issues.

Every release-sensitive change requires an independent review bound to the exact
commit. A green CI run does not authorize publication or deployment.
