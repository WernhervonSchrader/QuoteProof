import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from .drafting import DraftingError, OpenAIQuoteDrafter
from .graph import QuoteReviewPipeline
from .models import DraftAndReviewResult, DraftRequest, QuoteDraft, ReviewResult
from .scenarios import list_scenarios, load_scenario


app = FastAPI(title="QuoteProof", version="0.1.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "QUOTEPROOF_ALLOWED_ORIGINS",
        "https://quoteproof-demo.wernhervonschrader.chatgpt.site",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
pipeline = QuoteReviewPipeline()


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


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "QuoteProof API",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scenarios")
def scenarios() -> list[str]:
    return list_scenarios()


@app.post("/review", response_model=ReviewResult)
def review(quote: QuoteDraft) -> ReviewResult:
    return pipeline.run(quote)


@app.post("/review/{scenario}", response_model=ReviewResult)
def review_scenario(scenario: str) -> ReviewResult:
    try:
        quote = load_scenario(scenario)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown scenario") from exc
    return pipeline.run(quote)


@app.post("/draft-and-review", response_model=DraftAndReviewResult)
def draft_and_review(request: DraftRequest) -> DraftAndReviewResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Server-side OpenAI drafting is not configured.",
        )
    drafter = OpenAIQuoteDrafter()
    try:
        quote = drafter.draft(request)
    except DraftingError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "The draft could not be generated safely.",
                "code": "structured_draft_missing",
            },
        ) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "The draft could not be generated safely.",
                "code": _safe_provider_error_code(exc),
            },
        ) from exc
    return DraftAndReviewResult(
        model=drafter.model,
        review=pipeline.run(quote),
    )
