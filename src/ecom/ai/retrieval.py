"""pgvector retrieval over the knowledge base (table docs, metric definitions, examples)."""
from pathlib import Path

import yaml

from ecom.ai import db
from ecom.ai.embeddings import embed, to_pgvector

KNOWLEDGE_FILE = Path(__file__).with_name("knowledge.yml")


def load_knowledge() -> list[dict]:
    data = yaml.safe_load(KNOWLEDGE_FILE.read_text())
    return [{"id": e["id"], "kind": kind.rstrip("s"), "content": e["content"].strip()}
            for kind, entries in data.items() for e in entries]


def index() -> int:
    entries = load_knowledge()
    with db.connect() as conn:
        conn.execute("DELETE FROM ai.knowledge")
        for e in entries:
            conn.execute(
                "INSERT INTO ai.knowledge (id, kind, content, embedding) VALUES (%s, %s, %s, %s::vector)",
                (e["id"], e["kind"], e["content"], to_pgvector(embed(e["content"]))),
            )
    return len(entries)


def search(question: str, k: int = 6) -> list[dict]:
    """Top-k entries by cosine distance; metric definitions are always included (they are short)."""
    rows = db.query(
        "SELECT id, kind, content, 1 - (embedding <=> %s::vector) AS similarity "
        "FROM ai.knowledge WHERE kind <> 'metric' ORDER BY embedding <=> %s::vector LIMIT %s",
        (to_pgvector(embed(question)),) * 2 + (k,),
    )
    metrics = db.query("SELECT id, kind, content, NULL AS similarity FROM ai.knowledge WHERE kind = 'metric'")
    return rows + metrics
