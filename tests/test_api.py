from fastapi.testclient import TestClient

from quoteproof.api import app


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
