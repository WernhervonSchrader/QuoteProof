from fastapi import FastAPI, HTTPException

from .graph import QuoteReviewPipeline
from .models import QuoteDraft, ReviewResult
from .scenarios import list_scenarios, load_scenario


app = FastAPI(title="QuoteProof", version="0.1.0")
pipeline = QuoteReviewPipeline()


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

