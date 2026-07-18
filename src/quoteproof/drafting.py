from __future__ import annotations

import os
from typing import Protocol

from openai import OpenAI

from .models import DraftRequest, QuoteDraft


class DraftingError(RuntimeError):
    """Raised when a model response cannot become a governed quote draft."""


class ResponsesClient(Protocol):
    class Responses(Protocol):
        def parse(self, **kwargs): ...

    responses: Responses


class OpenAIQuoteDrafter:
    """Creates a structured draft; it has no authority over the gate decision."""

    def __init__(
        self,
        client: ResponsesClient | None = None,
        model: str | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
        self.client = client or OpenAI()

    def draft(self, request: DraftRequest) -> QuoteDraft:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Convert the sales request into a quotation draft. Extract only "
                        "facts present in the request. Use null for missing optional fields "
                        "and omit incomplete line items. Never decide approval, sanctions, "
                        "export-control, or quality compliance. Preserve the supplied quote "
                        "ID and use the supplied default currency only when no currency is "
                        "stated. The downstream deterministic controls own every decision."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"quote_id: {request.quote_id}\n"
                        f"default_currency: {request.default_currency}\n"
                        f"request:\n{request.request_text}"
                    ),
                },
            ],
            text_format=QuoteDraft,
        )
        quote = response.output_parsed
        if quote is None:
            raise DraftingError("The model did not return a valid quotation draft.")
        if quote.quote_id != request.quote_id:
            quote = quote.model_copy(update={"quote_id": request.quote_id})
        return quote
