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
    revision: int = Field(default=1, ge=1, le=10_000)
    customer: ShortText | None = None
    customer_id: Identifier | None = None
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
    customer_document: str | None = Field(
        default=None,
        max_length=50_000,
        description="The customer-facing quotation text exactly as it would be sent.",
    )

    def calculated_total(self) -> Decimal:
        subtotal = sum((item.line_total for item in self.items), Decimal("0"))
        return (subtotal * (Decimal("1") - self.discount_rate)).quantize(Decimal("0.01"))


class RuleStatus(StrEnum):
    CONFIRMED = "confirmed"
    PLACEHOLDER = "placeholder"


class RuleProvenance(StrictModel):
    """Who set a business rule, and whether it is confirmed or a placeholder."""

    status: RuleStatus = RuleStatus.CONFIRMED
    confirmed_by: ShortText | None = None
    confirmed_on: ShortText | None = None
    note: LongText | None = None


class BusinessRules(StrictModel):
    currency: CurrencyCode = "EUR"
    allowed_currencies: tuple[CurrencyCode, ...] = ()
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
    list_price_tolerance: Decimal = Decimal("0.05")
    minimum_margin_over_cost: Decimal = Decimal("0")
    provenance: dict[str, RuleProvenance] = Field(default_factory=dict)

    def permitted_currencies(self) -> tuple[str, ...]:
        return self.allowed_currencies or (self.currency,)


class OutboundRules(StrictModel):
    """What must never appear in a customer-facing quotation."""

    forbidden_terms: tuple[str, ...] = (
        "margin",
        "marge",
        "deckungsbeitrag",
        "contribution margin",
        "markup",
        "aufschlag",
        "internal",
        "intern",
        "cost price",
        "einstandspreis",
        "selbstkosten",
        "herstellkosten",
        "stundensatz",
        "hourly rate",
        "burden rate",
        "gemeinkostenzuschlag",
        "not for customer",
    )
    leak_cost_figures: bool = True
    leak_other_customer_names: bool = True


class ERPItem(StrictModel):
    sku: str
    description: str | None = None
    list_price: Decimal | None = None
    cost_floor: Decimal | None = None
    currency: str | None = None
    controlled_goods: bool | None = None
    export_classification: str | None = None
    blocked_for_sale: bool = False
    source: str


class ERPCustomer(StrictModel):
    customer_id: str | None = None
    name: str
    country: str | None = None
    blocked: bool = False
    credit_hold: bool = False
    source: str


class ERPEvidence(StrictModel):
    """A read-only snapshot of what the ERP said, with the source of each record."""

    adapter: str
    status: str
    customer: ERPCustomer | None = None
    items: dict[str, ERPItem] = Field(default_factory=dict)
    missing_skus: list[str] = Field(default_factory=list)
    known_customer_names: list[str] = Field(default_factory=list)
    error: str | None = None


class ApprovalRecord(StrictModel):
    """A human release, bound to the exact decision basis it was given on."""

    approved_by: ShortText
    approved_at: ShortText
    decision_basis_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


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
    profile_id: str = "default"
    erp_evidence: ERPEvidence | None = None
    decision_basis_hash: str = ""
    rule_provenance: dict[str, RuleProvenance] = Field(default_factory=dict)
    decision_scope: str = "synthetic_demo_only"
    disclaimer: str = (
        "This response uses synthetic policy fixtures and is not sanctions, export, "
        "legal, quality, or human approval."
    )


class RevisionReviewRequest(StrictModel):
    quote: QuoteDraft
    previous: QuoteDraft | None = None
    approval: ApprovalRecord | None = None


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
    previous: QuoteDraft | None
    approval: ApprovalRecord | None
    erp_evidence: ERPEvidence | None
    decision_basis_hash: str
