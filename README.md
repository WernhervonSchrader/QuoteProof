# QuoteProof

> **AI-generated quotations you can actually approve.**

**QuoteProof is not another AI quote generator. It is a proof and governance layer for AI-assisted commercial decisions.**

A normal language model can create a polished quotation while silently carrying forward a wrong total, an unsupported assumption, a missing approval, or a compliance conflict. QuoteProof lets GPT-5.6 draft and analyse the request, but it does not let the model approve its own work.

**GPT-5.6 generates. RIF challenges. Deterministic controls decide.**

[Open the live demo](https://quoteproof-demo.wernhervonschrader.chatgpt.site)

## The problem it solves

An AI-generated offer may look complete and still create financial, contractual, compliance, or reputational damage. RAG alone does not solve this: retrieving a policy does not prove that the model used it correctly, surfaced every material uncertainty, or respected the final decision boundary.

QuoteProof therefore separates three responsibilities that are often collapsed into one model call:

| Responsibility | Owner | Authority |
| --- | --- | --- |
| Draft a structured quotation | GPT-5.6 | May propose |
| Explain facts, assumptions, constraints, contradictions, uncertainty, and options | GPT-5.6 + RIF contract | Advisory only |
| Validate evidence and apply commercial controls | Deterministic code | Sole release authority |

The result is one of three explicit outcomes:

- **PASS** — all configured controls passed;
- **REQUIRES HUMAN REVIEW** — a material uncertainty or approval requirement needs an authorised person;
- **BLOCKED** — at least one hard control failed.

A review finding can never override a blocking finding, and model output can never grant PASS.

## What happens in a real run

A user enters a sales request in natural language. QuoteProof then:

1. asks GPT-5.6 for a schema-validated quotation draft;
2. calculates financial totals deterministically instead of trusting generated arithmetic;
3. retrieves approved, versioned policy cards;
4. creates a compact, evidence-linked RIF Reasoning Brief;
5. validates the model's evidence coverage, assumptions, contradictions, uncertainty, confidence, and abstention route;
6. runs deterministic quotation, discount, sanctions-fixture, export, and delivery-quality controls;
7. applies fail-closed precedence: **BLOCKED > HUMAN REVIEW > PASS**;
8. renders the report from validated state and checks that its prose matches the structured decision.

Every stage emits an audit event.

### Example: why the RIF layer matters

In a live test, GPT-5.6 correctly drafted ten units at EUR 250 with a five-percent discount and QuoteProof calculated the EUR 2,375 net total. The model nevertheless assigned high confidence while material screening evidence remained incomplete.

The RIF validator detected that the confidence exceeded the available evidence strength and routed the quotation to **REQUIRES HUMAN REVIEW**. The model produced useful reasoning, but it could not approve its own confidence.

In the restricted-party and controlled-goods scenario, the same pipeline returned **BLOCKED**. The softer reasoning-review finding could not weaken the sanctions and export-control blocks.

## Why this is different from “LLM + RAG”

| Conventional pattern | QuoteProof |
| --- | --- |
| Retrieved text is inserted into a prompt | Retrieved policy cards have IDs and versions |
| The model explains its own answer | A separate validator checks the reasoning contract |
| Confidence is accepted as generated | Confidence is checked against evidence coverage |
| Prose becomes the decision | Structured state is authoritative |
| The model can effectively approve its own output | Deterministic controls alone own release authority |
| Failures may degrade silently | Missing or invalid reasoning fails closed to human review |
| Audit is added afterwards | Every graph node emits an audit event |

This is auditable decision support, not private chain-of-thought. QuoteProof stores the reviewable decision record needed by a user, authorised reviewer, or auditor.

## Judge path — about two minutes

The prepared scenarios are public and require no OpenAI call.

1. Open the [live demo](https://quoteproof-demo.wernhervonschrader.chatgpt.site).
2. Select **PASS**, **HUMAN REVIEW**, and **BLOCKED**.
3. Compare the findings, policy evidence, gate precedence, and eight-step audit trail.
4. Enter the jury access code supplied privately in the Devpost testing instructions.
5. Select **Generate AI draft** to run the live GPT-5.6 path.
6. Inspect the structured quote, RIF Reasoning Brief, reasoning validation, deterministic findings, and final decision.

## Architecture

```text
Sales request
    ↓
GPT-5.6 structured draft
    ↓
Deterministic total calculation
    ↓
Versioned policy retrieval
    ↓
RIF evidence-linked reasoning brief
    ↓
RIF contract validation
    ↓
Deterministic commercial controls
    ↓
PASS · REQUIRES HUMAN REVIEW · BLOCKED
    ↓
Report-integrity check + audit trail
```

The implementation uses the OpenAI Responses API, FastAPI, Pydantic, LangGraph, TypeScript, and React.

## Gate 1 scope

The Build Week MVP includes:

- three prepared quotation scenarios;
- optional live server-side GPT-5.6 drafting;
- deterministic required-field, currency, arithmetic, and discount checks;
- controlled policy retrieval for simulated sanctions, foreign-trade, and batch-purity checks;
- evidence-linked governed reasoning;
- fail-closed reasoning validation;
- explicit PASS, REQUIRES HUMAN REVIEW, and BLOCKED outcomes;
- report-integrity validation;
- an eight-event audit trail;
- repeatable API and regression tests.

## Drafting and arithmetic contract

The sales request supplies line items, unit prices, and an optional discount.

If it does not state a net total, QuoteProof calculates the value deterministically and returns `net_total_source: "calculated"`. If the request explicitly states a total, QuoteProof preserves it as comparison evidence and returns `net_total_source: "declared"`. A mismatch with the deterministic calculation is blocked.

This separates normal quotation creation from intentional arithmetic-tampering tests.

## How Codex and GPT-5.6 were used

QuoteProof was built during OpenAI Build Week with Codex as the implementation agent. Codex helped:

- translate the product idea into the FastAPI and LangGraph architecture;
- implement the English demo UI and server-side OpenAI integration;
- add the RIF reasoning-governance layer;
- diagnose and repair the net-total contract;
- harden schema validation, secret handling, CORS, and fail-closed errors;
- write regression tests and prepare the deployment;
- document the boundary between model reasoning and release authority.

The product and governance decisions remained human-owned: the model must not approve itself, JSON state is authoritative, hard blocks take precedence, and simulated compliance data must never be presented as production clearance.

GPT-5.6 is used at runtime only for probabilistic drafting and the advisory Reasoning Brief. It identifies facts, assumptions, constraints, contradictions, uncertainties, options, and a recommended next action. RIF validates that output before deterministic controls make the final decision.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
uvicorn quoteproof.api:app --reload
```

Open `http://127.0.0.1:8000/docs` and run:

- `POST /review/pass`
- `POST /review/review`
- `POST /review/blocked`
- `POST /draft-and-review` — requires server-side `OPENAI_API_KEY` and `QUOTEPROOF_DEMO_KEY`

## Security boundary

`OPENAI_API_KEY` is read only by the server-side draft endpoint and must never use a `NEXT_PUBLIC_` prefix.

The live endpoint additionally requires `X-QuoteProof-Demo-Key`, validated against the server-side `QUOTEPROOF_DEMO_KEY`. The disposable jury code is supplied privately, is not embedded in the frontend, and protects API budget without requiring an OpenAI login. Prepared deterministic scenarios remain public.

The default CORS policy permits only the QuoteProof demo origin.

## Scope and limitations

QuoteProof is a focused Build Week MVP. It deliberately does **not** claim:

- live EU, UN, US, or UK sanctions-list screening;
- legal export-control clearance;
- general hallucination prevention;
- complete RIF or RRS conformance;
- production certification or readiness.

Restricted-party data is an explicit simulation fixture. These boundaries are part of the product: a reliable system must make clear not only what it knows, but also what it cannot safely decide.

For the detailed governance rationale, see [RIF_GOVERNANCE.md](docs/RIF_GOVERNANCE.md).
