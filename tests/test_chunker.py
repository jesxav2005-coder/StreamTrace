import pytest

from app.chunker import is_test_path, module_for, skip_license_header, split_into_chunks

LICENSE = """/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.
 */
"""


def numbered(n, start=1):
    return "\n".join(f"line {i}" for i in range(start, start + n))


def test_short_file_is_one_chunk_with_real_line_numbers():
    chunks = split_into_chunks(numbered(10), "core/src/main/Foo.java")
    assert len(chunks) == 1
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 10)
    assert chunks[0].module == "core"
    assert chunks[0].content.splitlines()[0] == "line 1"


def test_license_header_is_skipped_but_line_numbers_still_count_from_the_top():
    text = LICENSE + numbered(5)
    chunks = split_into_chunks(text, "storage/Foo.java")
    assert len(chunks) == 1
    assert chunks[0].start_line == 5  # the licence is lines 1-4
    assert chunks[0].content.splitlines()[0] == "line 1"


def test_comment_that_is_not_a_license_is_kept():
    text = "/*\n * Helper for parsing.\n */\n" + numbered(3)
    assert skip_license_header(text.splitlines()) == 0


def test_long_file_overlaps_and_covers_every_line():
    chunks = split_into_chunks(numbered(200), "clients/Big.java", max_lines=60, overlap=10)
    assert len(chunks) > 3
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 200
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.start_line <= previous.end_line  # they overlap
        assert current.start_line > previous.start_line  # and always move forward
    covered = set()
    for c in chunks:
        covered.update(range(c.start_line, c.end_line + 1))
    assert covered == set(range(1, 201))


def test_chunk_content_matches_its_line_range():
    chunks = split_into_chunks(numbered(150), "core/A.java", max_lines=40, overlap=5)
    for c in chunks:
        lines = c.content.splitlines()
        assert len(lines) == c.end_line - c.start_line + 1
        assert lines[0] == f"line {c.start_line}"
        assert lines[-1] == f"line {c.end_line}"


def test_window_prefers_to_end_at_a_blank_line():
    lines = [f"line {i}" for i in range(1, 100)]
    lines[54] = ""  # line 55 is blank, inside the last quarter of the first window
    chunks = split_into_chunks("\n".join(lines), "core/A.java", max_lines=60, overlap=5)
    assert chunks[0].end_line == 55


def test_empty_and_blank_files_give_no_chunks():
    assert split_into_chunks("", "core/A.java") == []
    assert split_into_chunks("\n\n  \n", "core/A.java") == []


def test_bad_settings_are_rejected():
    with pytest.raises(ValueError):
        split_into_chunks("x", "core/A.java", max_lines=10, overlap=10)


def test_module_for_and_test_paths():
    assert module_for("storage/src/main/java/Foo.java") == "storage"
    assert is_test_path("core/src/test/scala/FooTest.scala")
    assert is_test_path("streams/src/testFixtures/java/Util.java")
    assert is_test_path("clients/src/main/java/org/ExampleTest.java")
    assert not is_test_path("core/src/main/scala/kafka/server/ReplicaManager.scala")
