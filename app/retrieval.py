"""Embed a question and find the closest stored code chunks."""

from collections.abc import Sequence

from app import db
from app.config import Settings
from app.embeddings import embed_texts, make_client


def retrieve(
    question: str,
    settings: Settings,
    k: int = 8,
    modules: Sequence[str] | None = None,
) -> list[dict]:
    client = make_client(settings)
    # One question needs one request, so give up quickly if the daily limit is used up.
    vector = embed_texts(
        client,
        [question],
        settings.embedding_model,
        settings.embedding_dimensions,
        max_retries=2,
    )[0]
    with db.connect(settings.database_url) as conn:
        return db.search(conn, vector, k=k, modules=modules)
