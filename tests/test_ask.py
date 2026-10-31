from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main

ROW = {
    "module": "storage",
    "file_path": "storage/src/main/java/Log.java",
    "start_line": 10,
    "end_line": 69,
    "content": "class Log {}",
    "score": 0.9,
}


class FakeLLM:
    def complete(self, prompt, system=None):
        assert "[1] storage/src/main/java/Log.java:10-69" in prompt
        return SimpleNamespace(text="1. Append to the log [1]", model="fake")


def client_with(monkeypatch, rows):
    monkeypatch.setattr(main, "retrieve", lambda *a, **k: rows)
    main.app.dependency_overrides[main.get_llm] = lambda: FakeLLM()
    return TestClient(main.app)


def test_search_returns_citations(monkeypatch):
    client = client_with(monkeypatch, [ROW])
    body = client.post("/search", json={"question": "how are logs written"}).json()
    assert body["results"][0]["citation"] == "storage/src/main/java/Log.java:10-69"
    main.app.dependency_overrides.clear()


def test_ask_returns_answer_and_sources(monkeypatch):
    client = client_with(monkeypatch, [ROW])
    body = client.post("/ask", json={"question": "how are logs written"}).json()
    assert body["answer"].startswith("1.")
    assert body["sources"][0]["n"] == 1
    main.app.dependency_overrides.clear()


def test_ask_with_empty_database_is_404(monkeypatch):
    client = client_with(monkeypatch, [])
    response = client.post("/ask", json={"question": "how are logs written"})
    assert response.status_code == 404
    main.app.dependency_overrides.clear()
