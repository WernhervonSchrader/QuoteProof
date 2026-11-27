from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from difflib import SequenceMatcher

from .models import (
    ApprovalRecord,
    BusinessRules,
    ERPEvidence,
    Finding,
    FindingEffect,
    OutboundRules,
    PolicyDocument,
    QuoteDraft,
    RuleStatus,
)


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
    quote: QuoteDraft,
    policies: list[PolicyDocument],
    extra_entities: tuple[str, ...] = (),
    review_threshold: float = 0.88,
    label: str = "simulated restricted-party screening fixture",
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
    entities = tuple(str(name) for name in policy.data.get("restricted_entities", []))
    return screen_restricted_parties(
        quote.customer,
        entities + tuple(extra_entities),
        policy_id=policy.id,
        review_threshold=review_threshold,
        label=label,
    )


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


# --- Profile-driven and ERP-backed controls ---------------------------------


def validate_currency(quote: QuoteDraft, rules: BusinessRules) -> list[Finding]:
    """Currency check against the profile's permitted currencies."""

    permitted = rules.permitted_currencies()
    if quote.currency is None or quote.currency in permitted:
        return []
    return [
        Finding(
            code="QP-CUR-001",
            effect=FindingEffect.BLOCK,
            message="Quotation currency violates the configured policy.",
            field="currency",
            expected=", ".join(permitted),
            actual=quote.currency,
            policy_id="POL-QUOTE-001",
        )
    ]


def validate_rule_provenance(rules: BusinessRules) -> list[Finding]:
    """A placeholder rule may run, but never silently: it routes to review."""

    return [
        Finding(
            code="QP-RULE-001",
            effect=FindingEffect.REVIEW,
            message="A business rule is a placeholder and has not been confirmed.",
            field=name,
            expected="confirmed rule with owner and date",
            actual="placeholder",
            policy_id="POL-PROFILE-001",
        )
        for name, provenance in sorted(rules.provenance.items())
        if provenance.status is RuleStatus.PLACEHOLDER
    ]


_LEGAL_FORMS = {
    "gmbh", "mbh", "ag", "kg", "ohg", "ug", "se", "eg", "ev", "co", "cokg", "kgaa",
    "ltd", "limited", "llc", "inc", "incorporated", "corp", "corporation", "plc",
    "llp", "lp", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "oy", "ab", "as",
    "aps", "kft", "sro", "spzoo", "fze", "fzco", "fzc", "company", "the",
}


def normalise_party_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.casefold().replace("&", " "))
    tokens = [token for token in text.split() if token not in _LEGAL_FORMS]
    return " ".join(tokens)


_SUFFIX_FORMS = tuple(sorted((form for form in _LEGAL_FORMS if len(form) >= 3), key=len, reverse=True))


def compact_party_name(name: str) -> str:
    """Spacing- and punctuation-free form, so 'FZ-E' or 'G.m.b.H.' cannot hide a match."""

    compact = normalise_party_name(name).replace(" ", "")
    changed = True
    while changed:
        changed = False
        for form in _SUFFIX_FORMS:
            if compact.endswith(form) and len(compact) > len(form) + 3:
                compact = compact[: -len(form)]
                changed = True
                break
    return compact


def screen_restricted_parties(
    customer: str | None,
    entities: tuple[str, ...],
    policy_id: str,
    review_threshold: float = 0.88,
    label: str = "restricted-party list",
) -> list[Finding]:
    """Normalised exact match blocks; a close match routes to human review."""

    if not customer or not entities:
        return []
    candidate = normalise_party_name(customer)
    if not candidate:
        return []
    best_name, best_score = None, 0.0
    for entity in entities:
        normalised = normalise_party_name(entity)
        if not normalised:
            continue
        if normalised == candidate or compact_party_name(entity) == compact_party_name(customer):
            return [
                Finding(
                    code="QP-SANCTIONS-001",
                    effect=FindingEffect.BLOCK,
                    message=f"Match in the {label} (legal form and punctuation ignored).",
                    field="customer",
                    expected="no match",
                    actual=customer,
                    policy_id=policy_id,
                )
            ]
        score = SequenceMatcher(None, candidate, normalised).ratio()
        if score > best_score:
            best_name, best_score = entity, score
    if best_score >= review_threshold:
        return [
            Finding(
                code="QP-SANCTIONS-002",
                effect=FindingEffect.REVIEW,
                message=f"Possible match in the {label}; a person must rule it out.",
                field="customer",
                expected=f"no entry similar to '{best_name}'",
                actual=f"{customer} (similarity {best_score:.2f})",
                policy_id=policy_id,
            )
        ]
    return []


def validate_against_erp(
    quote: QuoteDraft,
    evidence: ERPEvidence | None,
    rules: BusinessRules,
    erp_required: bool,
) -> list[Finding]:
    """Check the quotation against what the ERP actually holds. Never guess."""

    if evidence is None:
        if not erp_required:
            return []
        return [
            Finding(
                code="QP-ERP-001",
                effect=FindingEffect.REVIEW,
                message="The profile requires ERP evidence, but no ERP adapter is configured.",
                field="erp",
                policy_id="POL-ERP-001",
            )
        ]
    if evidence.status != "ok":
        return [
            Finding(
                code="QP-ERP-001",
                effect=FindingEffect.REVIEW,
                message="ERP evidence is unavailable; prices and items could not be verified.",
                field="erp",
                actual=evidence.error,
                policy_id="POL-ERP-001",
            )
        ]

    findings: list[Finding] = []
    customer = evidence.customer
    if customer is None and (quote.customer or quote.customer_id):
        findings.append(
            Finding(
                code="QP-ERP-003",
                effect=FindingEffect.REVIEW,
                message="Customer not found in the ERP.",
                field="customer",
                actual=quote.customer_id or quote.customer,
                policy_id="POL-ERP-001",
            )
        )
    elif customer is not None:
        if customer.blocked:
            findings.append(
                Finding(
                    code="QP-ERP-004",
                    effect=FindingEffect.BLOCK,
                    message="Customer is blocked in the ERP.",
                    field="customer",
                    actual=customer.source,
                    policy_id="POL-ERP-001",
                )
            )
        if customer.credit_hold:
            findings.append(
                Finding(
                    code="QP-ERP-005",
                    effect=FindingEffect.REVIEW,
                    message="Customer is on credit hold in the ERP.",
                    field="customer",
                    actual=customer.source,
                    policy_id="POL-ERP-001",
                )
            )

    for sku in evidence.missing_skus:
        findings.append(
            Finding(
                code="QP-ERP-002",
                effect=FindingEffect.REVIEW,
                message="Item not found in the ERP; its price has no system basis.",
                field=f"items[{sku}]",
                actual=sku,
                policy_id="POL-ERP-001",
            )
        )

    erp_controlled = False
    for line in quote.items:
        item = evidence.items.get(line.sku)
        if item is None:
            continue
        field = f"items[{line.sku}]"
        if item.blocked_for_sale:
            findings.append(
                Finding(
                    code="QP-ERP-006",
                    effect=FindingEffect.BLOCK,
                    message="Item is blocked for sale in the ERP.",
                    field=field,
                    actual=item.source,
                    policy_id="POL-ERP-001",
                )
            )
        if item.currency and quote.currency and item.currency != quote.currency:
            findings.append(
                Finding(
                    code="QP-PRICE-003",
                    effect=FindingEffect.REVIEW,
                    message="ERP price currency differs from the quotation currency; no conversion is assumed.",
                    field=field,
                    expected=item.currency,
                    actual=quote.currency,
                    policy_id="POL-PRICE-001",
                )
            )
            continue
        effective = (line.unit_price * (Decimal("1") - quote.discount_rate)).quantize(Decimal("0.0001"))
        if item.cost_floor is not None:
            floor = (item.cost_floor * (Decimal("1") + rules.minimum_margin_over_cost)).quantize(
                Decimal("0.0001")
            )
            if effective < floor:
                findings.append(
                    Finding(
                        code="QP-PRICE-001",
                        effect=FindingEffect.BLOCK,
                        message="Net unit price after discount is below the ERP price floor.",
                        field=field,
                        expected=f">= {floor} ({item.source})",
                        actual=str(effective),
                        policy_id="POL-PRICE-001",
                    )
                )
        if item.list_price is not None and item.list_price > 0:
            deviation = abs(line.unit_price - item.list_price) / item.list_price
            if deviation > rules.list_price_tolerance:
                findings.append(
                    Finding(
                        code="QP-PRICE-002",
                        effect=FindingEffect.REVIEW,
                        message="Quoted unit price deviates from the ERP list price beyond tolerance.",
                        field=field,
                        expected=f"{item.list_price} ± {rules.list_price_tolerance:%} ({item.source})",
                        actual=str(line.unit_price),
                        policy_id="POL-PRICE-001",
                    )
                )
        if item.controlled_goods:
            erp_controlled = True

    if erp_controlled and not quote.controlled_goods and not quote.export_license_id:
        findings.append(
            Finding(
                code="QP-EXPORT-002",
                effect=FindingEffect.BLOCK,
                message="The ERP marks an item as controlled goods, but the quotation does not.",
                field="controlled_goods",
                expected="true, with documented export authorisation",
                actual="false",
                policy_id="POL-EXPORT-001",
            )
        )
    return findings


def _contains_term(text: str, term: str) -> bool:
    pattern = r"(?<![\w])" + re.escape(term.casefold()) + r"(?![\w])"
    return re.search(pattern, text) is not None


def _amount_variants(value: Decimal) -> set[str]:
    quantised = value.quantize(Decimal("0.01"))
    plain = f"{quantised:.2f}"
    integer, fraction = plain.split(".")
    grouped = f"{int(integer):,}"
    variants = {plain, f"{integer},{fraction}", f"{grouped}.{fraction}", f"{grouped.replace(',', '.')},{fraction}"}
    if fraction == "00":
        variants.add(integer)
    return {variant for variant in variants if len(variant.replace(".", "").replace(",", "")) >= 3}


def validate_outbound_document(
    quote: QuoteDraft,
    outbound: OutboundRules,
    evidence: ERPEvidence | None,
) -> list[Finding]:
    """Deterministic leak check on everything the customer will read."""

    parts = [quote.customer_document or "", quote.payment_terms or ""]
    parts.extend(item.description for item in quote.items)
    text = "\n".join(parts).casefold()
    if not text.strip():
        return []

    findings: list[Finding] = []
    leaked_terms = sorted({term for term in outbound.forbidden_terms if _contains_term(text, term)})
    if leaked_terms:
        findings.append(
            Finding(
                code="QP-OUT-001",
                effect=FindingEffect.BLOCK,
                message="Customer-facing text contains internal pricing language.",
                field="customer_document",
                expected="no internal terms",
                actual=", ".join(leaked_terms),
                policy_id="POL-OUTBOUND-001",
            )
        )

    if evidence is not None and evidence.status == "ok":
        if outbound.leak_cost_figures:
            leaked_costs = sorted(
                sku
                for sku, item in evidence.items.items()
                if item.cost_floor is not None
                and any(_contains_term(text, variant) for variant in _amount_variants(item.cost_floor))
            )
            if leaked_costs:
                findings.append(
                    Finding(
                        code="QP-OUT-002",
                        effect=FindingEffect.BLOCK,
                        message="Customer-facing text contains an internal ERP cost figure.",
                        field="customer_document",
                        actual=", ".join(leaked_costs),
                        policy_id="POL-OUTBOUND-001",
                    )
                )
        if outbound.leak_other_customer_names:
            addressee = normalise_party_name(quote.customer or "")
            normalised_text = " " + normalise_party_name(text) + " "
            others = sorted(
                name
                for name in evidence.known_customer_names
                if (normalised := normalise_party_name(name))
                and normalised != addressee
                and len(normalised) >= 4
                and f" {normalised} " in normalised_text
            )
            if others:
                findings.append(
                    Finding(
                        code="QP-OUT-003",
                        effect=FindingEffect.BLOCK,
                        message="Customer-facing text names another customer.",
                        field="customer_document",
                        actual=", ".join(others),
                        policy_id="POL-OUTBOUND-001",
                    )
                )
    return findings


_BASIS_EXCLUDED = {"customer_document"}


def decision_basis_hash(quote: QuoteDraft, rules: BusinessRules, profile_id: str) -> str:
    """Fingerprint of everything a release decision rests on.

    Any change to customer, items, prices, terms, flags or the active rules
    produces a new hash, so an earlier approval no longer covers the quote.
    """

    payload = {
        "profile": profile_id,
        "quote": quote.model_dump(mode="json", exclude=_BASIS_EXCLUDED),
        "document": hashlib.sha256((quote.customer_document or "").encode("utf-8")).hexdigest(),
        "rules": rules.model_dump(mode="json", exclude={"provenance"}),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scope(quote: QuoteDraft) -> list[tuple[str, str]]:
    return sorted((item.sku, str(item.quantity.normalize())) for item in quote.items)


def validate_revision(
    quote: QuoteDraft,
    previous: QuoteDraft | None,
    approval: ApprovalRecord | None,
    basis_hash: str,
) -> list[Finding]:
    """Counter-offers are revisions with a record, and approvals do not carry over."""

    findings: list[Finding] = []
    if previous is not None:
        if previous.quote_id != quote.quote_id:
            findings.append(
                Finding(
                    code="QP-REV-003",
                    effect=FindingEffect.BLOCK,
                    message="The previous version belongs to a different quotation.",
                    field="quote_id",
                    expected=previous.quote_id,
                    actual=quote.quote_id,
                    policy_id="POL-REVISION-001",
                )
            )
            return findings
        if quote.revision <= previous.revision:
            findings.append(
                Finding(
                    code="QP-REV-002",
                    effect=FindingEffect.BLOCK,
                    message="A revision must carry a higher revision number than the version it replaces.",
                    field="revision",
                    expected=f"> {previous.revision}",
                    actual=str(quote.revision),
                    policy_id="POL-REVISION-001",
                )
            )
        if _scope(quote) == _scope(previous) and quote.calculated_total() < previous.calculated_total():
            findings.append(
                Finding(
                    code="QP-REV-001",
                    effect=FindingEffect.REVIEW,
                    message="Price dropped with an unchanged scope: the margin moved.",
                    field="net_total",
                    expected=str(previous.calculated_total()),
                    actual=str(quote.calculated_total()),
                    policy_id="POL-REVISION-001",
                )
            )
    if approval is not None and approval.decision_basis_hash != basis_hash:
        findings.append(
            Finding(
                code="QP-APPROVAL-001",
                effect=FindingEffect.REVIEW,
                message="The recorded approval covered a different decision basis and has lapsed.",
                field="approval",
                expected=approval.decision_basis_hash[:12],
                actual=basis_hash[:12],
                policy_id="POL-REVISION-001",
            )
        )
    return findings
