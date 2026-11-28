from __future__ import annotations

import json
from typing import Protocol

from .drafting import ResponsesClient
from .models import (
    Finding,
    FindingEffect,
    PolicyDocument,
    QuoteDraft,
    ReasoningBrief,
    ReasoningConfidence,
    ReasoningMateriality,
    ReasoningResponse,
    ReasoningValidation,
    ReasoningValidationStatus,
)

REASONING_POLICY_ID = "POL-RIF-REASONING-001"


class ReasoningError(RuntimeError):
    """Raised when governed reasoning cannot produce its structured contract."""


class ReasoningAnalyst(Protocol):
    def analyse(
        self,
        quote: QuoteDraft,
        policies: list[PolicyDocument],
    ) -> ReasoningBrief: ...


class OpenAIReasoningAnalyst:
    """Produces evidence-linked decision support without release authority."""

    def __init__(
        self,
        client: ResponsesClient,
        model: str,
        max_output_tokens: int = 1_200,
    ) -> None:
        self.model = model
        self.client = client
        self.max_output_tokens = max_output_tokens

    def analyse(
        self,
        quote: QuoteDraft,
        policies: list[PolicyDocument],
    ) -> ReasoningBrief:
        quote_evidence_ids = [
            f"QUOTE:{field}"
            for field in QuoteDraft.model_fields
            if getattr(quote, field) not in (None, "", [])
        ]
        policy_evidence_ids = [policy.id for policy in policies]
        policy_payload = [
            {
                "id": policy.id,
                "title": policy.title,
                "content": policy.content,
            }
            for policy in policies
        ]
        response = self.client.responses.parse(
            model=self.model,
            max_output_tokens=self.max_output_tokens,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Create a concise, auditable reasoning brief for quotation review. "
                        "Return decision support, not private chain-of-thought. Separate facts, "
                        "assumptions, constraints, contradictions, uncertainties and trade-off "
                        "options. Every fact, constraint, contradiction and uncertainty must cite "
                        "only the supplied evidence IDs. Never invent a source. Evaluate within "
                        "the explicit Build Week simulation scope; do not escalate solely because "
                        "the known sanctions fixture is simulated. Never set or imply PASS, BLOCKED, approval, "
                        "sanctions clearance or legal export clearance. Use human_review when a "
                        "material constraint is unknown or a material contradiction is unresolved. "
                        "Use abstain when the evidence cannot support useful decision assistance. "
                        "The downstream deterministic validators retain all release authority."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"allowed_evidence_ids: {json.dumps(quote_evidence_ids + policy_evidence_ids)}\n"
                        f"quote: {quote.model_dump_json()}\n"
                        f"policies: {json.dumps(policy_payload)}"
                    ),
                },
            ],
            text_format=ReasoningBrief,
        )
        brief = response.output_parsed
        if brief is None:
            raise ReasoningError("The model did not return a governed reasoning brief.")
        return ReasoningBrief.model_validate(brief)


def _allowed_evidence_ids(
    quote: QuoteDraft,
    policies: list[PolicyDocument],
) -> set[str]:
    quote_ids = {
        f"QUOTE:{field}"
        for field in QuoteDraft.model_fields
        if getattr(quote, field) not in (None, "", [])
    }
    return quote_ids | {policy.id for policy in policies}


def validate_reasoning_brief(
    brief: ReasoningBrief,
    quote: QuoteDraft,
    policies: list[PolicyDocument],
) -> tuple[ReasoningValidation, list[Finding]]:
    """Deterministically validate the advisory brief against evidence and RIF gates."""

    allowed = _allowed_evidence_ids(quote, policies)
    evidence_sets = [
        *(fact.evidence_ids for fact in brief.facts),
        *(constraint.evidence_ids for constraint in brief.constraints),
        *(conflict.evidence_ids for conflict in brief.contradictions),
        *(uncertainty.evidence_ids for uncertainty in brief.uncertainties),
    ]
    total_evidence_sets = len(evidence_sets)
    grounded_sets = sum(
        1 for evidence_ids in evidence_sets if evidence_ids and set(evidence_ids) <= allowed
    )
    coverage = grounded_sets / total_evidence_sets if total_evidence_sets else 0.0
    issues: list[str] = []

    if not brief.facts:
        issues.append("The reasoning brief contains no evidence-linked facts.")
    if any(not ids or not set(ids) <= allowed for ids in evidence_sets):
        issues.append(
            "One or more reasoning statements use missing or unapproved evidence IDs."
        )
    if any(
        item.materiality in {ReasoningMateriality.HIGH, ReasoningMateriality.CRITICAL}
        for item in brief.assumptions
    ):
        issues.append("A material assumption remains unresolved.")
    if any(
        not item.resolved
        and item.materiality in {ReasoningMateriality.HIGH, ReasoningMateriality.CRITICAL}
        for item in brief.contradictions
    ):
        issues.append("A material contradiction remains unresolved.")
    if any(
        item.materiality in {ReasoningMateriality.HIGH, ReasoningMateriality.CRITICAL}
        for item in brief.uncertainties
    ):
        issues.append("A material uncertainty requires human ownership.")
    if brief.required_response in {
        ReasoningResponse.ABSTAIN,
        ReasoningResponse.HUMAN_REVIEW,
    }:
        issues.append(f"The reasoning route requires {brief.required_response.value}.")
    if brief.confidence is ReasoningConfidence.HIGH and (
        brief.assumptions or brief.uncertainties
    ):
        issues.append("High confidence exceeds the available evidence strength.")
    advisory_text = " ".join(
        [brief.mission, brief.recommended_next_action]
        + [option.title for option in brief.options]
    ).casefold()
    prohibited_authority_claims = (
        "approved by human",
        "human approved",
        "sanctions cleared",
        "sanctions clearance",
        "export cleared",
        "export clearance granted",
        "legal approval granted",
    )
    if any(claim in advisory_text for claim in prohibited_authority_claims):
        issues.append("Advisory output attempted to assert external or human approval.")

    status = (
        ReasoningValidationStatus.REQUIRES_HUMAN_REVIEW
        if issues
        else ReasoningValidationStatus.APPROVED
    )
    validation = ReasoningValidation(
        status=status,
        evidence_coverage=round(coverage, 4),
        issues=issues,
    )
    findings = []
    if issues:
        findings.append(
            Finding(
                code="QP-REASON-001",
                effect=FindingEffect.REVIEW,
                message="Governed reasoning requires authorised human review.",
                field="reasoning_brief",
                expected="evidence-linked, calibrated and contradiction-safe reasoning",
                actual="; ".join(issues),
                policy_id=REASONING_POLICY_ID,
            )
        )
    return validation, findings
