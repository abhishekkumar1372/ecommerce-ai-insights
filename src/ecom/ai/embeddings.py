"""Text embeddings for retrieval.

Default: a dependency-free hashing embedder (word unigrams + bigrams hashed into
384 dimensions). It is fast, deterministic and good enough for a few dozen
knowledge entries that share vocabulary with the questions. To use a neural embedding model instead,
replace embed() and change the vector(384) column in db/init/02_ai.sql to the
model's dimension.
"""
import hashlib
import math
import re
from itertools import pairwise

DIM = 384
_STOP = {"the", "a", "an", "of", "in", "by", "for", "to", "and", "or", "is", "are", "what", "which", "how",
         "me", "show", "with", "on", "per", "each", "was", "were", "did", "do", "does", "from", "that"}


def _tokens(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in _STOP]
    # crude stemming so "categories" ~ "category", "orders" ~ "order"
    words = [re.sub(r"(ies|es|s)$", lambda m: "y" if m.group(1) == "ies" else "", w) if len(w) > 4 else w
             for w in words]
    parts = []
    for w in words:
        parts += w.split("_") if "_" in w else []
    return words + parts + [f"{a} {b}" for a, b in pairwise(words)]


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    for tok in _tokens(text):
        h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
        vec[h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
