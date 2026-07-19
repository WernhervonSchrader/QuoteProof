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

## Governed reasoning

Live drafting also produces a concise RIF v3.4 reasoning brief: facts with
evidence IDs, declared assumptions, hard and soft constraints, contradictions,
uncertainties, trade-off options, confidence, and an abstention or human-review
route. This is auditable decision support rather than private chain-of-thought.

A separate deterministic node validates evidence coverage, approved source
IDs, material assumptions, unresolved contradictions, confidence calibration,
and abstention. Invalid or unavailable reasoning can only add a human-review
requirement; it cannot grant `PASS`, remove a blocking finding, or release a
quotation. The existing deterministic gate remains the sole decision owner.

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

The live endpoint additionally requires the disposable request header
`X-QuoteProof-Demo-Key`, validated against the server-side
`QUOTEPROOF_DEMO_KEY` secret. This shared jury code protects API budget without
requiring an OpenAI login. It is not embedded in the frontend, and the prepared
deterministic scenarios remain public.

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

## RIF governance in detail

The RIF contribution is documented in
[docs/RIF_GOVERNANCE.md](docs/RIF_GOVERNANCE.md). It explains how QuoteProof
turns model reasoning into evidence-linked, validated decision support without
giving the model release authority.

The short version: OpenAI drafts, policy RAG supplies versioned evidence, RIF
checks facts, assumptions, constraints, contradictions, uncertainty and
confidence, and deterministic controls alone produce PASS, REQUIRES HUMAN
REVIEW or BLOCKED.

## How Codex and GPT-5.6 were used

Codex was used as the implementation agent for QuoteProof: it shaped the
FastAPI and LangGraph workflow, implemented the English demo UI, connected the
server-side OpenAI path, added the RIF reasoning-governance layer, wrote
regression tests, and deployed the public demo.

GPT-5.6 is used at runtime only for the probabilistic drafting and reasoning
brief. It extracts a structured quotation from the sales request and proposes
facts, assumptions, constraints, contradictions, uncertainties and options.
That output is then validated by RIF and passed to deterministic controls.
GPT-5.6 never has release authority: only the deterministic gate can return
PASS, REQUIRES HUMAN REVIEW or BLOCKED.

### Judge path

1. Open the public demo.
2. Enter the jury access code supplied in the Devpost submission.
3. Choose a prepared PASS, HUMAN REVIEW or BLOCKED scenario, or enter a live
   sales request.
4. For the live path, enter the access code and select **Generate AI draft**.
5. Inspect the structured quote, RIF Reasoning Brief, control findings and
   eight-step audit trail.

