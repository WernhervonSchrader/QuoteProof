from decimal import Decimal

from quoteproof.graph import QuoteReviewPipeline
from quoteproof.models import GateDecision
from quoteproof.scenarios import load_scenario


def test_pass_scenario() -> None:
    result = QuoteReviewPipeline().run(load_scenario("pass"))
    assert result.gate is GateDecision.PASS
    assert result.findings == []
    assert result.report_integrity is True


def test_review_scenario() -> None:
    result = QuoteReviewPipeline().run(load_scenario("review"))
    assert result.gate is GateDecision.REQUIRES_HUMAN_REVIEW
    assert [finding.code for finding in result.findings] == [
        "QP-DISCOUNT-001",
        "QP-QUALITY-001",
    ]


def test_blocked_scenario() -> None:
    result = QuoteReviewPipeline().run(load_scenario("blocked"))
    assert result.gate is GateDecision.BLOCKED
    assert "QP-TOTAL-001" in [finding.code for finding in result.findings]


def test_block_precedes_review() -> None:
    quote = load_scenario("review").model_copy(update={"net_total": Decimal("1900.00")})
    result = QuoteReviewPipeline().run(quote)
    assert result.gate is GateDecision.BLOCKED


def test_gate_is_reproducible() -> None:
    pipeline = QuoteReviewPipeline()
    quote = load_scenario("review")
    first = pipeline.run(quote)
    second = pipeline.run(quote)
    assert first.gate == second.gate
    assert first.findings == second.findings


def test_audit_trail_covers_all_nodes() -> None:
    result = QuoteReviewPipeline().run(load_scenario("pass"))
    assert [event.node for event in result.audit_trail] == [
        "ingest",
        "retrieve_knowledge",
        "reason",
        "validate_reasoning",
        "validate",
        "gate",
        "report",
        "report_integrity",
    ]


def test_policy_retrieval_is_traceable() -> None:
    result = QuoteReviewPipeline().run(load_scenario("review"))
    policy_ids = {policy.id for policy in result.retrieved_policies}
    assert {"POL-QUOTE-001", "POL-SANCTIONS-001", "POL-EXPORT-001"} <= policy_ids
    assert all(finding.policy_id in policy_ids for finding in result.findings)


def test_simulated_sanctions_match_blocks() -> None:
    result = QuoteReviewPipeline().run(load_scenario("blocked"))
    assert result.gate is GateDecision.BLOCKED
    assert "QP-SANCTIONS-001" in {finding.code for finding in result.findings}


def test_missing_export_authorisation_blocks_controlled_goods() -> None:
    result = QuoteReviewPipeline().run(load_scenario("blocked"))
    assert "QP-EXPORT-001" in {finding.code for finding in result.findings}
