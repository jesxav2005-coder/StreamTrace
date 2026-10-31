"""Turn text into vectors with any OpenAI-compatible embeddings API."""

import time
from collections.abc import Callable, Sequence

import openai

from app.config import Settings

RETRYABLE = (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError)


def make_client(settings: Settings) -> openai.OpenAI:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set.")
    return openai.OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )


def embed_texts(
    client,
    texts: Sequence[str],
    model: str,
    dimensions: int,
    max_retries: int = 8,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list[float]]:
    """Embed one batch of texts. Waits and retries when the API is busy or rate limited."""
    if not texts:
        return []
    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(model=model, input=list(texts), dimensions=dimensions)
        except RETRYABLE:
            if attempt == max_retries - 1:
                raise
            # The free tier limit resets every minute, so wait up to ~65 seconds.
            sleep(min(15 * 2**attempt, 65))
            continue
        items = list(response.data)
        # Some providers leave `index` empty; then the order returned is the order sent.
        if all(item.index is not None for item in items):
            items.sort(key=lambda item: item.index)
        return [item.embedding for item in items]
    raise RuntimeError("unreachable")
