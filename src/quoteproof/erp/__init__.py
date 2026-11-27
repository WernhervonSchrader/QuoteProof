"""ERP adapters. QuoteProof reads from an ERP; it never writes to one."""

from .base import ERPAdapter, ERPUnavailable, collect_evidence
from .registry import available_adapters, build_adapter, register_adapter

__all__ = [
    "ERPAdapter",
    "ERPUnavailable",
    "available_adapters",
    "build_adapter",
    "collect_evidence",
    "register_adapter",
]
