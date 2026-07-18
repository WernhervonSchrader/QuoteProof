from __future__ import annotations

from langgraph.graph import END, StateGraph

from .models import (
    AuditEvent,
    BusinessRules,
    FindingEffect,
    GateDecision,
    QuoteDraft,
    QuoteState,
    ReviewResult,
)
from .validators import (
    validate_currency,
    validate_discount,
    validate_required_fields,
    validate_total,
)


def _event(node: str, action: str, status: str, detail: str = "") -> AuditEvent:
    return AuditEvent.now(node=node, action=action, status=status, detail=detail)


class QuoteReviewPipeline:
    """LangGraph pipeline in which deterministic validators own routing authority."""

    def __init__(self, rules: BusinessRules | None = None) -> None:
        self.rules = rules or BusinessRules()
        self.graph = self._build()

    def ingest(self, state: QuoteState) -> dict:
        audit = state["audit_trail"] + [
            _event("ingest", "accept_structured_quote", "OK", state["quote"].quote_id)
        ]
        return {"audit_trail": audit}

    def validate(self, state: QuoteState) -> dict:
        quote, rules = state["quote"], state["rules"]
        findings = [
            *validate_required_fields(quote, rules),
            *validate_currency(quote, rules),
            *validate_total(quote, rules),
            *validate_discount(quote, rules),
        ]
        audit = state["audit_trail"] + [
            _event(
                "validate",
                "run_deterministic_controls",
                "FAIL" if findings else "OK",
                ",".join(f.code for f in findings) or "no_findings",
            )
        ]
        return {"findings": findings, "audit_trail": audit}

    def decide_gate(self, state: QuoteState) -> dict:
        effects = {finding.effect for finding in state["findings"]}
        if FindingEffect.BLOCK in effects:
            gate = GateDecision.BLOCKED
        elif FindingEffect.REVIEW in effects:
            gate = GateDecision.REQUIRES_HUMAN_REVIEW
        else:
            gate = GateDecision.PASS
        audit = state["audit_trail"] + [
            _event("gate", "apply_fail_closed_precedence", gate.value)
        ]
        return {"gate": gate, "audit_trail": audit}

    def generate_report(self, state: QuoteState) -> dict:
        gate = state["gate"]
        assert gate is not None
        if gate is GateDecision.PASS:
            summary = "Quotation passed all configured deterministic controls."
        elif gate is GateDecision.REQUIRES_HUMAN_REVIEW:
            summary = "Quotation requires an authorised human review before release."
        else:
            summary = "Quotation is blocked because at least one hard control failed."
        audit = state["audit_trail"] + [
            _event("report", "render_summary_from_gate", "OK", gate.value)
        ]
        return {"summary": summary, "audit_trail": audit}

    def validate_report_integrity(self, state: QuoteState) -> dict:
        gate = state["gate"]
        expected_phrase = {
            GateDecision.PASS: "passed",
            GateDecision.REQUIRES_HUMAN_REVIEW: "human review",
            GateDecision.BLOCKED: "blocked",
        }[gate]
        integrity = expected_phrase in state["summary"].lower()
        audit = state["audit_trail"] + [
            _event(
                "report_integrity",
                "compare_report_to_gate",
                "OK" if integrity else "FAIL",
                gate.value,
            )
        ]
        return {"report_integrity": integrity, "audit_trail": audit}

    def _build(self):
        graph = StateGraph(QuoteState)
        graph.add_node("ingest", self.ingest)
        graph.add_node("validate", self.validate)
        graph.add_node("gate", self.decide_gate)
        graph.add_node("report", self.generate_report)
        graph.add_node("report_integrity", self.validate_report_integrity)
        graph.set_entry_point("ingest")
        graph.add_edge("ingest", "validate")
        graph.add_edge("validate", "gate")
        graph.add_edge("gate", "report")
        graph.add_edge("report", "report_integrity")
        graph.add_edge("report_integrity", END)
        return graph.compile()

    def run(self, quote: QuoteDraft) -> ReviewResult:
        initial: QuoteState = {
            "quote": quote,
            "rules": self.rules,
            "findings": [],
            "gate": None,
            "summary": "",
            "audit_trail": [],
            "report_integrity": False,
        }
        result = self.graph.invoke(initial)
        return ReviewResult.model_validate(result)

