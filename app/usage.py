"""Tracks every LLM call: tokens, cost, latency and whether the fallback model was used."""

import json
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    timestamp: float
    role: str  # "primary" or "fallback"
    model: str
    ok: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    error: str | None = None


class UsageTracker:
    """Thread-safe usage log. Keeps running totals and the latest calls in memory,
    and appends each call to a JSON-lines file so totals survive a restart."""

    def __init__(self, path: str = "", keep_recent: int = 200) -> None:
        self._lock = threading.Lock()
        self._path = Path(path) if path else None
        self._recent: deque[UsageRecord] = deque(maxlen=keep_recent)
        self._totals = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "fallback_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
        }
        self._load()

    def _apply(self, r: UsageRecord) -> None:
        t = self._totals
        t["total_calls"] += 1
        t["successful_calls" if r.ok else "failed_calls"] += 1
        if r.role == "fallback":
            t["fallback_calls"] += 1
        t["prompt_tokens"] += r.prompt_tokens
        t["completion_tokens"] += r.completion_tokens
        t["cost_usd"] += r.cost_usd
        self._recent.append(r)

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            log.warning("Could not read usage log %s: %s", self._path, exc)
            return
        for line in lines:
            try:
                self._apply(UsageRecord(**json.loads(line)))
            except (ValueError, TypeError):
                continue  # skip a damaged line instead of crashing at startup

    def add(self, record: UsageRecord) -> None:
        with self._lock:
            self._apply(record)
            if not self._path:
                return
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record)) + "\n")
            except OSError as exc:
                log.warning("Could not write usage log %s: %s", self._path, exc)

    def summary(self, recent: int = 10) -> dict:
        with self._lock:
            t = dict(self._totals)
            latest = list(self._recent)[-recent:] if recent > 0 else []
        t["total_tokens"] = t["prompt_tokens"] + t["completion_tokens"]
        t["cost_usd"] = round(t["cost_usd"], 6)
        t["recent"] = [asdict(r) for r in reversed(latest)]
        return t


def now() -> float:
    return time.time()
