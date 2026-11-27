import sqlite3
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from quoteproof.erp import build_adapter, collect_evidence, register_adapter
from quoteproof.erp.base import ERPUnavailable
from quoteproof.erp.sql import (
    QuerySpec,
    SQLAdapter,
    SQLConfigError,
    check_read_only,
    translate_placeholders,
)
from quoteproof.erp.static import StaticAdapter
from quoteproof.graph import QuoteReviewPipeline
from quoteproof.models import (
    ApprovalRecord,
    BusinessRules,
    ERPEvidence,
    FindingEffect,
    GateDecision,
    OutboundRules,
    QuoteDraft,
    QuoteItem,
)
from quoteproof.profile import ProfileError, load_profile, parse_profile
from quoteproof.scenarios import load_scenario
from quoteproof.validators import (
    decision_basis_hash,
    normalise_party_name,
    screen_restricted_parties,
    validate_against_erp,
    validate_outbound_document,
    validate_revision,
)


def codes(findings):
    return [finding.code for finding in findings]


def quote(**overrides) -> QuoteDraft:
    base = {
        "quote_id": "Q-1",
        "customer": "Acme Manufacturing GmbH",
        "customer_country": "DE",
        "destination_country": "DE",
        "currency": "EUR",
        "items": [
            {"sku": "GB-4471", "description": "Planetary gearbox 40:1", "quantity": "4", "unit_price": "1850.00"}
        ],
        "discount_rate": "0",
        "net_total": "7400.00",
        "payment_terms": "30 days net",
        "valid_until": "2026-12-31",
    }
    base.update(overrides)
    return QuoteDraft.model_validate(base)


@pytest.fixture
def erp() -> StaticAdapter:
    return StaticAdapter.from_file("demo_erp/export.json", label="test-erp")


# --- Profiles -----------------------------------------------------------------


def test_default_profile_keeps_demo_behaviour() -> None:
    profile = load_profile("default")
    assert profile.rules.permitted_currencies() == ("EUR",)
    assert profile.erp.adapter == "none"
    result = QuoteReviewPipeline(profile=profile).run(load_scenario("pass"))
    assert result.gate is GateDecision.PASS


def test_placeholder_rule_routes_to_review() -> None:
    profile = parse_profile(
        {"rules": {"maximum_discount_without_approval": {"value": "0.2", "status": "placeholder"}}},
        "t",
    )
    result = QuoteReviewPipeline(profile=profile).run(load_scenario("pass"))
    assert result.gate is GateDecision.REQUIRES_HUMAN_REVIEW
    assert "QP-RULE-001" in codes(result.findings)
    assert result.rule_provenance["maximum_discount_without_approval"].status.value == "placeholder"


def test_unknown_rule_and_missing_profile_fail_loudly() -> None:
    with pytest.raises(ProfileError):
        parse_profile({"rules": {"maximum_discount": "0.2"}}, "t")
    with pytest.raises(ProfileError):
        load_profile("does-not-exist")


def test_several_currencies_can_be_permitted() -> None:
    profile = parse_profile({"rules": {"allowed_currencies": ["EUR", "CHF"]}}, "t")
    result = QuoteReviewPipeline(profile=profile).run(
        load_scenario("pass").model_copy(update={"currency": "CHF"})
    )
    assert "QP-CUR-001" not in codes(result.findings)


# --- Generic SQL adapter --------------------------------------------------------


def make_erp_db(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE qp_v_items (ArtikelNr TEXT, Bezeichnung TEXT, VKPreis TEXT,
            Preisuntergrenze TEXT, Waehrung TEXT, Exportkontrolle TEXT, Gesperrt TEXT);
        CREATE TABLE qp_v_customers (KundenNr TEXT, Name1 TEXT, Land TEXT,
            Liefersperre INTEGER, Kreditsperre INTEGER, Aktiv INTEGER);
        INSERT INTO qp_v_items VALUES ('GB-4471', 'Planetengetriebe', '1.850,00', '1240,00', 'EUR', 'N', 'N');
        INSERT INTO qp_v_items VALUES ('SV-200', 'Servoregler', '2400.00', '1610.00', 'EUR', 'J', 'N');
        INSERT INTO qp_v_customers VALUES ('K-1', 'Acme Manufacturing GmbH', 'DE', 0, 0, 1);
        INSERT INTO qp_v_customers VALUES ('K-2', 'Nordwerk Antriebstechnik AG', 'DE', 0, 1, 1);
        INSERT INTO qp_v_customers VALUES ('K-3', 'Nordwerk Antriebstechnik AG', 'AT', 0, 0, 0);
        """
    )
    conn.commit()
    conn.close()


SQL_OPTIONS = {
    "driver": "sqlite3",
    "connection_env": "TEST_ERP_DSN",
    "label": "unknown-3tier-erp",
    "queries": {
        "item": {
            "sql": "SELECT ArtikelNr, Bezeichnung, VKPreis, Preisuntergrenze, Waehrung, Exportkontrolle, Gesperrt FROM qp_v_items WHERE ArtikelNr = :sku",
            "columns": {
                "sku": "ArtikelNr",
                "description": "Bezeichnung",
                "list_price": "VKPreis",
                "cost_floor": "Preisuntergrenze",
                "currency": "Waehrung",
                "controlled_goods": "Exportkontrolle",
                "blocked_for_sale": "Gesperrt",
            },
        },
        "customer_by_name": {
            "sql": "SELECT KundenNr, Name1, Land, Liefersperre, Kreditsperre FROM qp_v_customers WHERE Name1 = :name",
            "columns": {
                "customer_id": "KundenNr",
                "name": "Name1",
                "country": "Land",
                "blocked": "Liefersperre",
                "credit_hold": "Kreditsperre",
            },
        },
        "customer_names": {
            "sql": "SELECT Name1 FROM qp_v_customers WHERE Aktiv = 1",
            "columns": {"name": "Name1"},
        },
    },
}


def test_sql_adapter_reads_an_unknown_erp_through_its_data_tier(tmp_path, monkeypatch) -> None:
    db = tmp_path / "erp.db"
    make_erp_db(db)
    monkeypatch.setenv("TEST_ERP_DSN", str(db))
    adapter = build_adapter("sql", SQL_OPTIONS)

    evidence = collect_evidence(
        adapter,
        quote(items=[
            {"sku": "GB-4471", "description": "x", "quantity": "1", "unit_price": "1850"},
            {"sku": "SV-200", "description": "y", "quantity": "1", "unit_price": "2400"},
            {"sku": "MISSING", "description": "z", "quantity": "1", "unit_price": "1"},
        ]),
    )
    assert evidence.status == "ok"
    gearbox = evidence.items["GB-4471"]
    assert gearbox.list_price == Decimal("1850.00")  # German "1.850,00"
    assert gearbox.cost_floor == Decimal("1240.00")
    assert gearbox.controlled_goods is False
    assert evidence.items["SV-200"].controlled_goods is True  # "J"
    assert evidence.missing_skus == ["MISSING"]
    assert evidence.customer.customer_id == "K-1"
    assert "unknown-3tier-erp" in gearbox.source
    assert "Nordwerk Antriebstechnik AG" in evidence.known_customer_names


def test_sql_adapter_fails_closed_on_ambiguous_customer(tmp_path, monkeypatch) -> None:
    db = tmp_path / "erp.db"
    make_erp_db(db)
    monkeypatch.setenv("TEST_ERP_DSN", str(db))
    adapter = build_adapter("sql", SQL_OPTIONS)
    evidence = collect_evidence(adapter, quote(customer="Nordwerk Antriebstechnik AG"))
    assert evidence.status == "unavailable"
    findings = validate_against_erp(quote(), evidence, BusinessRules(), erp_required=True)
    assert codes(findings) == ["QP-ERP-001"]
    assert findings[0].effect is FindingEffect.REVIEW


def test_sql_adapter_without_connection_or_driver_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("TEST_ERP_DSN", raising=False)
    evidence = collect_evidence(build_adapter("sql", SQL_OPTIONS), quote())
    assert evidence.status == "unavailable"
    assert "TEST_ERP_DSN" in evidence.error

    no_driver = build_adapter("sql", {**SQL_OPTIONS, "driver": "not_an_installed_driver"})
    monkeypatch.setenv("TEST_ERP_DSN", "x")
    evidence = collect_evidence(no_driver, quote())
    assert evidence.status == "unavailable"
    assert "not installed" in evidence.error


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE items SET price = 0",
        "SELECT * FROM items; DROP TABLE items",
        "SELECT * FROM items -- hidden",
        "SELECT * INTO copy FROM items",
        "WITH x AS (DELETE FROM items RETURNING *) SELECT * FROM x",
        "EXEC sp_who",
        "",
    ],
)
def test_only_read_only_queries_are_accepted(sql) -> None:
    with pytest.raises(SQLConfigError):
        check_read_only(sql)


def test_read_only_check_is_enforced_when_the_profile_loads() -> None:
    with pytest.raises(SQLConfigError):
        SQLAdapter(queries={"item": QuerySpec(sql="DELETE FROM items WHERE sku = :sku")})


def test_nolock_hint_and_casts_are_allowed() -> None:
    check_read_only("SELECT a FROM items WITH (NOLOCK) WHERE sku = :sku")
    sql, params = translate_placeholders("SELECT a::text FROM t WHERE sku = :sku", "qmark", {"sku": "A"})
    assert sql == "SELECT a::text FROM t WHERE sku = ?"
    assert params == ["A"]


@pytest.mark.parametrize(
    "style, expected_sql, expected_params",
    [
        ("qmark", "SELECT * FROM t WHERE a = ? AND b = ?", ["1", "2"]),
        ("numeric", "SELECT * FROM t WHERE a = :1 AND b = :2", ["1", "2"]),
        ("named", "SELECT * FROM t WHERE a = :sku AND b = :name", {"sku": "1", "name": "2"}),
        ("format", "SELECT * FROM t WHERE a = %s AND b = %s", ["1", "2"]),
        ("pyformat", "SELECT * FROM t WHERE a = %(sku)s AND b = %(name)s", {"sku": "1", "name": "2"}),
    ],
)
def test_placeholders_follow_the_driver_paramstyle(style, expected_sql, expected_params) -> None:
    sql, params = translate_placeholders(
        "SELECT * FROM t WHERE a = :sku AND b = :name", style, {"sku": "1", "name": "2"}
    )
    assert sql == expected_sql
    assert params == expected_params


def test_custom_adapters_can_be_registered(erp) -> None:
    register_adapter("in-memory-test", lambda options: erp)
    assert build_adapter("in-memory-test", {}) is erp
    with pytest.raises(ValueError):
        build_adapter("no-such-erp", {})


# --- ERP-backed controls ----------------------------------------------------------


def test_price_below_erp_floor_blocks(erp) -> None:
    q = quote(discount_rate="0.35", net_total="4810.00")
    rules = BusinessRules(maximum_discount_without_approval=Decimal("0.5"))
    findings = validate_against_erp(q, collect_evidence(erp, q), rules, erp_required=True)
    assert "QP-PRICE-001" in codes(findings)
    assert next(f for f in findings if f.code == "QP-PRICE-001").effect is FindingEffect.BLOCK


def test_minimum_margin_is_added_to_the_floor(erp) -> None:
    q = quote(discount_rate="0.30", net_total="5180.00")  # 1295.00 net per unit
    evidence = collect_evidence(erp, q)
    assert "QP-PRICE-001" not in codes(validate_against_erp(q, evidence, BusinessRules(), True))
    strict = BusinessRules(minimum_margin_over_cost=Decimal("0.10"))  # floor 1364.00
    assert "QP-PRICE-001" in codes(validate_against_erp(q, evidence, strict, True))


def test_list_price_deviation_and_unknown_item_need_review(erp) -> None:
    q = quote(items=[
        {"sku": "GB-4471", "description": "x", "quantity": "1", "unit_price": "2100.00"},
        {"sku": "FANTASY-1", "description": "invented", "quantity": "1", "unit_price": "10"},
    ], net_total="2110.00")
    findings = validate_against_erp(q, collect_evidence(erp, q), BusinessRules(), True)
    assert {"QP-PRICE-002", "QP-ERP-002"} <= set(codes(findings))
    assert all(f.effect is FindingEffect.REVIEW for f in findings)


def test_erp_export_flag_overrides_the_quotation(erp) -> None:
    q = quote(items=[{"sku": "SV-200", "description": "Servo drive", "quantity": "1", "unit_price": "2400"}],
              net_total="2400.00", controlled_goods=False)
    findings = validate_against_erp(q, collect_evidence(erp, q), BusinessRules(), True)
    assert "QP-EXPORT-002" in codes(findings)


def test_blocked_customer_blocks_and_credit_hold_reviews(erp) -> None:
    blocked = quote(customer="Old Account Trading GmbH")
    assert "QP-ERP-004" in codes(validate_against_erp(blocked, collect_evidence(erp, blocked), BusinessRules(), True))
    held = quote(customer="Helvetia Precision SA")
    assert "QP-ERP-005" in codes(validate_against_erp(held, collect_evidence(erp, held), BusinessRules(), True))


def test_blocked_item_and_foreign_currency_price(erp) -> None:
    q = quote(items=[{"sku": "LEGACY-07", "description": "Encoder", "quantity": "1", "unit_price": "310"}],
              net_total="310.00", currency="CHF")
    found = codes(validate_against_erp(q, collect_evidence(erp, q), BusinessRules(), True))
    assert "QP-ERP-006" in found
    assert "QP-PRICE-003" in found


def test_required_erp_without_adapter_needs_review() -> None:
    assert codes(validate_against_erp(quote(), None, BusinessRules(), erp_required=True)) == ["QP-ERP-001"]
    assert validate_against_erp(quote(), None, BusinessRules(), erp_required=False) == []


# --- Outbound document check -----------------------------------------------------


def test_internal_language_in_the_customer_document_blocks() -> None:
    q = quote(customer_document="Angebot 4711. Bei dieser Marge ist noch Luft für Nachlass.")
    findings = validate_outbound_document(q, OutboundRules(), None)
    assert codes(findings) == ["QP-OUT-001"]
    assert findings[0].actual == "marge"


def test_word_boundaries_avoid_false_alarms() -> None:
    q = quote(customer_document="International shipping, Interne Anforderungen erfüllt? Yes. Margins of the sheet: 20 mm.")
    assert validate_outbound_document(q, OutboundRules(forbidden_terms=("internal", "margin")), None) == []


def test_internal_cost_figure_and_other_customer_names_block(erp) -> None:
    q = quote(customer_document=(
        "Planetengetriebe 40:1 zu 1.850,00 EUR. Einstand bei uns 1.240,00 EUR – "
        "wie schon bei Nordwerk Antriebstechnik AG geliefert."
    ))
    findings = validate_outbound_document(q, OutboundRules(forbidden_terms=()), collect_evidence(erp, q))
    assert codes(findings) == ["QP-OUT-002", "QP-OUT-003"]
    assert findings[1].actual == "Nordwerk Antriebstechnik AG"


def test_addressee_name_and_list_price_are_allowed(erp) -> None:
    q = quote(customer_document="Sehr geehrte Damen und Herren der Acme Manufacturing GmbH, Preis 1.850,00 EUR.")
    assert validate_outbound_document(q, OutboundRules(), collect_evidence(erp, q)) == []


# --- Revisions and approvals -----------------------------------------------------


def test_price_drop_with_unchanged_scope_means_margin_moved() -> None:
    first = quote()
    counter = quote(revision=2, items=[
        {"sku": "GB-4471", "description": "Planetary gearbox 40:1", "quantity": "4", "unit_price": "1700.00"}
    ], net_total="6800.00")
    findings = validate_revision(counter, first, None, "x" * 64)
    assert codes(findings) == ["QP-REV-001"]


def test_scope_change_is_not_reported_as_margin_move() -> None:
    first = quote()
    smaller = quote(revision=2, items=[
        {"sku": "GB-4471", "description": "Planetary gearbox 40:1", "quantity": "2", "unit_price": "1850.00"}
    ], net_total="3700.00")
    assert validate_revision(smaller, first, None, "x" * 64) == []


def test_revision_number_must_increase_and_belong_to_the_same_quote() -> None:
    assert codes(validate_revision(quote(), quote(), None, "x" * 64)) == ["QP-REV-002"]
    assert codes(validate_revision(quote(quote_id="Q-2", revision=2), quote(), None, "x" * 64)) == ["QP-REV-003"]


def test_approval_lapses_when_anything_material_changes() -> None:
    rules = BusinessRules()
    original = quote()
    basis = decision_basis_hash(original, rules, "default")
    approval = ApprovalRecord(approved_by="M. Muster", approved_at="2026-11-27T10:00:00Z", decision_basis_hash=basis)
    assert validate_revision(original, None, approval, basis) == []

    for change in (
        {"payment_terms": "60 days net"},
        {"customer_document": "New wording"},
        {"discount_rate": "0.02", "net_total": "7252.00"},
    ):
        changed = original.model_copy(update=change)
        new_basis = decision_basis_hash(QuoteDraft.model_validate(changed.model_dump()), rules, "default")
        assert new_basis != basis
        assert codes(validate_revision(changed, None, approval, new_basis)) == ["QP-APPROVAL-001"]

    stricter = BusinessRules(maximum_discount_without_approval=Decimal("0.05"))
    assert decision_basis_hash(original, stricter, "default") != basis


# --- Restricted-party screening --------------------------------------------------


def test_legal_form_and_punctuation_do_not_hide_a_match() -> None:
    assert normalise_party_name("Restricted Entity Example Ltd.") == normalise_party_name(
        "RESTRICTED ENTITY EXAMPLE LIMITED"
    )
    findings = screen_restricted_parties(
        "Restricted Entity Example Limited", ("Restricted Entity Example Ltd",), "POL-SANCTIONS-001"
    )
    assert codes(findings) == ["QP-SANCTIONS-001"]


def test_near_match_goes_to_review_and_unrelated_names_pass() -> None:
    near = screen_restricted_parties(
        "Restricted Entitiy Exampel GmbH", ("Restricted Entity Example Ltd",), "POL-SANCTIONS-001"
    )
    assert codes(near) == ["QP-SANCTIONS-002"]
    assert near[0].effect is FindingEffect.REVIEW
    assert screen_restricted_parties("Acme Manufacturing GmbH", ("Restricted Entity Example Ltd",), "P") == []


# --- End to end with an ERP-backed profile ----------------------------------------


def test_erp_profile_end_to_end_is_traceable() -> None:
    pipeline = QuoteReviewPipeline(profile=load_profile("demo-erp"))
    clean = pipeline.run(load_scenario("pass"))
    assert clean.gate is GateDecision.PASS
    assert clean.erp_evidence.status == "ok"
    assert len(clean.decision_basis_hash) == 64
    assert [e.status for e in clean.audit_trail if e.node == "erp_lookup"] == ["OK"]

    risky = pipeline.run(quote(
        customer="Sample Embargoed Trading FZ-E",
        items=[{"sku": "SV-200", "description": "Servo drive", "quantity": "1", "unit_price": "1500"}],
        net_total="1500.00",
        customer_document="Preis inkl. Marge: 1500 EUR",
    ))
    assert risky.gate is GateDecision.BLOCKED
    assert {"QP-SANCTIONS-001", "QP-PRICE-001", "QP-EXPORT-002", "QP-OUT-001"} <= set(codes(risky.findings))
    retrieved = {policy.id for policy in risky.retrieved_policies}
    assert all(finding.policy_id in retrieved for finding in risky.findings)


def test_unreachable_erp_never_passes(tmp_path) -> None:
    class Broken:
        adapter_id = "broken"

        def customer(self, customer_id, name):
            raise ERPUnavailable("timeout")

        def items(self, skus):
            return {}

        def customer_names(self):
            return []

    result = QuoteReviewPipeline(profile=load_profile("demo-erp"), erp=Broken()).run(load_scenario("pass"))
    assert result.gate is GateDecision.REQUIRES_HUMAN_REVIEW
    assert "QP-ERP-001" in codes(result.findings)


def test_api_exposes_profile_without_secrets_and_reviews_revisions() -> None:
    from quoteproof.api import app

    client = TestClient(app)
    profile = client.get("/profile").json()
    assert profile["profile_id"] == "default"
    assert "connection_env" not in str(profile)

    first = load_scenario("pass")
    second = first.model_copy(update={"revision": 2, "discount_rate": Decimal("0.15"), "net_total": Decimal("1700.00")})
    response = client.post(
        "/review/revision",
        json={"quote": second.model_dump(mode="json"), "previous": first.model_dump(mode="json")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gate"] == "REQUIRES_HUMAN_REVIEW"
    assert "QP-REV-001" in [finding["code"] for finding in body["findings"]]


@pytest.mark.parametrize(
    "spelling",
    ["Sample Embargoed Trading FZ-E", "Sample Embargoed Trading F.Z.E.", "SAMPLE-EMBARGOED TRADING fze"],
)
def test_punctuation_inside_the_legal_form_does_not_hide_a_match(spelling) -> None:
    findings = screen_restricted_parties(spelling, ("Sample Embargoed Trading FZE",), "P")
    assert codes(findings) == ["QP-SANCTIONS-001"]


def test_short_suffixes_do_not_create_false_matches() -> None:
    assert screen_restricted_parties("Atlas Mechanik", ("Atl Mechanik",), "P", review_threshold=0.99) == []
