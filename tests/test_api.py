import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from httpx import Request, Response
from openai import APITimeoutError, AuthenticationError

from quoteproof.api import (
    _default_client_factory,
    _safe_provider_error_code,
    app,
    create_app,
)
from quoteproof.config import DEFAULT_ORIGIN, AppSettings
from quoteproof.live import UsageDecision

ACCESS_CODE = "synthetic-access-code-24-chars"
VALID_DRAFT = {"quote_id": "QP-42", "request_text": "Prepare a synthetic quote."}


class SpySecretResolver:
    def __init__(self, value: str | None, events: list[str], name: str) -> None:
        self.value = value
        self.events = events
        self.name = name

    def resolve(self) -> str | None:
        self.events.append(self.name)
        return self.value


class FakeUsageGuard:
    def __init__(self, decision: UsageDecision, events: list[str]) -> None:
        self.decision = decision
        self.events = events

    def check(self, subject_id: str) -> UsageDecision:
        assert len(subject_id) == 24
        assert ACCESS_CODE not in subject_id
        self.events.append("usage")
        return self.decision


class FakeResponses:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=None)


def live_settings(*, killed: bool = False, body_limit: int = 16_384) -> AppSettings:
    return AppSettings(
        allowed_origins=(DEFAULT_ORIGIN,),
        live_draft_enabled=True,
        live_draft_kill_switch=killed,
        max_request_body_bytes=body_limit,
    )


def guarded_app(
    *,
    decision: UsageDecision = UsageDecision.ALLOW,
    provider_key: str | None = None,
    responses: FakeResponses | None = None,
    settings: AppSettings | None = None,
):
    events: list[str] = []
    fake_responses = responses or FakeResponses()

    def client_factory(api_key: str):
        assert api_key == "synthetic-provider-placeholder"  # pragma: allowlist secret
        events.append("client")
        return SimpleNamespace(responses=fake_responses)

    application = create_app(
        settings=settings or live_settings(),
        usage_guard=FakeUsageGuard(decision, events),
        demo_access_resolver=SpySecretResolver(ACCESS_CODE, events, "access_secret"),
        provider_secret_resolver=SpySecretResolver(provider_key, events, "provider_secret"),
        client_factory=client_factory,
    )
    return application, events, fake_responses


def post_live(application, payload=VALID_DRAFT, *, access_code: str = ACCESS_CODE):
    return TestClient(application).post(
        "/draft-and-review",
        headers={"X-QuoteProof-Demo-Key": access_code},
        json=payload,
    )


def test_live_draft_is_disabled_by_default_before_all_sensitive_gates() -> None:
    events: list[str] = []
    application = create_app(
        settings=AppSettings(),
        usage_guard=FakeUsageGuard(UsageDecision.ALLOW, events),
        demo_access_resolver=SpySecretResolver(ACCESS_CODE, events, "access_secret"),
        provider_secret_resolver=SpySecretResolver("unused", events, "provider_secret"),
        client_factory=lambda key: (_ for _ in ()).throw(AssertionError(key)),
    )

    response = post_live(application)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "live_draft_disabled"
    assert events == []


def test_kill_switch_precedes_access_and_usage() -> None:
    events: list[str] = []
    application = create_app(
        settings=live_settings(killed=True),
        usage_guard=FakeUsageGuard(UsageDecision.ALLOW, events),
        demo_access_resolver=SpySecretResolver(ACCESS_CODE, events, "access_secret"),
        provider_secret_resolver=SpySecretResolver("unused", events, "provider_secret"),
    )

    response = post_live(application)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "live_draft_killed"
    assert events == []


def test_invalid_access_stops_before_usage_and_provider() -> None:
    application, events, _ = guarded_app(provider_key="synthetic-provider-placeholder")

    response = post_live(application, access_code="wrong-access-code-with-length")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "access_denied"
    assert events == ["access_secret"]


@pytest.mark.parametrize(
    ("decision", "expected_code"),
    [
        (UsageDecision.RATE_LIMITED, "rate_limited"),
        (UsageDecision.QUOTA_EXCEEDED, "quota_exceeded"),
        (UsageDecision.BUDGET_EXCEEDED, "budget_exceeded"),
        (UsageDecision.UNAVAILABLE, "usage_guard_unavailable"),
    ],
)
def test_usage_denials_stop_before_input_secret_and_client(
    decision: UsageDecision,
    expected_code: str,
) -> None:
    application, events, _ = guarded_app(
        decision=decision,
        provider_key="synthetic-provider-placeholder",
    )

    response = post_live(application, payload={"untrusted": "payload"})

    assert response.status_code in {429, 503}
    assert response.json()["detail"]["code"] == expected_code
    assert events == ["access_secret", "usage"]


@pytest.mark.parametrize(
    "payload",
    [
        {"quote_id": "QP-42", "request_text": "valid", "unknown": True},
        {"quote_id": "QP-42", "request_text": "valid", "default_currency": "EURO"},
        {"quote_id": "contains spaces", "request_text": "valid"},
        ["not", "an", "object"],
    ],
)
def test_invalid_live_input_stops_before_provider_secret(payload: object) -> None:
    application, events, _ = guarded_app(provider_key="synthetic-provider-placeholder")

    response = post_live(application, payload=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert events == ["access_secret", "usage"]


def test_malformed_json_stops_before_provider_secret() -> None:
    application, events, _ = guarded_app(provider_key="synthetic-provider-placeholder")

    response = TestClient(application).post(
        "/draft-and-review",
        headers={"X-QuoteProof-Demo-Key": ACCESS_CODE},
        content=b"{not-json",
    )

    assert response.status_code == 422
    assert events == ["access_secret", "usage"]


def test_oversized_body_stops_before_every_live_gate() -> None:
    application, events, _ = guarded_app(settings=live_settings(body_limit=1_024))

    response = post_live(
        application,
        payload={"quote_id": "QP-42", "request_text": "x" * 2_000},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_too_large"
    assert events == []


def test_missing_provider_secret_is_resolved_only_after_prior_gates() -> None:
    application, events, responses = guarded_app(provider_key=None)

    response = post_live(application)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_not_configured"
    assert events == ["access_secret", "usage", "provider_secret"]
    assert responses.calls == []


def test_provider_timeout_is_sanitized_and_output_is_bounded() -> None:
    timeout = APITimeoutError(request=Request("POST", "https://api.openai.com/v1/responses"))
    responses = FakeResponses(error=timeout)
    application, events, _ = guarded_app(
        provider_key="synthetic-provider-placeholder",
        responses=responses,
    )

    response = post_live(application)

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "message": "The draft could not be generated safely.",
        "code": "provider_unavailable",
    }
    assert events == ["access_secret", "usage", "provider_secret", "client"]
    assert responses.calls[0]["max_output_tokens"] == 1_200
    assert "api.openai.com" not in response.text


def test_default_client_has_explicit_timeout_and_bounded_retries(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_openai(**kwargs: object):
        captured.update(kwargs)
        return SimpleNamespace(responses=SimpleNamespace())

    monkeypatch.setattr("quoteproof.api.OpenAI", fake_openai)
    settings = AppSettings(provider_timeout_seconds=7.5, provider_max_retries=1)

    _default_client_factory(settings)("synthetic-provider-placeholder")

    assert captured == {
        "api_key": "synthetic-provider-placeholder",  # pragma: allowlist secret
        "timeout": 7.5,
        "max_retries": 1,
    }


def test_review_rejects_unknown_fields_and_invalid_formats() -> None:
    payload = {
        "quote_id": "QP-42",
        "customer_country": "de",
        "destination_country": "DEU",
        "currency": "euro",
        "valid_until": "31-08-2026",
        "unexpected": "canary",
    }

    response = TestClient(app).post("/review", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert "canary" not in response.text


def test_review_rejects_more_than_fifty_items() -> None:
    item = {"sku": "SKU-1", "description": "Synthetic item", "quantity": 1, "unit_price": 1}
    payload = {"quote_id": "QP-42", "items": [item] * 51}

    response = TestClient(app).post("/review", json=payload)

    assert response.status_code == 422


def test_cors_allows_configured_origin_and_disposable_header() -> None:
    response = TestClient(app).options(
        "/draft-and-review",
        headers={
            "Origin": DEFAULT_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-quoteproof-demo-key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == DEFAULT_ORIGIN
    assert "x-quoteproof-demo-key" in response.headers["access-control-allow-headers"].lower()


def test_cors_denies_unconfigured_origin() -> None:
    response = TestClient(app).options(
        "/draft-and-review",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://example.com",
        "https://" + "user:" + "pass@" + "example.com",
        "https://example.com/path",
    ],
)
def test_production_cors_configuration_rejects_unsafe_origins(origin: str) -> None:
    with pytest.raises(RuntimeError, match="Unsafe CORS"):
        create_app(settings=AppSettings(allowed_origins=(origin,)))


def test_development_profile_explicitly_allows_local_http() -> None:
    create_app(
        settings=AppSettings(
            profile="development",
            allowed_origins=("http://127.0.0.1:3000",),
        )
    )


def test_logs_and_errors_do_not_echo_canary_input_or_credentials(caplog) -> None:
    canary = "CANARY-QUOTE-TEXT-DO-NOT-LOG"
    credential_canary = "sk-proj-CANARY-NOT-A-REAL-KEY"
    application, _, _ = guarded_app(provider_key=credential_canary)

    with caplog.at_level(logging.INFO, logger="quoteproof.operations"):
        response = post_live(
            application,
            payload={"quote_id": "QP-42", "request_text": canary, "unknown": True},
        )

    combined = response.text + caplog.text
    assert response.status_code == 422
    assert canary not in combined
    assert credential_canary not in combined
    assert ACCESS_CODE not in combined


def test_root_declares_synthetic_scope_without_runtime_secrets() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "QuoteProof API",
        "status": "ok",
        "docs": "/docs",
        "decision_scope": "synthetic_demo_only",
    }


def test_provider_error_classification_does_not_expose_message() -> None:
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(401, request=request)
    error = AuthenticationError("secret provider detail", response=response, body=None)

    assert _safe_provider_error_code(error) == "provider_authentication_failed"
