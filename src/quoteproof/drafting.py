from __future__ import annotations

import os
from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel, Field

from .models import DraftingResult, DraftRequest, NetTotalSource, QuoteDraft


class DraftingError(RuntimeError):
    """Raised when a model response cannot become a governed quote draft."""


class ResponsesClient(Protocol):
    class Responses(Protocol):
        def parse(self, **kwargs): ...

    responses: Responses


class GeneratedQuoteItem(BaseModel):
    """Model-facing schema without defaults or Decimal union encodings."""

    sku: str
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class GeneratedQuoteDraft(BaseModel):
    """Strict structured-output envelope; every field is explicitly required."""

    quote_id: str
    customer: str | None
    customer_country: str | None
    destination_country: str | None
    currency: str | None
    items: list[GeneratedQuoteItem]
    discount_rate: float = Field(ge=0, le=1)
    net_total: float | None
    payment_terms: str | None
    valid_until: str | None
    controlled_goods: bool
    export_license_id: str | None
    batch_pure_required: bool
    batch_pure_confirmed: bool | None


class OpenAIQuoteDrafter:
    """Creates a structured draft; it has no authority over the gate decision."""

    def __init__(
        self,
        client: ResponsesClient | None = None,
        model: str | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
        self.client = client or OpenAI()

    def draft(self, request: DraftRequest) -> DraftingResult:
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
                        "stated. Treat net_total as a declared comparison value: copy it only "
                        "when the request explicitly states a total, otherwise return null. "
                        "Do not calculate or infer net_total. The downstream deterministic "
                        "controls own calculations and every decision."
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
            text_format=GeneratedQuoteDraft,
        )
        generated = response.output_parsed
        if generated is None:
            raise DraftingError("The model did not return a valid quotation draft.")
        quote = QuoteDraft.model_validate(generated.model_dump())
        if quote.quote_id != request.quote_id:
            quote = quote.model_copy(update={"quote_id": request.quote_id})
        if generated.net_total is not None:
            source = NetTotalSource.DECLARED
        elif quote.items:
            quote = quote.model_copy(update={"net_total": quote.calculated_total()})
            source = NetTotalSource.CALCULATED
        else:
            source = NetTotalSource.MISSING
        return DraftingResult(quote=quote, net_total_source=source)
