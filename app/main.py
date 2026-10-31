from functools import lru_cache
from typing import Annotated

import openai
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.llm import LLMNotConfiguredError, LLMService, LLMUnavailableError
from app.retrieval import retrieve
from app.schemas import ChatRequest, ChatResponse, UsageResponse
from app.usage import UsageTracker

app = FastAPI(title="StreamTrace", version="0.3.0")

SettingsDep = Annotated[Settings, Depends(get_settings)]

ASK_SYSTEM_PROMPT = (
    "You explain how Apache Kafka works, using only the numbered code excerpts you are given. "
    "Answer as a numbered list of steps. After each step, cite the excerpt it comes from, "
    "like [2]. If the excerpts do not cover part of the question, say what is missing "
    "instead of guessing."
)


@lru_cache
def get_tracker() -> UsageTracker:
    return UsageTracker(get_settings().usage_log_path)


@lru_cache
def get_llm() -> LLMService:
    return LLMService(get_settings(), get_tracker())


LLMDep = Annotated[LLMService, Depends(get_llm)]
TrackerDep = Annotated[UsageTracker, Depends(get_tracker)]


class SearchRequest(BaseModel):
    question: str = Field(min_length=3)
    k: int = Field(default=8, ge=1, le=20)
    modules: list[str] | None = None


class Source(BaseModel):
    n: int
    module: str
    file_path: str
    start_line: int
    end_line: int
    citation: str
    score: float
    content: str


class SearchResponse(BaseModel):
    question: str
    results: list[Source]


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    sources: list[Source]


def to_sources(rows: list[dict]) -> list[Source]:
    return [
        Source(
            n=i,
            citation=f"{r['file_path']}:{r['start_line']}-{r['end_line']}",
            **r,
        )
        for i, r in enumerate(rows, start=1)
    ]


def run_retrieval(body: SearchRequest, settings: Settings) -> list[Source]:
    try:
        rows = retrieve(body.question, settings, k=body.k, modules=body.modules)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except openai.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Embedding quota used up. Try again later.") from exc
    except (openai.APIError, psycopg.Error) as exc:
        raise HTTPException(status_code=503, detail="Search is unavailable right now.") from exc
    return to_sources(rows)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send visitors who open the bare address to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health(settings: SettingsDep) -> dict:
    """Liveness: the process is up. Must be fast and must not call the LLM or the DB."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, llm: LLMDep) -> ChatResponse:
    """Send a prompt to the primary model, falling back to the second model if it fails."""
    try:
        result = llm.complete(body.prompt, system=body.system)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="LLM is not configured.") from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=502, detail="All configured models failed.") from exc
    return ChatResponse(
        answer=result.text,
        model=result.model,
        fallback_used=result.fallback_used,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )


@app.post("/search", response_model=SearchResponse)
def search(body: SearchRequest, settings: SettingsDep) -> SearchResponse:
    """The stored code chunks closest to the question, with file and line citations."""
    return SearchResponse(question=body.question, results=run_retrieval(body, settings))


@app.post("/ask", response_model=AskResponse)
def ask(body: SearchRequest, settings: SettingsDep, llm: LLMDep) -> AskResponse:
    """Find relevant code, then have the LLM write a cited step list from it."""
    sources = run_retrieval(body, settings)
    if not sources:
        raise HTTPException(status_code=404, detail="No code has been ingested yet.")
    excerpts = "\n\n".join(f"[{s.n}] {s.citation}\n{s.content}" for s in sources)
    prompt = f"Question: {body.question}\n\nCode excerpts:\n\n{excerpts}"
    try:
        result = llm.complete(prompt, system=ASK_SYSTEM_PROMPT)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="LLM is not configured.") from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=502, detail="All configured models failed.") from exc
    return AskResponse(question=body.question, answer=result.text, model=result.model, sources=sources)


@app.get("/usage", response_model=UsageResponse)
def usage(tracker: TrackerDep, recent: Annotated[int, Query(ge=0, le=100)] = 10) -> UsageResponse:
    """Totals for tokens and cost, plus the most recent calls."""
    return UsageResponse(**tracker.summary(recent=recent))
