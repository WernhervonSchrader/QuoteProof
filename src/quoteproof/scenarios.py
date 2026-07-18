from __future__ import annotations

import json
from pathlib import Path

from .models import QuoteDraft


CASE_DIR = Path(__file__).resolve().parents[2] / "demo_cases"


def list_scenarios() -> list[str]:
    return sorted(path.stem for path in CASE_DIR.glob("*.json"))


def load_scenario(name: str) -> QuoteDraft:
    if name not in list_scenarios():
        raise KeyError(name)
    return QuoteDraft.model_validate(json.loads((CASE_DIR / f"{name}.json").read_text()))

