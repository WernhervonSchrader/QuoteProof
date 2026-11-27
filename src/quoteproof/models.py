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
    revision: int = Field(default=1, ge=1)
    customer: str | None = None
    customer_id: str | None = None
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
    customer_document: str | None = Field(
        default=None,
        max_length=50_000,
        description="The customer-facing quotation text exactly as it would be sent.",
    )

    def calculated_total(self) -> Decimal:
        subtotal = sum((item.line_total for item in self.items), Decimal("0"))
        return (subtotal * (Decimal("1") - self.discount_rate)).quantize(Decimal("0.01"))


class RuleStatus(str, Enum):
    CONFIRMED = "confirmed"
    PLACEHOLDER = "placeholder"


class RuleProvenance(BaseModel):
    """Who set a business rule, and whether it is confirmed or a placeholder."""

    status: RuleStatus = RuleStatus.CONFIRMED
    confirmed_by: str | None = None
    confirmed_on: str | None = None
    note: str | None = None


class BusinessRules(BaseModel):
    currency: str = "EUR"
    allowed_currencies: tuple[str, ...] = ()
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


class OutboundRules(BaseModel):
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


class ERPItem(BaseModel):
    sku: str
    description: str | None = None
    list_price: Decimal | None = None
    cost_floor: Decimal | None = None
    currency: str | None = None
    controlled_goods: bool | None = None
    export_classification: str | None = None
    blocked_for_sale: bool = False
    source: str


class ERPCustomer(BaseModel):
    customer_id: str | None = None
    name: str
    country: str | None = None
    blocked: bool = False
    credit_hold: bool = False
    source: str


class ERPEvidence(BaseModel):
    """A read-only snapshot of what the ERP said, with the source of each record."""

    adapter: str
    status: str
    customer: ERPCustomer | None = None
    items: dict[str, ERPItem] = Field(default_factory=dict)
    missing_skus: list[str] = Field(default_factory=list)
    known_customer_names: list[str] = Field(default_factory=list)
    error: str | None = None


class ApprovalRecord(BaseModel):
    """A human release, bound to the exact decision basis it was given on."""

    approved_by: str = Field(min_length=1)
    approved_at: str
    decision_basis_hash: str = Field(min_length=64, max_length=64)


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
    profile_id: str = "default"
    erp_evidence: ERPEvidence | None = None
    decision_basis_hash: str = ""
    rule_provenance: dict[str, RuleProvenance] = Field(default_factory=dict)


class RevisionReviewRequest(BaseModel):
    quote: QuoteDraft
    previous: QuoteDraft | None = None
    approval: ApprovalRecord | None = None


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
    previous: QuoteDraft | None
    approval: ApprovalRecord | None
    erp_evidence: ERPEvidence | None
    decision_basis_hash: str
