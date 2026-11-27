"""Adapter registry. A new ERP is one registered factory, not a code change elsewhere."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .base import ERPAdapter
from .sql import SQLAdapter
from .static import StaticAdapter


AdapterFactory = Callable[[dict[str, Any]], ERPAdapter]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _static(options: dict[str, Any]) -> ERPAdapter:
    path = Path(options["file"])
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return StaticAdapter.from_file(path, label=options.get("label"))


_REGISTRY: dict[str, AdapterFactory] = {
    "sql": SQLAdapter.from_options,
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
        raise ValueError(f"Unknown ERP adapter '{name}'. Available: {', '.join(available_adapters())}")
    return _REGISTRY[name](options)
