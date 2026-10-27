"""Request and response models."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    system: str | None = Field(default=None, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    model: str
    fallback_used: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


class UsageEntry(BaseModel):
    timestamp: float
    role: str
    model: str
    ok: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    error: str | None = None


class UsageResponse(BaseModel):
    total_calls: int
    successful_calls: int
    failed_calls: int
    fallback_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    recent: list[UsageEntry]
