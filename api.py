from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from service import run_research


class SearchRequest(BaseModel):
    query: str = Field(min_length=3)
    recency: Literal["any", "past_year", "past_3_years", "past_5_years"] = "any"
    max_results: int = Field(default=10, ge=1, le=20)
    summary_mode: Literal["map_reduce", "single_call"] = "map_reduce"


class Paper(BaseModel):
    title: str
    snippet: str
    link: str


class PaperSummary(BaseModel):
    title: str
    link: str
    summary: str


class Guardrail(BaseModel):
    hallucination_check_passed: bool
    violations: list[dict]


class SearchResponse(BaseModel):
    refined_query: dict
    scholar_results: list[Paper]
    paper_summaries: list[PaperSummary]
    final_synthesis: str
    guardrail: Guardrail


app = FastAPI(title="Google Scholar Research Assistant API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    try:
        shared = run_research(
            query=payload.query,
            recency=payload.recency,
            max_results=payload.max_results,
            summary_mode=payload.summary_mode,
        )
        return SearchResponse(
            refined_query=shared["refined_query"],
            scholar_results=shared["scholar_results"],
            paper_summaries=shared["paper_summaries"],
            final_synthesis=shared["final_synthesis"],
            guardrail=shared["guardrail"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
