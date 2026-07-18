from __future__ import annotations

from decimal import Decimal

from .models import BusinessRules, Finding, FindingEffect, QuoteDraft


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
        )
    ]

