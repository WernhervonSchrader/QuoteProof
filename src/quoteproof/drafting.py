from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from .models import (
    CurrencyCode,
    DraftingResult,
    DraftRequest,
    Identifier,
    NetTotalSource,
    QuoteDraft,
    ShortText,
    StrictModel,
)


class DraftingError(RuntimeError):
    """Raised when a model response cannot become a governed quote draft."""


class ResponsesClient(Protocol):
    class Responses(Protocol):
        def parse(self, **kwargs: object) -> Any: ...

    responses: Responses


class GeneratedQuoteItem(StrictModel):
    """Model-facing schema without defaults or Decimal union encodings."""

    sku: Identifier
    description: ShortText
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class GeneratedQuoteDraft(StrictModel):
    """Strict structured-output envelope; every field is explicitly required."""

    quote_id: Identifier
    customer: ShortText | None
    customer_country: str | None = Field(pattern=r"^[A-Z]{2}$")
    destination_country: str | None = Field(pattern=r"^[A-Z]{2}$")
    currency: CurrencyCode | None
    items: list[GeneratedQuoteItem] = Field(max_length=50)
    discount_rate: float = Field(ge=0, le=1)
    net_total: float | None
    payment_terms: ShortText | None
    valid_until: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    controlled_goods: bool
    export_license_id: Identifier | None
    batch_pure_required: bool
    batch_pure_confirmed: bool | None


class OpenAIQuoteDrafter:
    """Creates a structured draft; it has no authority over the gate decision."""

    def __init__(
        self,
        client: ResponsesClient,
        model: str,
        max_output_tokens: int = 1_200,
    ) -> None:
        self.model = model
        self.client = client
        self.max_output_tokens = max_output_tokens

    def draft(self, request: DraftRequest) -> DraftingResult:
        response = self.client.responses.parse(
            model=self.model,
            max_output_tokens=self.max_output_tokens,
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
