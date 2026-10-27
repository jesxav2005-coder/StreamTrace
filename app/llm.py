"""LLM calls with a fallback model. Works with any OpenAI-compatible API."""

import time
from dataclasses import dataclass

import openai

from app.config import Settings
from app.usage import UsageRecord, UsageTracker, now


class LLMNotConfiguredError(Exception):
    """No API key or primary model has been set."""


class LLMUnavailableError(Exception):
    """The primary model and the fallback model both failed."""


@dataclass
class LLMResult:
    text: str
    model: str
    fallback_used: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


class LLMService:
    def __init__(self, settings: Settings, tracker: UsageTracker, client=None) -> None:
        self._settings = settings
        self._tracker = tracker
        self._client = client

    def _get_client(self):
        if self._client is None:
            s = self._settings
            if not s.llm_api_key or not s.llm_primary_model:
                raise LLMNotConfiguredError("Set LLM_API_KEY and LLM_PRIMARY_MODEL.")
            # max_retries=0: if the primary model fails we switch to the fallback straight away.
            self._client = openai.OpenAI(
                api_key=s.llm_api_key,
                base_url=s.llm_base_url or None,
                timeout=s.llm_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def complete(self, prompt: str, system: str | None = None) -> LLMResult:
        s = self._settings
        client = self._get_client()
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})

        # (role, model, USD per 1M input tokens, USD per 1M output tokens)
        attempts = [
            ("primary", s.llm_primary_model, s.primary_input_price_per_m, s.primary_output_price_per_m),
        ]
        if s.llm_fallback_model:
            attempts.append(
                (
                    "fallback",
                    s.llm_fallback_model,
                    s.fallback_input_price_per_m,
                    s.fallback_output_price_per_m,
                ),
            )

        last_error: Exception | None = None
        for role, model, price_in, price_out in attempts:
            start = time.perf_counter()
            try:
                resp = client.chat.completions.create(model=model, messages=messages)
                if not resp.choices:
                    raise ValueError("empty response")
            except (openai.OpenAIError, ValueError) as exc:
                latency = int((time.perf_counter() - start) * 1000)
                # Only the error class name is stored, so no key or prompt text leaks into the log.
                failed = UsageRecord(now(), role, model, False, 0, 0, 0.0, latency, type(exc).__name__)
                self._tracker.add(failed)
                last_error = exc
                continue

            latency = int((time.perf_counter() - start) * 1000)
            used = resp.usage
            prompt_tokens = (used.prompt_tokens if used else 0) or 0
            completion_tokens = (used.completion_tokens if used else 0) or 0
            cost = (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000
            self._tracker.add(
                UsageRecord(now(), role, model, True, prompt_tokens, completion_tokens, cost, latency)
            )
            return LLMResult(
                text=resp.choices[0].message.content or "",
                model=model,
                fallback_used=role == "fallback",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                latency_ms=latency,
            )

        raise LLMUnavailableError("All configured models failed.") from last_error
