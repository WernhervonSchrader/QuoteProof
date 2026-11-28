"""Adapter registry. A new ERP is one registered factory, not a code change elsewhere."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import ERPAdapter
from .sql import SQLAdapter
from .static import StaticAdapter

AdapterFactory = Callable[[dict[str, Any]], ERPAdapter]


def _static(options: dict[str, Any]) -> ERPAdapter:
    path = Path(str(options["file"]))
    base_dir = options.get("base_dir")
    if not path.is_absolute() and base_dir:
        path = Path(str(base_dir)) / path
    label = options.get("label")
    return StaticAdapter.from_file(path, label=str(label) if label else None)


def _sql(options: dict[str, Any]) -> ERPAdapter:
    return SQLAdapter.from_options(options)


_REGISTRY: dict[str, AdapterFactory] = {
    "sql": _sql,
    "static": _static,
}


def register_adapter(name: str, factory: AdapterFactory) -> None:
    """Register an adapter for another ERP, e.g. an Odoo JSON-RPC or SAP OData client."""

    _REGISTRY[name] = factory


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def build_adapter(name: str, options: dict[str, Any]) -> ERPAdapter | None:
    if name in {"", "none"}:
        return None
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown ERP adapter '{name}'. Available: {', '.join(available_adapters())}"
        )
    return _REGISTRY[name](options)
