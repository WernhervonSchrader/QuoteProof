from decimal import Decimal
from types import SimpleNamespace

import pytest

from quoteproof.drafting import (
    DraftingError,
    GeneratedQuoteDraft,
    OpenAIQuoteDrafter,
)
from quoteproof.graph import QuoteReviewPipeline
from quoteproof.models import DraftRequest, GateDecision, NetTotalSource
from quoteproof.scenarios import load_scenario


class FakeResponses:
    def __init__(self, output: GeneratedQuoteDraft | None) -> None:
        self.output = output
        self.call: dict | None = None

    def parse(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(output_parsed=self.output)


def test_openai_draft_is_structured_and_quote_id_is_authoritative() -> None:
    generated = GeneratedQuoteDraft.model_validate(
        load_scenario("pass").model_copy(update={"quote_id": "wrong-id"}).model_dump()
    )
    responses = FakeResponses(generated)
    drafter = OpenAIQuoteDrafter(
        client=SimpleNamespace(responses=responses),
        model="test-model",
    )

    drafted = drafter.draft(
        DraftRequest(quote_id="QP-42", request_text="Prepare the quotation.")
    )

    assert drafted.quote.quote_id == "QP-42"
    assert drafted.net_total_source is NetTotalSource.DECLARED
    assert responses.call is not None
    assert responses.call["text_format"] is GeneratedQuoteDraft
    assert responses.call["model"] == "test-model"


def test_missing_structured_output_fails_closed() -> None:
    drafter = OpenAIQuoteDrafter(
        client=SimpleNamespace(responses=FakeResponses(None)),
        model="test-model",
    )

    with pytest.raises(DraftingError):
        drafter.draft(DraftRequest(quote_id="QP-42", request_text="Draft it."))


def test_missing_total_is_calculated_deterministically_before_review() -> None:
    generated = GeneratedQuoteDraft.model_validate(
        load_scenario("pass").model_copy(
            update={"discount_rate": Decimal("0.15"), "net_total": None}
        ).model_dump()
    )
    drafter = OpenAIQuoteDrafter(
        client=SimpleNamespace(responses=FakeResponses(generated)),
        model="test-model",
    )

    drafted = drafter.draft(
        DraftRequest(quote_id="QP-CALC", request_text="Apply a 15 percent discount.")
    )
    review = QuoteReviewPipeline().run(drafted.quote)

    assert drafted.net_total_source is NetTotalSource.CALCULATED
    assert drafted.quote.net_total == drafted.quote.calculated_total()
    assert review.gate is GateDecision.REQUIRES_HUMAN_REVIEW
    assert [finding.code for finding in review.findings] == ["QP-DISCOUNT-001"]


def test_explicit_inconsistent_total_remains_declared_and_blocks() -> None:
    generated = GeneratedQuoteDraft.model_validate(
        load_scenario("pass").model_copy(
            update={"net_total": Decimal("100.00")}
        ).model_dump()
    )
    drafter = OpenAIQuoteDrafter(
        client=SimpleNamespace(responses=FakeResponses(generated)),
        model="test-model",
    )

    drafted = drafter.draft(
        DraftRequest(quote_id="QP-DECLARED", request_text="Keep net total at EUR 100.")
    )
    review = QuoteReviewPipeline().run(drafted.quote)

    assert drafted.net_total_source is NetTotalSource.DECLARED
    assert drafted.quote.net_total == 100
    assert review.gate is GateDecision.BLOCKED
    assert "QP-TOTAL-001" in [finding.code for finding in review.findings]
