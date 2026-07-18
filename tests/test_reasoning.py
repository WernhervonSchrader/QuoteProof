from quoteproof.graph import QuoteReviewPipeline
from quoteproof.models import (
    GateDecision,
    ReasoningAssumption,
    ReasoningBrief,
    ReasoningConfidence,
    ReasoningConstraint,
    ReasoningConstraintType,
    ReasoningContradiction,
    ReasoningFact,
    ReasoningMateriality,
    ReasoningOption,
    ReasoningResponse,
    ReasoningUncertainty,
    ReasoningValidationStatus,
)
from quoteproof.scenarios import load_scenario


class FakeReasoner:
    def __init__(self, brief: ReasoningBrief) -> None:
        self.brief = brief

    def analyse(self, quote, policies) -> ReasoningBrief:
        return self.brief


def approved_brief() -> ReasoningBrief:
    return ReasoningBrief(
        mission="Assess the quotation without owning the release decision.",
        facts=[
            ReasoningFact(
                statement="The quoted currency is EUR.",
                evidence_ids=["QUOTE:currency"],
                materiality=ReasoningMateriality.MEDIUM,
            )
        ],
        assumptions=[],
        constraints=[
            ReasoningConstraint(
                statement="Quotation arithmetic must be consistent.",
                constraint_type=ReasoningConstraintType.HARD,
                evidence_ids=["POL-QUOTE-001"],
                satisfied=True,
            )
        ],
        contradictions=[],
        uncertainties=[],
        options=[
            ReasoningOption(
                title="Continue to deterministic gates",
                benefit="Preserves release authority in validated rules.",
                sacrifice="No autonomous approval is provided.",
                risks=[],
                preconditions=["All deterministic controls must pass."],
            )
        ],
        recommended_next_action="Continue to deterministic validation.",
        confidence=ReasoningConfidence.HIGH,
        required_response=ReasoningResponse.ANSWER,
    )


def test_valid_reasoning_is_advisory_and_cannot_change_a_pass_gate() -> None:
    result = QuoteReviewPipeline(reasoner=FakeReasoner(approved_brief())).run(
        load_scenario("pass")
    )

    assert result.reasoning_validation.status is ReasoningValidationStatus.APPROVED
    assert result.reasoning_validation.evidence_coverage == 1
    assert result.gate is GateDecision.PASS
    assert "gate" not in ReasoningBrief.model_fields


def test_ungrounded_material_reasoning_routes_to_human_review() -> None:
    brief = approved_brief().model_copy(
        update={
            "facts": [
                ReasoningFact(
                    statement="An unverified source clears the customer.",
                    evidence_ids=["POL-UNKNOWN-999"],
                    materiality=ReasoningMateriality.CRITICAL,
                )
            ],
            "assumptions": [
                ReasoningAssumption(
                    statement="Supplier confirmation will arrive later.",
                    materiality=ReasoningMateriality.HIGH,
                )
            ],
            "contradictions": [
                ReasoningContradiction(
                    statement="Required confirmation is absent.",
                    evidence_ids=["POL-QUALITY-001"],
                    materiality=ReasoningMateriality.HIGH,
                    resolved=False,
                )
            ],
            "uncertainties": [
                ReasoningUncertainty(
                    statement="Batch-pure fulfilment is unknown.",
                    evidence_ids=["QUOTE:batch_pure_required"],
                    materiality=ReasoningMateriality.HIGH,
                )
            ],
            "required_response": ReasoningResponse.HUMAN_REVIEW,
        }
    )

    result = QuoteReviewPipeline(reasoner=FakeReasoner(brief)).run(
        load_scenario("pass").model_copy(update={"batch_pure_required": True})
    )

    assert (
        result.reasoning_validation.status
        is ReasoningValidationStatus.REQUIRES_HUMAN_REVIEW
    )
    assert result.gate is GateDecision.REQUIRES_HUMAN_REVIEW
    assert "QP-REASON-001" in {finding.code for finding in result.findings}
