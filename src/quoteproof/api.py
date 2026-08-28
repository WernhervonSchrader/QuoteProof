from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from .config import AppSettings
from .drafting import DraftingError, OpenAIQuoteDrafter, ResponsesClient
from .graph import QuoteReviewPipeline
from .live import (
    DenyAllUsageGuard,
    EnvironmentDemoAccessResolver,
    EnvironmentOpenAISecretResolver,
    SecretResolver,
    UsageDecision,
    UsageGuard,
)
from .models import DraftAndReviewResult, DraftRequest, QuoteDraft, ReviewResult
from .reasoning import OpenAIReasoningAnalyst
from .scenarios import list_scenarios, load_scenario
from .telemetry import emit_operation_log

ClientFactory = Callable[[str], ResponsesClient]


def _safe_provider_error_code(exc: OpenAIError) -> str:
    if isinstance(exc, AuthenticationError):
        return "provider_authentication_failed"
    if isinstance(exc, PermissionDeniedError):
        return "provider_permission_denied"
    if isinstance(exc, RateLimitError):
        return "provider_rate_or_quota_limited"
    if isinstance(exc, BadRequestError):
        return "provider_request_rejected"
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return "provider_unavailable"
    return "provider_error"


def _safe_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "code": code},
    )


def _usage_error(decision: UsageDecision) -> HTTPException:
    mapping = {
        UsageDecision.RATE_LIMITED: (429, "rate_limited"),
        UsageDecision.QUOTA_EXCEEDED: (429, "quota_exceeded"),
        UsageDecision.BUDGET_EXCEEDED: (429, "budget_exceeded"),
        UsageDecision.UNAVAILABLE: (503, "usage_guard_unavailable"),
    }
    status, code = mapping[decision]
    return _safe_http_error(status, code, "Live drafting is not available.")


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, maximum_bytes: int) -> None:
        super().__init__(app)
        self.maximum_bytes = maximum_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > self.maximum_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": {
                                    "message": "Request body is too large.",
                                    "code": "request_too_large",
                                }
                            },
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "detail": {
                                "message": "Request metadata is invalid.",
                                "code": "invalid_content_length",
                            }
                        },
                    )
            body = await request.body()
            if len(body) > self.maximum_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": {
                            "message": "Request body is too large.",
                            "code": "request_too_large",
                        }
                    },
                )
        return await call_next(request)


def _default_client_factory(settings: AppSettings) -> ClientFactory:
    def create(api_key: str) -> ResponsesClient:
        client = OpenAI(
            api_key=api_key,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
        )
        return cast(ResponsesClient, client)

    return create


def create_app(
    *,
    settings: AppSettings | None = None,
    usage_guard: UsageGuard | None = None,
    demo_access_resolver: SecretResolver | None = None,
    provider_secret_resolver: SecretResolver | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    active_settings = settings or AppSettings.from_environment()
    active_settings.validate()
    active_usage_guard = usage_guard or DenyAllUsageGuard()
    active_demo_resolver = demo_access_resolver or EnvironmentDemoAccessResolver()
    active_provider_resolver = provider_secret_resolver or EnvironmentOpenAISecretResolver()
    active_client_factory = client_factory or _default_client_factory(active_settings)

    api = FastAPI(
        title="QuoteProof",
        version="0.1.0",
        description=(
            "Synthetic-data-only quotation governance demonstration. Do not submit "
            "customer, personal, confidential, regulated, or credential data. The "
            "optional live route transfers submitted text and derived context to OpenAI; "
            "it is disabled by default."
        ),
    )
    api.add_middleware(
        RequestBodyLimitMiddleware,
        maximum_bytes=active_settings.max_request_body_bytes,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-QuoteProof-Demo-Key"],
    )
    pipeline = QuoteReviewPipeline()

    @api.middleware("http")
    async def operational_logging(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        started = time.monotonic()
        try:
            response = await call_next(request)
            status = "ok" if response.status_code < 400 else "rejected"
            error_code = "none" if response.status_code < 400 else "request_rejected"
        except Exception:
            duration_ms = round((time.monotonic() - started) * 1_000)
            emit_operation_log(
                component="api",
                status="error",
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                error_code="internal_error",
            )
            raise
        duration_ms = round((time.monotonic() - started) * 1_000)
        emit_operation_log(
            component="api",
            status=status,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            error_code=error_code,
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @api.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "message": "Request validation failed.",
                    "code": "invalid_request",
                }
            },
        )

    @api.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "QuoteProof API",
            "status": "ok",
            "docs": "/docs",
            "decision_scope": "synthetic_demo_only",
        }

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/scenarios")
    def scenarios() -> list[str]:
        return list_scenarios()

    @api.post("/review", response_model=ReviewResult)
    def review(quote: QuoteDraft) -> ReviewResult:
        return pipeline.run(quote)

    @api.post("/review/{scenario}", response_model=ReviewResult)
    def review_scenario(
        scenario: str = Path(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$"),
    ) -> ReviewResult:
        try:
            quote = load_scenario(scenario)
        except KeyError:
            raise _safe_http_error(404, "unknown_scenario", "Unknown scenario.") from None
        return pipeline.run(quote)

    @api.post("/draft-and-review", response_model=DraftAndReviewResult)
    async def draft_and_review(
        request: Request,
        demo_access_code: str | None = Header(
            default=None,
            alias="X-QuoteProof-Demo-Key",
            max_length=256,
        ),
    ) -> DraftAndReviewResult:
        if not active_settings.live_draft_enabled:
            raise _safe_http_error(503, "live_draft_disabled", "Live drafting is disabled.")
        if active_settings.live_draft_kill_switch:
            raise _safe_http_error(503, "live_draft_killed", "Live drafting is disabled.")

        expected_access_code = active_demo_resolver.resolve()
        if expected_access_code is None or len(expected_access_code) < 24:
            raise _safe_http_error(
                503, "access_not_configured", "Live drafting is not available."
            )
        if demo_access_code is None or not hmac.compare_digest(
            demo_access_code, expected_access_code
        ):
            raise _safe_http_error(
                401, "access_denied", "Live drafting access is missing or invalid."
            )

        subject_id = hashlib.sha256(demo_access_code.encode("utf-8")).hexdigest()[:24]
        usage_decision = active_usage_guard.check(subject_id)
        if usage_decision is not UsageDecision.ALLOW:
            raise _usage_error(usage_decision)

        try:
            raw_payload = json.loads((await request.body()).decode("utf-8"))
            if not isinstance(raw_payload, dict):
                raise ValueError
            draft_request = DraftRequest.model_validate(raw_payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
            raise _safe_http_error(
                422, "invalid_request", "Request validation failed."
            ) from None

        provider_key = active_provider_resolver.resolve()
        if provider_key is None:
            raise _safe_http_error(
                503, "provider_not_configured", "Live drafting is not available."
            )

        provider_client = active_client_factory(provider_key)
        drafter = OpenAIQuoteDrafter(
            client=provider_client,
            model=active_settings.model,
            max_output_tokens=active_settings.provider_max_output_tokens,
        )
        try:
            drafted = drafter.draft(draft_request)
            review_result = QuoteReviewPipeline(
                reasoner=OpenAIReasoningAnalyst(
                    client=provider_client,
                    model=active_settings.model,
                    max_output_tokens=active_settings.provider_max_output_tokens,
                )
            ).run(drafted.quote)
        except DraftingError:
            raise _safe_http_error(
                502,
                "structured_draft_missing",
                "The draft could not be generated safely.",
            ) from None
        except OpenAIError as exc:
            raise _safe_http_error(
                502,
                _safe_provider_error_code(exc),
                "The draft could not be generated safely.",
            ) from None
        return DraftAndReviewResult(
            model=drafter.model,
            net_total_source=drafted.net_total_source,
            review=review_result,
        )

    return api


app = create_app()
