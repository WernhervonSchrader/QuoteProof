from fastapi.testclient import TestClient
from openai import AuthenticationError
from httpx import Request, Response

from quoteproof.api import _safe_provider_error_code, app


def test_draft_endpoint_fails_closed_without_jury_access_secret(monkeypatch) -> None:
    monkeypatch.delenv("QUOTEPROOF_DEMO_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).post(
        "/draft-and-review",
        headers={"X-QuoteProof-Demo-Key": "present-but-not-configured"},
        json={"quote_id": "QP-42", "request_text": "Prepare a quotation."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Server-side jury access is not configured."
    }


def test_draft_endpoint_rejects_invalid_jury_access_code(monkeypatch) -> None:
    monkeypatch.setenv("QUOTEPROOF_DEMO_KEY", "jury-code-with-adequate-length")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).post(
        "/draft-and-review",
        headers={"X-QuoteProof-Demo-Key": "incorrect-code"},
        json={"quote_id": "QP-42", "request_text": "Prepare a quotation."},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Jury access code is missing or invalid."
    }


def test_valid_jury_code_reaches_openai_secret_boundary(monkeypatch) -> None:
    access_code = "jury-code-with-adequate-length"
    monkeypatch.setenv("QUOTEPROOF_DEMO_KEY", access_code)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).post(
        "/draft-and-review",
        headers={"X-QuoteProof-Demo-Key": access_code},
        json={"quote_id": "QP-42", "request_text": "Prepare a quotation."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Server-side OpenAI drafting is not configured."
    }


def test_cors_allows_disposable_jury_header() -> None:
    response = TestClient(app).options(
        "/draft-and-review",
        headers={
            "Origin": "https://quoteproof-demo.wernhervonschrader.chatgpt.site",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-quoteproof-demo-key"
            ),
        },
    )

    assert response.status_code == 200
    assert "x-quoteproof-demo-key" in response.headers[
        "access-control-allow-headers"
    ].lower()


def test_root_describes_server_without_exposing_configuration() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "QuoteProof API",
        "status": "ok",
        "docs": "/docs",
    }


def test_provider_error_classification_does_not_expose_message() -> None:
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(401, request=request)
    error = AuthenticationError("secret provider detail", response=response, body=None)

    assert _safe_provider_error_code(error) == "provider_authentication_failed"
