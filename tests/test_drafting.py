from types import SimpleNamespace

import pytest

from quoteproof.drafting import (
    DraftingError,
    GeneratedQuoteDraft,
    OpenAIQuoteDrafter,
)
from quoteproof.models import DraftRequest, QuoteDraft
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

    draft = drafter.draft(
        DraftRequest(quote_id="QP-42", request_text="Prepare the quotation.")
    )

    assert draft.quote_id == "QP-42"
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
