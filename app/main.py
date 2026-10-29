from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import Settings, get_settings
from app.llm import LLMNotConfiguredError, LLMService, LLMUnavailableError
from app.schemas import ChatRequest, ChatResponse, UsageResponse
from app.usage import UsageTracker

app = FastAPI(title="Examate RAG starter", version="0.2.0")

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_tracker() -> UsageTracker:
    return UsageTracker(get_settings().usage_log_path)


@lru_cache
def get_llm() -> LLMService:
    return LLMService(get_settings(), get_tracker())


LLMDep = Annotated[LLMService, Depends(get_llm)]
TrackerDep = Annotated[UsageTracker, Depends(get_tracker)]


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


@app.get("/usage", response_model=UsageResponse)
def usage(tracker: TrackerDep, recent: Annotated[int, Query(ge=0, le=100)] = 10) -> UsageResponse:
    """Totals for tokens and cost, plus the most recent calls."""
    return UsageResponse(**tracker.summary(recent=recent))
