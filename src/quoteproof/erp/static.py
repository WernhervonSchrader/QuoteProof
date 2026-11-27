"""File-based adapter: ERP exports, fixtures and demos without a live system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ERPCustomer, ERPItem
from .base import ERPUnavailable


class StaticAdapter:
    def __init__(self, data: dict[str, Any], label: str = "static") -> None:
        self.adapter_id = label
        self._items = {
            str(item["sku"]): item for item in data.get("items", [])
        }
        self._customers = list(data.get("customers", []))

    @classmethod
    def from_file(cls, path: str | Path, label: str | None = None) -> "StaticAdapter":
        file = Path(path)
        if not file.is_file():
            raise ERPUnavailable(f"ERP export not found: {file.name}")
        return cls(json.loads(file.read_text("utf-8")), label=label or f"static:{file.name}")

    def items(self, skus: list[str]) -> dict[str, ERPItem]:
        return {
            sku: ERPItem(**self._items[sku], source=f"{self.adapter_id} item {sku}")
            for sku in skus
            if sku in self._items
        }

    def customer(self, customer_id: str | None, name: str | None) -> ERPCustomer | None:
        for record in self._customers:
            if customer_id and str(record.get("customer_id")) == customer_id:
                return ERPCustomer(**record, source=f"{self.adapter_id} customer {customer_id}")
        for record in self._customers:
            if name and str(record.get("name", "")).casefold() == name.casefold():
                return ERPCustomer(**record, source=f"{self.adapter_id} customer {name}")
        return None

    def customer_names(self) -> list[str]:
        return [str(record["name"]) for record in self._customers if record.get("name")]
