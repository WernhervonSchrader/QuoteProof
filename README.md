# QuoteProof

> AI-generated offers you can actually approve.

QuoteProof is a Build Week MVP that demonstrates a governed review process for
AI-assisted quotations. A LangGraph workflow keeps drafting and explanation
separate from deterministic approval authority.

## Gate 1 scope

- three prepared quotation scenarios;
- deterministic required-field, currency, total, and discount checks;
- controlled policy retrieval for sanctions, foreign-trade and batch-purity checks;
- `PASS`, `REQUIRES_HUMAN_REVIEW`, and `BLOCKED` outcomes;
- report-integrity validation;
- an audit event for every graph node;
- FastAPI endpoints and repeatable tests.
- optional server-side OpenAI structured drafting through the Responses API.

The current Gate 1 implementation deliberately does **not** claim complete RIF
or RRS conformance, general hallucination prevention, or production readiness.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
uvicorn quoteproof.api:app --reload
```

Open `http://127.0.0.1:8000/docs` and run one of:

- `POST /review/pass`
- `POST /review/review`
- `POST /review/blocked`
- `POST /draft-and-review` (requires the server-side `OPENAI_API_KEY` secret)

## Core rule

**The model may generate the draft. Deterministic controls decide whether it
may proceed.**

The OpenAI adapter can create a schema-validated draft, but it cannot approve
the quote. Its output always enters the same LangGraph knowledge retrieval and
deterministic validation pipeline as the prepared scenarios.

## Drafting input contract

The sales request supplies line items, unit prices, and an optional discount.
When it does not explicitly state a net total, QuoteProof calculates that value
deterministically before review and returns `net_total_source: "calculated"`.
When the request explicitly states a net total, QuoteProof preserves it as a
comparison value and returns `net_total_source: "declared"`; a mismatch with
the deterministic calculation is blocked. This keeps ordinary quote creation
separate from intentional arithmetic-tampering tests.

## Secret boundary

`OPENAI_API_KEY` is read only by the server-side draft endpoint. It must be
provided by the deployment runtime or GitHub Actions secret configuration and
must never use a `NEXT_PUBLIC_` prefix. The deterministic review endpoints work
without an API key.

## Deploy the API on Vercel

The repository contains a Vercel FastAPI entrypoint and a 60-second function
limit for governed drafting requests. Import the GitHub repository into Vercel,
then add `OPENAI_API_KEY` as a **Sensitive** Production environment variable.
Optionally set `OPENAI_MODEL`; it defaults to `gpt-5.6-terra`.

The default CORS policy permits only the QuoteProof demo origin. Override it
with a comma-separated `QUOTEPROOF_ALLOWED_ORIGINS` server variable when the
frontend URL changes.

## Knowledge-layer boundary

The MVP retrieves versioned policy cards before validation and links every
finding to a policy ID. The restricted-party data is an explicit simulation
fixture. QuoteProof does not claim a live EU, UN, US or UK sanctions-list check,
legal export-control clearance, or production compliance coverage.
