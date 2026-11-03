"""Run the answer-key questions through /trace and write eval/results/."""

import json
import re
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
KEYS = Path("eval/answer_keys")
OUT = Path("eval/results")


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(KEYS.glob("q*.json")):
        key = json.loads(path.read_text(encoding="utf-8"))
        print("running", path.stem, flush=True)
        try:
            response = httpx.post(f"{BASE}/trace", json={"question": key["question"]}, timeout=240)
            body = response.json()
            status = response.status_code
        except httpx.HTTPError as exc:
            body, status = {"detail": type(exc).__name__}, 0
        result = {"id": path.stem, "status": status, "question": key["question"]}
        if status == 200:
            result.update(check(key, body))
            result["plan"] = body["plan"]
            result["answer"] = body["answer"]
            result["sources"] = [
                {k: s[k] for k in ("n", "file_path", "start_line", "end_line", "score")}
                for s in body["sources"]
            ]
        else:
            result["error"] = body.get("detail")
        (OUT / f"{path.stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        rows.append(result)
        time.sleep(5)

    lines = [
        "| # | Question (short) | Files found | Bad citations | Complete and correct? | Notes |",
        "| - | ---------------- | ----------- | ------------- | --------------------- | ----- |",
    ]
    for r in rows:
        short = r["question"][:50]
        if r["status"] != 200:
            lines.append(f"| {r['id']} | {short} | error {r['status']} | | | {r.get('error')} |")
            continue
        found = f"{r['found']} of {r['wanted']}" if r["wanted"] else "n/a"
        bad = len(r["invalid_citations"])
        lines.append(f"| {r['id']} | {short} | {found} | {bad} | | |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
