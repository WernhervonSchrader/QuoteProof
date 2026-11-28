from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import ERPCustomer, ERPEvidence, ERPItem, QuoteDraft


class ERPUnavailable(RuntimeError):
    """The ERP could not be read. Callers fail closed to human review."""


@runtime_checkable
class ERPAdapter(Protocol):
    """The whole contract an ERP has to meet. Read-only by construction.

    Any system fits behind it: a SQL database of a three-tier ERP, a REST or
    JSON-RPC middle tier (Odoo, SAP OData, Business Central), or file exports.
    """

    adapter_id: str

    def customer(self, customer_id: str | None, name: str | None) -> ERPCustomer | None: ...

    def items(self, skus: list[str]) -> dict[str, ERPItem]: ...

    def customer_names(self) -> list[str]: ...


def collect_evidence(adapter: ERPAdapter | None, quote: QuoteDraft) -> ERPEvidence | None:
    """Take one read-only snapshot for a quotation. Errors become evidence, not crashes."""

    if adapter is None:
        return None
    skus = sorted({item.sku for item in quote.items})
    try:
        customer = adapter.customer(quote.customer_id, quote.customer)
        items = adapter.items(skus)
        names = adapter.customer_names()
    except ERPUnavailable as exc:
        return ERPEvidence(adapter=adapter.adapter_id, status="unavailable", error=str(exc))
    except Exception as exc:
        return ERPEvidence(
            adapter=adapter.adapter_id,
            status="unavailable",
            error=f"{type(exc).__name__}: adapter failed",
        )
    return ERPEvidence(
        adapter=adapter.adapter_id,
        status="ok",
        customer=customer,
        items=items,
        missing_skus=[sku for sku in skus if sku not in items],
        known_customer_names=sorted(set(names)),
    )
