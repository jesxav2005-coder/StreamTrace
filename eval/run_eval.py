"""Run the answer-key questions through /trace and write eval/results/.

Usage:
    python eval\\run_eval.py                 run every question that has no good result yet
    python eval\\run_eval.py q02 q05         run only these questions
    python eval\\run_eval.py --force         rerun everything, even good results
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
KEYS = Path("eval/answer_keys")
OUT = Path("eval/results")

RETRY_WAIT = float(os.environ.get("EVAL_RETRY_WAIT", 65))  # seconds to wait after a 429
MAX_RETRIES = 3  # retries per question after the first try
PAUSE = float(os.environ.get("EVAL_PAUSE", 20))  # seconds between questions
STOP_AFTER_BLOCKED = 3  # stop if this many questions in a row stay blocked


def cited_numbers(answer: str) -> set[int]:
    numbers = set()
    for group in re.findall(r"\[([\d,\s]+)\]", answer):
        numbers.update(int(n) for n in re.findall(r"\d+", group))
    return numbers


def check(key: dict, body: dict) -> dict:
    sources = body.get("sources", [])
    wanted = sorted({Path(step["file"]).name for step in key.get("steps", [])})
    found = {Path(s["file_path"]).name for s in sources}
    valid = {s["n"] for s in sources}
    cited = cited_numbers(body.get("answer", ""))
    return {
        "wanted": len(wanted),
        "found": len([name for name in wanted if name in found]),
        "missing": [name for name in wanted if name not in found],
        "invalid_citations": sorted(cited - valid),
    }


def has_good_result(question_id: str) -> bool:
    path = OUT / f"{question_id}.json"
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status") == 200
    except (OSError, ValueError):
        return False


def ask(question: str) -> tuple[int, dict]:
    """Call /trace. Wait and retry when the server answers 429."""
    status, body = 0, {}
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = httpx.post(f"{BASE}/trace", json={"question": question}, timeout=240)
            status = response.status_code
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return 0, {"detail": type(exc).__name__}
        if status != 429:
            return status, body
        if attempt < MAX_RETRIES:
            print(
                f"  429 received, waiting {RETRY_WAIT:.0f}s (retry {attempt + 1} of {MAX_RETRIES})",
                flush=True,
            )
            time.sleep(RETRY_WAIT)
    return status, body


def build_summary() -> str:
    lines = [
        "| # | Question (short) | Files found | Bad citations | Complete and correct? | Notes |",
        "| - | ---------------- | ----------- | ------------- | --------------------- | ----- |",
    ]
    for path in sorted(KEYS.glob("q*.json")):
        result_path = OUT / f"{path.stem}.json"
        if not result_path.exists():
            lines.append(f"| {path.stem} | not run | | | | |")
            continue
        r = json.loads(result_path.read_text(encoding="utf-8"))
        short = r["question"][:50]
        if r["status"] != 200:
            lines.append(f"| {r['id']} | {short} | error {r['status']} | | | {r.get('error')} |")
            continue
        found = f"{r['found']} of {r['wanted']}" if r["wanted"] else "n/a"
        bad = len(r["invalid_citations"])
        missing = ", ".join(r["missing"])
        lines.append(f"| {r['id']} | {short} | {found} | {bad} | | missing: {missing} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    chosen = {a for a in args if a.startswith("q")}
    OUT.mkdir(parents=True, exist_ok=True)

    blocked_in_a_row = 0
    first = True
    for path in sorted(KEYS.glob("q*.json")):
        if chosen and path.stem not in chosen:
            continue
        if not force and has_good_result(path.stem):
            print("skipping", path.stem, "(already has a good result)", flush=True)
            continue
        if not first:
            time.sleep(PAUSE)
        first = False

        key = json.loads(path.read_text(encoding="utf-8"))
        print("running", path.stem, flush=True)
        status, body = ask(key["question"])
        result = {"id": path.stem, "status": status, "question": key["question"]}
        if status == 200:
            result.update(check(key, body))
            result["plan"] = body["plan"]
            result["answer"] = body["answer"]
            result["sources"] = [
                {k: s[k] for k in ("n", "file_path", "start_line", "end_line", "score")}
                for s in body["sources"]
            ]
            blocked_in_a_row = 0
        else:
            result["error"] = body.get("detail")
            blocked_in_a_row = blocked_in_a_row + 1 if status == 429 else 0
        (OUT / f"{path.stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

        if blocked_in_a_row >= STOP_AFTER_BLOCKED:
            print(
                f"Stopping: {STOP_AFTER_BLOCKED} questions in a row were blocked (429). "
                "The daily quota is probably used up. Wait for it to reset and run the same command again.",
                flush=True,
            )
            break

    summary = build_summary()
    (OUT / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()