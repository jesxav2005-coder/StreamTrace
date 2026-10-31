"""Postgres + pgvector storage for code chunks."""

from collections.abc import Sequence

import psycopg

from app.chunker import Chunk


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def connect(database_url: str) -> psycopg.Connection:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(database_url)


def init_schema(conn: psycopg.Connection, dimensions: int) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id          BIGSERIAL PRIMARY KEY,
                module      TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                start_line  INTEGER NOT NULL,
                end_line    INTEGER NOT NULL,
                content     TEXT NOT NULL,
                embedding   vector({int(dimensions)}),
                UNIQUE (file_path, start_line, end_line)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS chunks_module_idx ON chunks (module)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
    conn.commit()


def ingested_files(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT file_path FROM chunks WHERE embedding IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def insert_chunks(
    conn: psycopg.Connection,
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("need one vector per chunk")
    rows = [
        (c.module, c.file_path, c.start_line, c.end_line, c.content, vector_literal(v))
        for c, v in zip(chunks, vectors, strict=True)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (module, file_path, start_line, end_line, content, embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (file_path, start_line, end_line) DO NOTHING
            """,
            rows,
        )
    conn.commit()


def count_chunks(conn: psycopg.Connection) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT module, COUNT(*), COUNT(DISTINCT file_path) FROM chunks GROUP BY module ORDER BY 1"
        )
        rows = cur.fetchall()
    return {m: {"chunks": c, "files": f} for m, c, f in rows}


def search(
    conn: psycopg.Connection,
    query_vector: Sequence[float],
    k: int = 8,
    modules: Sequence[str] | None = None,
) -> list[dict]:
    """The k chunks closest to the query vector, optionally limited to some modules."""
    literal = vector_literal(query_vector)
    sql = """
        SELECT module, file_path, start_line, end_line, content,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        WHERE embedding IS NOT NULL
    """
    params: list = [literal]
    if modules:
        sql += " AND module = ANY(%s)"
        params.append(list(modules))
    sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params += [literal, k]
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = ["module", "file_path", "start_line", "end_line", "content", "score"]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
