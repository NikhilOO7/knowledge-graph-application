"""Embedding + summarisation tool.

Used to build a *context signature* for each document and each bucket so the
Context-Router agent can decide whether an upload belongs to an existing bucket.

If a real embedding endpoint is unavailable, falls back to a deterministic
hashing-based bag-of-words vector so context routing still works offline.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List, Optional

from openai import OpenAI

from ..config import settings
from . import llm

_FALLBACK_DIM = 256
_embed_client: Optional[OpenAI] = None


def _client() -> OpenAI:
    global _embed_client
    if _embed_client is None:
        if settings.llm_provider == "ollama":
            _embed_client = OpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama")
        else:
            _embed_client = OpenAI(api_key=settings.openai_api_key)
    return _embed_client


def embed(text: str) -> List[float]:
    text = (text or "").strip()
    if not text:
        return [0.0] * _FALLBACK_DIM
    if settings.llm_provider == "openai" and settings.openai_api_key:
        try:
            resp = _client().embeddings.create(
                model=settings.openai_embedding_model, input=text[:8000]
            )
            return resp.data[0].embedding
        except Exception:
            pass
    return _hash_embed(text)


def _hash_embed(text: str) -> List[float]:
    vec = [0.0] * _FALLBACK_DIM
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % _FALLBACK_DIM] += 1.0
    return _normalize(vec)


def _normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def mean_vector(vectors: List[List[float]]) -> List[float]:
    vectors = [v for v in vectors if v]
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            acc[i] += v[i]
    return [x / len(vectors) for x in acc]


def summarize(text: str, max_words: int = 80) -> str:
    """Short topical summary used as the human-readable bucket signature."""
    text = (text or "").strip()
    if not text:
        return ""
    if not settings.llm_is_configured:
        return text[:400]
    try:
        return llm.chat(
            system="You summarise documents into a short topical description "
            "capturing the main subject, domain, and key entities.",
            user=f"Summarise the following in {max_words} words or fewer, "
            f"focusing on what the document is ABOUT:\n\n{text[:6000]}",
            temperature=0.2,
        ).strip()
    except Exception:
        return text[:400]
