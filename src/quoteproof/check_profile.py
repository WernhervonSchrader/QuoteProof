"""Check a tenant profile and, optionally, its ERP connection.

    python -m quoteproof.check_profile example-sql-3tier
    python -m quoteproof.check_profile example-sql-3tier --sku 4711 --customer-id K-100

Prints what was loaded and what the ERP returned. Never prints secrets.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from .erp import build_adapter
from .erp.base import collect_evidence
from .models import QuoteDraft, QuoteItem
from .profile import ProfileError, load_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quoteproof.check_profile")
    parser.add_argument("profile", nargs="?", default=None)
    parser.add_argument("--sku", action="append", default=[], help="Item number to look up")
    parser.add_argument("--customer-id")
    parser.add_argument("--customer-name")
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.profile)
        adapter = build_adapter(profile.erp.adapter, profile.erp.options)
        entities = (
            profile.restricted_parties.load_entities() if profile.restricted_parties else ()
        )
    except (ProfileError, ValueError) as exc:
        print(f"PROFILE ERROR: {exc}")
        return 2

    print(f"Profile:      {profile.profile_id} - {profile.description}")
    print(f"Currencies:   {', '.join(profile.rules.permitted_currencies())}")
    for name, provenance in sorted(profile.rules.provenance.items()):
        owner = (
            f" by {provenance.confirmed_by} on {provenance.confirmed_on}"
            if provenance.confirmed_by
            else ""
        )
        print(f"Rule:         {name}: {provenance.status.value}{owner}")
    print(f"Restricted:   {len(entities)} entries")
    print(f"ERP adapter:  {profile.erp.adapter} (required: {profile.erp.required})")

    if adapter is None or not (args.sku or args.customer_id or args.customer_name):
        print("ERP lookup:   skipped (no adapter, or no --sku/--customer given)")
        return 0

    probe = QuoteDraft(
        quote_id="CHECK",
        customer=args.customer_name,
        customer_id=args.customer_id,
        items=[
            QuoteItem(
                sku=sku, description="check", quantity=Decimal("1"), unit_price=Decimal("0")
            )
            for sku in args.sku
        ],
    )
    evidence = collect_evidence(adapter, probe)
    if evidence is None or evidence.status != "ok":
        print(f"ERP lookup:   FAILED - {evidence.error if evidence else 'no adapter'}")
        return 1
    print(
        f"Customer:     {evidence.customer.model_dump(exclude_none=True) if evidence.customer else 'not found'}"
    )
    for sku, item in evidence.items.items():
        print(f"Item {sku}: {item.model_dump(exclude_none=True)}")
    for sku in evidence.missing_skus:
        print(f"Item {sku}: not found")
    print(f"Known customer names: {len(evidence.known_customer_names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
