from fastapi.testclient import TestClient
from openai import AuthenticationError
from httpx import Request, Response

from quoteproof.api import _safe_provider_error_code, app


def test_draft_endpoint_fails_closed_without_server_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).post(
        "/draft-and-review",
        json={"quote_id": "QP-42", "request_text": "Prepare a quotation."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Server-side OpenAI drafting is not configured."
    }


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
