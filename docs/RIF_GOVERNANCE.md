# How RIF makes QuoteProof governable

QuoteProof separates three responsibilities that are often collapsed into one
LLM call:

1. **Drafting** — OpenAI turns the sales request into a structured quotation.
2. **Reasoning support** — RIF v3.4 makes the decision context explicit and
   evidence-linked.
3. **Release authority** — deterministic controls decide whether the quotation
   can proceed.

The model can propose. RIF makes the proposal inspectable. Deterministic rules
remain the only release authority.

## What RIF adds to a quotation review

Before a gate decision is presented, the governed workflow produces a compact
**Reasoning Brief**:

- the mission: what decision is being supported;
- facts linked to retrieved policy and quote evidence IDs;
- declared assumptions and their materiality;
- hard and soft constraints, including whether each is satisfied;
- contradictions and whether they are resolved;
- uncertainties and their materiality;
- alternative options with benefits, sacrifices, risks and preconditions;
- a recommended next action;
- calibrated confidence;
- the required response: answer, partial answer, abstention or human review.

This is deliberately **not private chain-of-thought**. It is a reviewable
decision record that a user, auditor or authorised reviewer can inspect.

## The RIF validation boundary

A separate deterministic validator checks the reasoning contract against the
retrieved evidence:

- evidence IDs must refer to approved policy cards or quote facts;
- material assumptions and unresolved contradictions must be surfaced;
- confidence must be compatible with the evidence coverage;
- an abstention or human-review route must be honoured;
- the reasoning must not claim a stronger outcome than the evidence supports.

The validator is fail-closed:

- invalid or unavailable reasoning may add REQUIRES_HUMAN_REVIEW;
- it can never grant PASS;
- it can never remove a sanctions, export, quality or arithmetic block;
- it can never release a quotation.

## End-to-end flow

~~~
Sales request
    ↓
OpenAI structured draft
    ↓
Versioned policy retrieval (RAG)
    ↓
RIF reasoning brief
    ↓
RIF contract validation
    ↓
Deterministic controls
    ↓
PASS · REQUIRES HUMAN REVIEW · BLOCKED
~~~

Every stage emits an audit event. The final report is rendered from the
validated structured state, and report-integrity checks ensure that the prose
matches the gate outcome.

## Why this matters for QuoteProof

A conventional RAG demo can retrieve a policy paragraph and still leave the
reviewer guessing:

- Which facts were actually used?
- Which assumption changed the recommendation?
- Is a contradiction unresolved?
- Is the model confident because evidence is strong, or because it guessed?
- Who owns the final release decision?

RIF answers those questions without turning the model into an autonomous
approver. It turns probabilistic reasoning into bounded, evidence-linked
decision support while keeping the final authority deterministic and
auditable.

## MVP scope and limitations

QuoteProof currently uses versioned policy cards and simulated screening data
for the demo. It does not claim live sanctions-list screening, legal
export-control clearance or complete RIF/RRS conformance. Those boundaries are
shown explicitly so that a reviewer can distinguish the MVP demonstration from
a production compliance service.
