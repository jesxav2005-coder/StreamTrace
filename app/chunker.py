"""Split source files into line-based chunks that keep real line numbers for citations."""

from dataclasses import dataclass
from pathlib import PurePosixPath

LICENSE_MARKER = "Licensed to the Apache Software Foundation"
TEST_DIRS = {"test", "testFixtures", "integration-test", "jmh"}


@dataclass(frozen=True)
class Chunk:
    module: str
    file_path: str  # relative to the Kafka root, with forward slashes
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    content: str


def module_for(file_path: str) -> str:
    """The module is the first folder, for example 'storage' in 'storage/src/main/...'."""
    return PurePosixPath(file_path).parts[0]


def is_test_path(file_path: str) -> bool:
    path = PurePosixPath(file_path)
    if TEST_DIRS & set(path.parts):
        return True
    return path.name.endswith(("Test.java", "Test.scala", "Tests.java", "Tests.scala"))


def skip_license_header(lines: list[str]) -> int:
    """Index of the first line after the leading Apache licence comment, or 0 if there is none."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not lines[i].lstrip().startswith("/*"):
        return 0
    for j in range(i, len(lines)):
        if "*/" in lines[j]:
            block = "\n".join(lines[i : j + 1])
            return j + 1 if LICENSE_MARKER in block else 0
    return 0


def split_into_chunks(
    text: str,
    file_path: str,
    max_lines: int = 60,
    overlap: int = 10,
) -> list[Chunk]:
    """Cut a file into windows of up to `max_lines` lines that overlap by `overlap` lines.

    The licence header is skipped but line numbers still count from the top of the file.
    A window ends at a blank line when there is one near its end, so a method is less
    likely to be cut in half.
    """
    if max_lines < 1 or overlap < 0 or overlap >= max_lines:
        raise ValueError("need max_lines >= 1 and 0 <= overlap < max_lines")

    lines = text.splitlines()
    module = module_for(file_path)
    total = len(lines)
    chunks: list[Chunk] = []
    start = skip_license_header(lines)

    while start < total:
        end = min(start + max_lines, total)
        if end < total:
            lowest = start + (max_lines * 3) // 4
            for i in range(end - 1, lowest - 1, -1):
                if not lines[i].strip():
                    end = i + 1
                    break
        body = lines[start:end]
        if any(line.strip() for line in body):
            chunks.append(Chunk(module, file_path, start + 1, end, "\n".join(body)))
        if end >= total:
            break
        start = max(end - overlap, start + 1)

    return chunks
