from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlsplit

DEFAULT_ORIGIN = "https://quoteproof-demo.wernhervonschrader.chatgpt.site"


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be an explicit boolean value")


@dataclass(frozen=True, slots=True)
class AppSettings:
    profile: Literal["production", "development"] = "production"
    allowed_origins: tuple[str, ...] = (DEFAULT_ORIGIN,)
    live_draft_enabled: bool = False
    live_draft_kill_switch: bool = True
    max_request_body_bytes: int = 16_384
    provider_timeout_seconds: float = 20.0
    provider_max_retries: int = 1
    provider_max_output_tokens: int = 1_200
    model: str = "gpt-5.6-terra"

    @classmethod
    def from_environment(cls) -> AppSettings:
        raw_origins = os.getenv("QUOTEPROOF_ALLOWED_ORIGINS", DEFAULT_ORIGIN)
        profile = os.getenv("QUOTEPROOF_PROFILE", "production").strip().lower()
        if profile not in {"production", "development"}:
            raise RuntimeError("QUOTEPROOF_PROFILE must be production or development")
        settings = cls(
            profile=cast(Literal["production", "development"], profile),
            allowed_origins=tuple(
                origin.strip() for origin in raw_origins.split(",") if origin.strip()
            ),
            live_draft_enabled=_boolean("QUOTEPROOF_LIVE_DRAFT_ENABLED", False),
            live_draft_kill_switch=_boolean("QUOTEPROOF_LIVE_DRAFT_KILL_SWITCH", True),
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.allowed_origins:
            raise RuntimeError("At least one explicit CORS origin is required")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            is_local_development = (
                self.profile == "development"
                and parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
            )
            if (
                "*" in origin
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or not parsed.hostname
                or (parsed.scheme != "https" and not is_local_development)
            ):
                raise RuntimeError(f"Unsafe CORS origin configuration: {origin!r}")
        if not 1_024 <= self.max_request_body_bytes <= 1_000_000:
            raise RuntimeError("Request body limit is outside the supported range")
        if not 1 <= self.provider_timeout_seconds <= 60:
            raise RuntimeError("Provider timeout is outside the supported range")
        if not 0 <= self.provider_max_retries <= 2:
            raise RuntimeError("Provider retry count is outside the supported range")
        if not 128 <= self.provider_max_output_tokens <= 4_096:
            raise RuntimeError("Provider output limit is outside the supported range")
        if not self.model or len(self.model) > 100:
            raise RuntimeError("Provider model configuration is invalid")
