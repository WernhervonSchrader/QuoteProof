from __future__ import annotations

import json
from importlib.resources import files

from .models import QuoteDraft

CASE_DIR = files("quoteproof").joinpath("data", "demo_cases")


def list_scenarios() -> list[str]:
    return sorted(
        path.name.removesuffix(".json")
        for path in CASE_DIR.iterdir()
        if path.name.endswith(".json")
    )


def load_scenario(name: str) -> QuoteDraft:
    if name not in list_scenarios():
        raise KeyError(name)
    payload = CASE_DIR.joinpath(f"{name}.json").read_text(encoding="utf-8")
    return QuoteDraft.model_validate(json.loads(payload))
