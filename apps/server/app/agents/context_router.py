"""Context-Router agent.

Decides whether an uploaded document belongs to an EXISTING context bucket
(append + enrich its graph) or needs a NEW bucket. This is the core of the
"if the context is already present in memory, use that context bucket and
append the knowledge graph" requirement.

Strategy:
  1. Embed the document -> signature vector + topical summary.
  2. Compare against every existing bucket's signature vector (cosine sim).
  3. If the best match >= threshold, append to that bucket. For borderline
     matches an LLM tie-breaker confirms topical relevance using the summaries.
  4. Otherwise create a new bucket (named by the LLM from the summary).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..config import settings
from ..services import embeddings, llm


@dataclass
class BucketSignature:
    id: str
    name: str
    summary: str
    vector: List[float]


@dataclass
class RouteDecision:
    action: str  # "append" | "create"
    bucket_id: Optional[str]
    bucket_name: str
    similarity: float
    reason: str


def route(
    doc_summary: str,
    doc_vector: List[float],
    existing: List[BucketSignature],
) -> RouteDecision:
    best: Optional[BucketSignature] = None
    best_sim = 0.0
    for sig in existing:
        sim = embeddings.cosine_similarity(doc_vector, sig.vector or [])
        if sim > best_sim:
            best_sim, best = sim, sig

    threshold = settings.bucket_match_threshold

    if best and best_sim >= threshold:
        return RouteDecision("append", best.id, best.name, best_sim,
                             f"High similarity ({best_sim:.2f}) to bucket '{best.name}'.")

    # Borderline band: let an LLM judge topical overlap using summaries.
    if best and best_sim >= threshold - 0.12 and llm.settings.llm_is_configured:
        if _llm_confirms_match(doc_summary, best.summary):
            return RouteDecision("append", best.id, best.name, best_sim,
                                 f"LLM confirmed topical match to '{best.name}' (sim {best_sim:.2f}).")

    name = _name_new_bucket(doc_summary)
    return RouteDecision("create", None, name, best_sim,
                         f"No bucket above threshold (best {best_sim:.2f}); created '{name}'.")


def _llm_confirms_match(doc_summary: str, bucket_summary: str) -> bool:
    try:
        data = llm.chat_json(
            system="You decide if two text descriptions concern the SAME subject "
            "area such that their knowledge graphs should be merged.",
            user=f"Document:\n{doc_summary}\n\nExisting bucket:\n{bucket_summary}\n\n"
            'Return {"same_subject": true|false}.',
            temperature=0.0,
        )
        return bool(data.get("same_subject"))
    except Exception:
        return False


def _name_new_bucket(doc_summary: str) -> str:
    if not doc_summary:
        return "Untitled Context"
    if not llm.settings.llm_is_configured:
        return doc_summary.split(".")[0][:60].strip() or "Untitled Context"
    try:
        data = llm.chat_json(
            system="You name knowledge-graph context buckets.",
            user=f"Give a short (2-5 word) title for a knowledge bucket about:\n{doc_summary}\n"
            'Return {"name": "..."}.',
            temperature=0.3,
        )
        return (data.get("name") or "Untitled Context").strip()[:60]
    except Exception:
        return doc_summary.split(".")[0][:60].strip() or "Untitled Context"
