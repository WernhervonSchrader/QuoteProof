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

## Core rule

**The model may generate the draft. Deterministic controls decide whether it
may proceed.**

Gate 2 will add the OpenAI draft adapter and the small browser demonstration.

## Knowledge-layer boundary

The MVP retrieves versioned policy cards before validation and links every
finding to a policy ID. The restricted-party data is an explicit simulation
fixture. QuoteProof does not claim a live EU, UN, US or UK sanctions-list check,
legal export-control clearance, or production compliance coverage.
