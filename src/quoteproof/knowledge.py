from __future__ import annotations

import json
from pathlib import Path

from .models import PolicyDocument, QuoteDraft


POLICY_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "policies.json"


def load_policy_pack() -> list[PolicyDocument]:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return [PolicyDocument.model_validate(item) for item in raw]


def retrieve_policies(quote: QuoteDraft) -> list[PolicyDocument]:
    """Retrieve only approved policy cards relevant to the quotation.

    This Gate 2 retriever is deterministic and local. It is intentionally not
    presented as a live sanctions or export-control data connection.
    """
    required_tags = {"quote", "sanctions"}
    if quote.discount_rate > 0:
        required_tags.add("approval")
    if quote.controlled_goods or quote.destination_country != quote.customer_country:
        required_tags.add("export")
    if quote.batch_pure_required:
        required_tags.add("quality")
    return [
        policy
        for policy in load_policy_pack()
        if required_tags.intersection(policy.tags)
    ]

