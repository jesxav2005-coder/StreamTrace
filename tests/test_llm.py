from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LLMNotConfiguredError, LLMService, LLMUnavailableError
from app.main import app, get_llm, get_tracker
from app.usage import UsageTracker


def ok_response(text="hello", prompt_tokens=10, completion_tokens=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def api_error():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://example.com"))


class FakeClient:
    """Plays back a list of outcomes: a response object, or an exception to raise."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.models_called = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages):
        self.models_called.append(model)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def settings(tmp_path):
    return Settings(
        llm_api_key="test-key",
        llm_primary_model="big",
        llm_fallback_model="small",
        primary_input_price_per_m=2.0,
        primary_output_price_per_m=4.0,
        usage_log_path=str(tmp_path / "usage.jsonl"),
    )


def test_primary_model_success(settings):
    tracker = UsageTracker(settings.usage_log_path)
    fake = FakeClient([ok_response()])
    result = LLMService(settings, tracker, client=fake).complete("hi")

    assert result.model == "big"
    assert result.fallback_used is False
    assert (result.prompt_tokens, result.completion_tokens) == (10, 5)
    assert result.cost_usd == pytest.approx((10 * 2.0 + 5 * 4.0) / 1_000_000)
    assert fake.models_called == ["big"]


def test_falls_back_when_primary_fails(settings):
    tracker = UsageTracker(settings.usage_log_path)
    fake = FakeClient([api_error(), ok_response("from fallback")])
    result = LLMService(settings, tracker, client=fake).complete("hi")

    assert result.text == "from fallback"
    assert result.model == "small"
    assert result.fallback_used is True
    assert fake.models_called == ["big", "small"]

    s = tracker.summary()
    assert (s["total_calls"], s["failed_calls"], s["successful_calls"], s["fallback_calls"]) == (2, 1, 1, 1)


def test_raises_when_both_models_fail(settings):
    tracker = UsageTracker(settings.usage_log_path)
    fake = FakeClient([api_error(), api_error()])
    with pytest.raises(LLMUnavailableError):
        LLMService(settings, tracker, client=fake).complete("hi")
    assert tracker.summary()["failed_calls"] == 2


def test_not_configured_without_key(tmp_path):
    empty = Settings(llm_api_key="", llm_primary_model="", usage_log_path="")
    with pytest.raises(LLMNotConfiguredError):
        LLMService(empty, UsageTracker("")).complete("hi")


def test_usage_survives_restart(settings):
    first = UsageTracker(settings.usage_log_path)
    LLMService(settings, first, client=FakeClient([ok_response()])).complete("hi")

    second = UsageTracker(settings.usage_log_path)  # a new process reading the same file
    assert second.summary()["total_calls"] == 1
    assert second.summary()["prompt_tokens"] == 10


@pytest.fixture
def api(settings):
    tracker = UsageTracker(settings.usage_log_path)
    fake = FakeClient([ok_response("pong")])
    service = LLMService(settings, tracker, client=fake)
    app.dependency_overrides[get_llm] = lambda: service
    app.dependency_overrides[get_tracker] = lambda: tracker
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_and_usage_endpoints(api):
    r = api.post("/chat", json={"prompt": "ping"})
    assert r.status_code == 200
    assert r.json()["answer"] == "pong"
    assert r.json()["fallback_used"] is False

    u = api.get("/usage").json()
    assert u["total_calls"] == 1
    assert u["total_tokens"] == 15
    assert u["recent"][0]["model"] == "big"


def test_chat_rejects_empty_prompt(api):
    assert api.post("/chat", json={"prompt": ""}).status_code == 422


def test_chat_returns_503_when_not_configured():
    empty = Settings(llm_api_key="", llm_primary_model="", usage_log_path="")
    unconfigured = LLMService(empty, UsageTracker(""))
    app.dependency_overrides[get_llm] = lambda: unconfigured
    try:
        with TestClient(app) as c:
            assert c.post("/chat", json={"prompt": "hi"}).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_chat_returns_502_when_all_models_fail(settings):
    tracker = UsageTracker("")
    service = LLMService(settings, tracker, client=FakeClient([api_error(), api_error()]))
    app.dependency_overrides[get_llm] = lambda: service
    try:
        with TestClient(app) as c:
            assert c.post("/chat", json={"prompt": "hi"}).status_code == 502
    finally:
        app.dependency_overrides.clear()
