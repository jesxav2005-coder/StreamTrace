"""Read Kafka source files, chunk them, embed the chunks and store them in Postgres.

Run from the project folder, for example:
    python -m app.ingest --dry-run
    python -m app.ingest --modules core storage --max-files 20
"""

import argparse
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

from app import db
from app.chunker import Chunk, is_test_path, split_into_chunks
from app.config import get_settings
from app.embeddings import embed_texts, make_client

SOURCE_SUFFIXES = {".java", ".scala"}


def iter_source_files(root: Path, modules: Iterable[str], include_tests: bool) -> Iterator[tuple[str, Path]]:
    """Yield (path relative to root, full path) for every Java and Scala file in the modules."""
    for module in modules:
        base = root / module
        if not base.is_dir():
            raise FileNotFoundError(f"module folder not found: {base}")
        for path in sorted(base.rglob("*")):
            if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if not include_tests and is_test_path(rel):
                continue
            yield rel, path


def build_groups(
    files: Iterable[tuple[str, list[Chunk]]], batch_size: int
) -> Iterator[list[tuple[str, list[Chunk]]]]:
    """Group whole files until a group holds at least `batch_size` chunks.

    A file is never split across groups, so a stored file always has all its chunks.
    """
    group: list[tuple[str, list[Chunk]]] = []
    count = 0
    for rel, chunks in files:
        if not chunks:
            continue
        group.append((rel, chunks))
        count += len(chunks)
        if count >= batch_size:
            yield group
            group, count = [], 0
    if group:
        yield group


def embedding_text(chunk: Chunk) -> str:
    return f"{chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n{chunk.content}"


def read_chunks(rel: str, path: Path, max_lines: int, overlap: int) -> list[Chunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return split_into_chunks(text, rel, max_lines=max_lines, overlap=overlap)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default="data/raw/kafka", help="folder that holds the Kafka source")
    parser.add_argument("--modules", nargs="+", default=["core", "storage"])
    parser.add_argument("--include-tests", action="store_true", help="also index test code")
    parser.add_argument("--max-files", type=int, default=0, help="stop after this many files (0 = all)")
    parser.add_argument("--max-lines", type=int, default=60, help="lines per chunk")
    parser.add_argument("--overlap", type=int, default=10, help="lines shared by neighbouring chunks")
    parser.add_argument("--batch-size", type=int, default=32, help="chunks per embedding request")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests")
    parser.add_argument("--dry-run", action="store_true", help="only count files and chunks")
    args = parser.parse_args()

    settings = get_settings()
    root = Path(args.root)
    files = iter_source_files(root, args.modules, args.include_tests)

    if args.dry_run:
        n_files = n_chunks = n_chars = 0
        for rel, path in files:
            chunks = read_chunks(rel, path, args.max_lines, args.overlap)
            n_files += 1
            n_chunks += len(chunks)
            n_chars += sum(len(embedding_text(c)) for c in chunks)
            if args.max_files and n_files >= args.max_files:
                break
        print(f"files={n_files} chunks={n_chunks} approx_tokens={n_chars // 4}")
        return

    client = make_client(settings)
    conn = db.connect(settings.database_url)
    db.init_schema(conn, settings.embedding_dimensions)
    done = db.ingested_files(conn)

    def chunked_files() -> Iterator[tuple[str, list[Chunk]]]:
        seen = 0
        for rel, path in files:
            if rel in done:
                continue
            yield rel, read_chunks(rel, path, args.max_lines, args.overlap)
            seen += 1
            if args.max_files and seen >= args.max_files:
                return

    stored_files = stored_chunks = 0
    for group in build_groups(chunked_files(), args.batch_size):
        chunks = [c for _, file_chunks in group for c in file_chunks]
        vectors: list[list[float]] = []
        for i in range(0, len(chunks), args.batch_size):
            batch = chunks[i : i + args.batch_size]
            vectors += embed_texts(
                client,
                [embedding_text(c) for c in batch],
                settings.embedding_model,
                settings.embedding_dimensions,
            )
            time.sleep(args.delay)
        db.insert_chunks(conn, chunks, vectors)
        stored_files += len(group)
        stored_chunks += len(chunks)
        print(f"stored files={stored_files} chunks={stored_chunks}", flush=True)

    print("done. totals in database:")
    for module, numbers in db.count_chunks(conn).items():
        print(f"  {module}: {numbers['files']} files, {numbers['chunks']} chunks")
    conn.close()


if __name__ == "__main__":
    main()
