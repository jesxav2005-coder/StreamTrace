from types import SimpleNamespace

import httpx
import openai
import pytest

from app.chunker import Chunk
from app.db import vector_literal
from app.embeddings import embed_texts
from app.ingest import build_groups, embedding_text, iter_source_files


def chunk(path, n):
    return [Chunk("core", path, i * 10 + 1, i * 10 + 10, "x") for i in range(n)]


def test_groups_keep_whole_files_together():
    files = [("a", chunk("a", 3)), ("b", chunk("b", 3)), ("c", chunk("c", 1)), ("d", chunk("d", 0))]
    groups = list(build_groups(files, batch_size=4))
    assert [[name for name, _ in g] for g in groups] == [["a", "b"], ["c"]]


def test_one_big_file_is_its_own_group():
    groups = list(build_groups([("big", chunk("big", 100)), ("s", chunk("s", 1))], batch_size=10))
    assert [len(g) for g in groups] == [1, 1]


def test_embedding_text_has_path_and_lines():
    text = embedding_text(Chunk("core", "core/A.java", 5, 20, "code here"))
    assert text.startswith("core/A.java (lines 5-20)")
    assert text.endswith("code here")


def test_vector_literal():
    assert vector_literal([1, 0.5, -0.25]) == "[1.000000,0.500000,-0.250000]"


class FakeEmbeddings:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input, dimensions):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        # return the items in reverse order to prove the code sorts them by index
        data = [SimpleNamespace(index=i, embedding=[float(i)] * dimensions) for i in range(len(input))]
        return SimpleNamespace(data=list(reversed(data)))


def rate_limit_error():
    request = httpx.Request("POST", "https://example.com")
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)


def test_embed_returns_vectors_in_input_order():
    client = FakeEmbeddings([None])
    vectors = embed_texts(client, ["a", "b", "c"], "m", 4, sleep=lambda s: None)
    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert len(vectors[0]) == 4


def test_embed_retries_when_rate_limited():
    waits = []
    client = FakeEmbeddings([rate_limit_error(), rate_limit_error(), None])
    vectors = embed_texts(client, ["a"], "m", 2, sleep=waits.append)
    assert len(vectors) == 1
    assert client.calls == 3
    assert waits == [2, 4]


def test_embed_gives_up_after_the_last_retry():
    client = FakeEmbeddings([rate_limit_error()] * 3)
    with pytest.raises(openai.RateLimitError):
        embed_texts(client, ["a"], "m", 2, max_retries=3, sleep=lambda s: None)


def test_iter_source_files_skips_tests_unless_asked(tmp_path):
    for rel in [
        "core/src/main/java/A.java",
        "core/src/main/scala/B.scala",
        "core/src/test/java/CTest.java",
        "core/src/main/java/notes.txt",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    without = [rel for rel, _ in iter_source_files(tmp_path, ["core"], include_tests=False)]
    with_tests = [rel for rel, _ in iter_source_files(tmp_path, ["core"], include_tests=True)]
    assert without == ["core/src/main/java/A.java", "core/src/main/scala/B.scala"]
    assert len(with_tests) == 3


def test_missing_module_folder_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(iter_source_files(tmp_path, ["nope"], include_tests=False))
