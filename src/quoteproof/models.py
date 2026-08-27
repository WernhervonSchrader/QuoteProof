from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
]
CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GateDecision(StrEnum):
    # This is a domain decision enum, not a credential.
    PASS = "PASS"  # nosec B105
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class FindingEffect(StrEnum):
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class NetTotalSource(StrEnum):
    DECLARED = "declared"
    CALCULATED = "calculated"
    MISSING = "missing"


class ReasoningMateriality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReasoningConstraintType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class ReasoningConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningResponse(StrEnum):
    ANSWER = "answer"
    PARTIAL_ANSWER = "partial_answer"
    ABSTAIN = "abstain"
    HUMAN_REVIEW = "human_review"


class ReasoningValidationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    APPROVED = "APPROVED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    FAIL = "FAIL"


class QuoteItem(StrictModel):
    sku: Identifier
    description: ShortText
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class QuoteDraft(StrictModel):
    quote_id: Identifier
    customer: ShortText | None = None
    customer_country: CountryCode | None = None
    destination_country: CountryCode | None = None
    currency: CurrencyCode | None = None
    items: list[QuoteItem] = Field(default_factory=list, max_length=50)
    discount_rate: Decimal = Field(
        default=Decimal("0"), ge=0, le=1, max_digits=5, decimal_places=4
    )
    net_total: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    payment_terms: ShortText | None = None
    valid_until: date | None = None
    controlled_goods: bool = False
    export_license_id: Identifier | None = None
    batch_pure_required: bool = False
    batch_pure_confirmed: bool | None = None

    def calculated_total(self) -> Decimal:
        subtotal = sum((item.line_total for item in self.items), Decimal("0"))
        return (subtotal * (Decimal("1") - self.discount_rate)).quantize(Decimal("0.01"))


class BusinessRules(StrictModel):
    currency: CurrencyCode = "EUR"
    maximum_discount_without_approval: Decimal = Decimal("0.10")
    required_fields: tuple[str, ...] = (
        "customer",
        "currency",
        "items",
        "net_total",
        "payment_terms",
        "valid_until",
    )
    total_tolerance: Decimal = Decimal("0.01")


class PolicyDocument(StrictModel):
    id: Identifier
    title: ShortText
    version: Identifier
    tags: list[Identifier] = Field(max_length=20)
    content: LongText
    data: dict[str, object] = Field(default_factory=dict)


class ReasoningFact(StrictModel):
    statement: LongText
    evidence_ids: list[ShortText] = Field(max_length=20)
    materiality: ReasoningMateriality


class ReasoningAssumption(StrictModel):
    statement: LongText
    materiality: ReasoningMateriality


class ReasoningConstraint(StrictModel):
    statement: LongText
    constraint_type: ReasoningConstraintType
    evidence_ids: list[ShortText] = Field(max_length=20)
    satisfied: bool | None


class ReasoningContradiction(StrictModel):
    statement: LongText
    evidence_ids: list[ShortText] = Field(max_length=20)
    materiality: ReasoningMateriality
    resolved: bool


class ReasoningUncertainty(StrictModel):
    statement: LongText
    evidence_ids: list[ShortText] = Field(max_length=20)
    materiality: ReasoningMateriality


class ReasoningOption(StrictModel):
    title: ShortText
    benefit: LongText
    sacrifice: LongText
    risks: list[LongText] = Field(max_length=20)
    preconditions: list[LongText] = Field(max_length=20)


class ReasoningBrief(StrictModel):
    mission: LongText
    facts: list[ReasoningFact] = Field(max_length=50)
    assumptions: list[ReasoningAssumption] = Field(max_length=50)
    constraints: list[ReasoningConstraint] = Field(max_length=50)
    contradictions: list[ReasoningContradiction] = Field(max_length=50)
    uncertainties: list[ReasoningUncertainty] = Field(max_length=50)
    options: list[ReasoningOption] = Field(max_length=20)
    recommended_next_action: LongText
    confidence: ReasoningConfidence
    required_response: ReasoningResponse


class ReasoningValidation(StrictModel):
    status: ReasoningValidationStatus
    evidence_coverage: float = Field(ge=0, le=1)
    issues: list[LongText] = Field(max_length=50)


class Finding(StrictModel):
    code: Identifier
    effect: FindingEffect
    message: LongText
    field: Identifier | None = None
    expected: LongText | None = None
    actual: LongText | None = None
    policy_id: Identifier


class AuditEvent(StrictModel):
    timestamp: str
    node: str
    action: str
    status: str
    detail: str = ""

    @classmethod
    def now(cls, node: str, action: str, status: str, detail: str = "") -> AuditEvent:
        return cls(
            timestamp=datetime.now(UTC).isoformat(),
            node=node,
            action=action,
            status=status,
            detail=detail,
        )


class ReviewResult(StrictModel):
    quote: QuoteDraft
    gate: GateDecision
    findings: list[Finding]
    retrieved_policies: list[PolicyDocument]
    summary: str
    audit_trail: list[AuditEvent]
    report_integrity: bool
    reasoning_brief: ReasoningBrief | None
    reasoning_validation: ReasoningValidation
    decision_scope: str = "synthetic_demo_only"
    disclaimer: str = (
        "This response uses synthetic policy fixtures and is not sanctions, export, "
        "legal, quality, or human approval."
    )


class DraftRequest(StrictModel):
    quote_id: Identifier
    request_text: str = Field(
        min_length=1,
        max_length=12_000,
        description=(
            "Synthetic data only. If live drafting is separately enabled, this text is "
            "transmitted to OpenAI."
        ),
    )
    default_currency: CurrencyCode = "EUR"


class DraftingResult(StrictModel):
    quote: QuoteDraft
    net_total_source: NetTotalSource


class DraftAndReviewResult(StrictModel):
    draft_source: str = "openai"
    model: str
    net_total_source: NetTotalSource
    review: ReviewResult


class QuoteState(TypedDict):
    quote: QuoteDraft
    rules: BusinessRules
    findings: list[Finding]
    retrieved_policies: list[PolicyDocument]
    gate: GateDecision | None
    summary: str
    audit_trail: list[AuditEvent]
    report_integrity: bool
    reasoning_brief: ReasoningBrief | None
    reasoning_validation: ReasoningValidation
    reasoning_error: str | None
