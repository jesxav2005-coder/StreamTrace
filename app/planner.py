"""Split a broad question into sub-questions and search for each one."""

import json
import re

from app.config import Settings
from app.retrieval import retrieve

KNOWN_MODULES = {"clients", "core", "storage"}

PLAN_SYSTEM_PROMPT = (
    "You help search the Apache Kafka source code. Split the user's question into 3 to 5 "
    "short search questions, in the order the request flows through the system. "
    "Each search question should target one part of the code. "
    'Reply with only a JSON list like [{"question": "...", "modules": ["core"]}]. '
    "Allowed modules: clients (producer and consumer client code), "
    "core (broker, request handling, replication), storage (log segments, disk writes, retention)."
)


def parse_plan(text: str, original: str, max_steps: int = 5) -> list[dict]:
    """Read the LLM's JSON plan. If anything is wrong, fall back to the original question."""
    fallback = [{"question": original, "modules": []}]
    match = re.search(r"\[.*\]", text or "", re.DOTALL)
    if not match:
        return fallback
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
    steps = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("question", "")).strip():
            continue
        modules = [m for m in item.get("modules") or [] if m in KNOWN_MODULES]
        steps.append({"question": str(item["question"]).strip(), "modules": modules})
    return steps[:max_steps] or fallback


def make_plan(question: str, llm) -> list[dict]:
    result = llm.complete(question, system=PLAN_SYSTEM_PROMPT)
    return parse_plan(result.text, question)


def plan_and_retrieve(
    question: str, settings: Settings, llm, k_per_step: int = 4
) -> tuple[list[dict], list[dict]]:
    """Returns (plan steps, de-duplicated chunks from searching each step)."""
    steps = make_plan(question, llm)
    seen = set()
    rows = []
    for step in steps:
        found = retrieve(step["question"], settings, k=k_per_step, modules=step["modules"] or None)
        for row in found:
            key = (row["file_path"], row["start_line"], row["end_line"])
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return steps, rows
