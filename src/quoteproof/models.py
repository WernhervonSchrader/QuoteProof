from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field, computed_field


class GateDecision(str, Enum):
    PASS = "PASS"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class FindingEffect(str, Enum):
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class NetTotalSource(str, Enum):
    DECLARED = "declared"
    CALCULATED = "calculated"
    MISSING = "missing"


class ReasoningMateriality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReasoningConstraintType(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class ReasoningConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningResponse(str, Enum):
    ANSWER = "answer"
    PARTIAL_ANSWER = "partial_answer"
    ABSTAIN = "abstain"
    HUMAN_REVIEW = "human_review"


class ReasoningValidationStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    APPROVED = "APPROVED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    FAIL = "FAIL"


class QuoteItem(BaseModel):
    sku: str
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)

    @computed_field
    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class QuoteDraft(BaseModel):
    quote_id: str
    customer: str | None = None
    customer_country: str | None = None
    destination_country: str | None = None
    currency: str | None = None
    items: list[QuoteItem] = Field(default_factory=list)
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    net_total: Decimal | None = None
    payment_terms: str | None = None
    valid_until: str | None = None
    controlled_goods: bool = False
    export_license_id: str | None = None
    batch_pure_required: bool = False
    batch_pure_confirmed: bool | None = None

    def calculated_total(self) -> Decimal:
        subtotal = sum((item.line_total for item in self.items), Decimal("0"))
        return (subtotal * (Decimal("1") - self.discount_rate)).quantize(Decimal("0.01"))


class BusinessRules(BaseModel):
    currency: str = "EUR"
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


class PolicyDocument(BaseModel):
    id: str
    title: str
    version: str
    tags: list[str]
    content: str
    data: dict[str, object] = Field(default_factory=dict)


class ReasoningFact(BaseModel):
    statement: str
    evidence_ids: list[str]
    materiality: ReasoningMateriality


class ReasoningAssumption(BaseModel):
    statement: str
    materiality: ReasoningMateriality


class ReasoningConstraint(BaseModel):
    statement: str
    constraint_type: ReasoningConstraintType
    evidence_ids: list[str]
    satisfied: bool | None


class ReasoningContradiction(BaseModel):
    statement: str
    evidence_ids: list[str]
    materiality: ReasoningMateriality
    resolved: bool


class ReasoningUncertainty(BaseModel):
    statement: str
    evidence_ids: list[str]
    materiality: ReasoningMateriality


class ReasoningOption(BaseModel):
    title: str
    benefit: str
    sacrifice: str
    risks: list[str]
    preconditions: list[str]


class ReasoningBrief(BaseModel):
    mission: str
    facts: list[ReasoningFact]
    assumptions: list[ReasoningAssumption]
    constraints: list[ReasoningConstraint]
    contradictions: list[ReasoningContradiction]
    uncertainties: list[ReasoningUncertainty]
    options: list[ReasoningOption]
    recommended_next_action: str
    confidence: ReasoningConfidence
    required_response: ReasoningResponse


class ReasoningValidation(BaseModel):
    status: ReasoningValidationStatus
    evidence_coverage: float = Field(ge=0, le=1)
    issues: list[str]


class Finding(BaseModel):
    code: str
    effect: FindingEffect
    message: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None
    policy_id: str


class AuditEvent(BaseModel):
    timestamp: str
    node: str
    action: str
    status: str
    detail: str = ""

    @classmethod
    def now(cls, node: str, action: str, status: str, detail: str = "") -> "AuditEvent":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node=node,
            action=action,
            status=status,
            detail=detail,
        )


class ReviewResult(BaseModel):
    quote: QuoteDraft
    gate: GateDecision
    findings: list[Finding]
    retrieved_policies: list[PolicyDocument]
    summary: str
    audit_trail: list[AuditEvent]
    report_integrity: bool
    reasoning_brief: ReasoningBrief | None
    reasoning_validation: ReasoningValidation


class DraftRequest(BaseModel):
    quote_id: str
    request_text: str = Field(min_length=1, max_length=12_000)
    default_currency: str = "EUR"


class DraftingResult(BaseModel):
    quote: QuoteDraft
    net_total_source: NetTotalSource


class DraftAndReviewResult(BaseModel):
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
