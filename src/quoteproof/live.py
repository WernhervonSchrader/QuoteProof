from __future__ import annotations

import os
from enum import StrEnum
from typing import Protocol


class UsageDecision(StrEnum):
    ALLOW = "allow"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNAVAILABLE = "unavailable"


class UsageGuard(Protocol):
    """Request-time interface for a persistent, deployment-wide usage guard."""

    def check(self, subject_id: str) -> UsageDecision: ...


class DenyAllUsageGuard:
    """Safe default when no approved distributed guard has been wired."""

    def check(self, subject_id: str) -> UsageDecision:
        del subject_id
        return UsageDecision.UNAVAILABLE


class SecretResolver(Protocol):
    def resolve(self) -> str | None: ...


class EnvironmentOpenAISecretResolver:
    """Resolve the provider secret only after every earlier request gate passes."""

    def resolve(self) -> str | None:
        value = os.getenv("OPENAI_API_KEY")
        return value if value and not value.isspace() else None


class EnvironmentDemoAccessResolver:
    """Resolve the access secret solely for the access-control gate."""

    def resolve(self) -> str | None:
        value = os.getenv("QUOTEPROOF_DEMO_KEY")
        return value if value and not value.isspace() else None
