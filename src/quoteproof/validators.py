from __future__ import annotations

from decimal import Decimal

from .models import BusinessRules, Finding, FindingEffect, PolicyDocument, QuoteDraft


def validate_required_fields(quote: QuoteDraft, rules: BusinessRules) -> list[Finding]:
    findings: list[Finding] = []
    for field in rules.required_fields:
        value = getattr(quote, field)
        if value is None or value == "" or value == []:
            findings.append(
                Finding(
                    code="QP-REQ-001",
                    effect=FindingEffect.BLOCK,
                    message=f"Required field '{field}' is missing.",
                    field=field,
                    policy_id="POL-QUOTE-001",
                )
            )
    return findings


def validate_currency(quote: QuoteDraft, rules: BusinessRules) -> list[Finding]:
    if quote.currency is None or quote.currency == rules.currency:
        return []
    return [
        Finding(
            code="QP-CUR-001",
            effect=FindingEffect.BLOCK,
            message="Quotation currency violates the configured policy.",
            field="currency",
            expected=rules.currency,
            actual=quote.currency,
            policy_id="POL-QUOTE-001",
        )
    ]


def validate_total(quote: QuoteDraft, rules: BusinessRules) -> list[Finding]:
    if quote.net_total is None or not quote.items:
        return []
    expected = quote.calculated_total()
    difference = abs(quote.net_total - expected)
    if difference <= rules.total_tolerance:
        return []
    return [
        Finding(
            code="QP-TOTAL-001",
            effect=FindingEffect.BLOCK,
            message="Declared net total does not match the calculated total.",
            field="net_total",
            expected=str(expected),
            actual=str(quote.net_total.quantize(Decimal("0.01"))),
            policy_id="POL-QUOTE-001",
        )
    ]


def validate_discount(quote: QuoteDraft, rules: BusinessRules) -> list[Finding]:
    if quote.discount_rate <= rules.maximum_discount_without_approval:
        return []
    return [
        Finding(
            code="QP-DISCOUNT-001",
            effect=FindingEffect.REVIEW,
            message="Discount exceeds the automatic approval authority.",
            field="discount_rate",
            expected=f"<= {rules.maximum_discount_without_approval}",
            actual=str(quote.discount_rate),
            policy_id="POL-APPROVAL-001",
        )
    ]


def validate_sanctions(
    quote: QuoteDraft, policies: list[PolicyDocument]
) -> list[Finding]:
    policy = next((item for item in policies if item.id == "POL-SANCTIONS-001"), None)
    if policy is None or quote.customer is None:
        return [
            Finding(
                code="QP-KNOWLEDGE-001",
                effect=FindingEffect.REVIEW,
                message="Sanctions-screening policy was not retrieved.",
                field="customer",
                policy_id="POL-SANCTIONS-001",
            )
        ]
    restricted = [str(name).casefold() for name in policy.data.get("restricted_entities", [])]
    if quote.customer.casefold() not in restricted:
        return []
    return [
        Finding(
            code="QP-SANCTIONS-001",
            effect=FindingEffect.BLOCK,
            message="Exact match in the simulated restricted-party screening fixture.",
            field="customer",
            actual=quote.customer,
            policy_id=policy.id,
        )
    ]


def validate_export_control(quote: QuoteDraft) -> list[Finding]:
    if not quote.controlled_goods or quote.export_license_id:
        return []
    return [
        Finding(
            code="QP-EXPORT-001",
            effect=FindingEffect.BLOCK,
            message="Controlled goods require a documented export authorisation.",
            field="export_license_id",
            expected="documented licence or release",
            actual="missing",
            policy_id="POL-EXPORT-001",
        )
    ]


def validate_batch_purity(quote: QuoteDraft) -> list[Finding]:
    if not quote.batch_pure_required or quote.batch_pure_confirmed is True:
        return []
    if quote.batch_pure_confirmed is False:
        return [
            Finding(
                code="QP-QUALITY-002",
                effect=FindingEffect.BLOCK,
                message="Batch-pure delivery is required but explicitly unavailable.",
                field="batch_pure_confirmed",
                expected="true",
                actual="false",
                policy_id="POL-QUALITY-001",
            )
        ]
    return [
        Finding(
            code="QP-QUALITY-001",
            effect=FindingEffect.REVIEW,
            message="Batch-pure delivery is required but supplier confirmation is missing.",
            field="batch_pure_confirmed",
            expected="documented confirmation",
            actual="unknown",
            policy_id="POL-QUALITY-001",
        )
    ]
