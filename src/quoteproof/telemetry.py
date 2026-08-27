from __future__ import annotations

import json
import logging
import re

LOGGER = logging.getLogger("quoteproof.operations")
_SAFE_CODE = re.compile(r"^[a-z0-9_]{1,64}$")


def emit_operation_log(
    *,
    component: str,
    status: str,
    duration_ms: int,
    correlation_id: str,
    error_code: str = "none",
) -> None:
    """Emit only the approved operational metadata allowlist."""

    safe_error = error_code if _SAFE_CODE.fullmatch(error_code) else "internal_error"
    payload = {
        "component": component,
        "status": status,
        "duration_ms": max(0, duration_ms),
        "correlation_id": correlation_id,
        "error_code": safe_error,
    }
    LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
