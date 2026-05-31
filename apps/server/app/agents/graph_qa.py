"""Graph-QA / retrieval agent (GraphRAG over a single bucket).

Answers a natural-language question by:
  1. pulling candidate entities from the question (keyword + LLM assist),
  2. retrieving their neighbourhoods from Neo4j as relationship triples,
  3. asking the LLM to answer grounded ONLY in those retrieved triples.

Returns the answer plus the triples used as evidence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ..db.neo4j_client import neo4j_client
from ..services import llm

_STOPWORDS = {
    "what", "which", "who", "how", "does", "the", "and", "for", "are", "with",
    "that", "this", "from", "have", "has", "was", "were", "use", "used", "about",
    "into", "between", "their", "they", "them", "show", "list", "find", "all",
}


def answer_question(bucket_id: str, question: str) -> Dict[str, Any]:
    keywords = _keywords(question)
    triples = _retrieve_triples(bucket_id, keywords)

    if not triples:
        # Fall back to a broad sample of the bucket's graph.
        triples = _sample_triples(bucket_id)

    context_lines = [
        f"({t['source']}) -[{t['type']}]-> ({t['target']})" for t in triples
    ]
    context_block = "\n".join(context_lines[:60]) or "(no relationships found)"

    if not llm.settings.llm_is_configured:
        answer = (
            "LLM not configured. Retrieved relationships:\n" + context_block
        )
    else:
        answer = llm.chat(
            system="You answer questions strictly from the provided knowledge-graph "
            "relationships. If the answer is not present, say so. Cite entity names.",
            user=f"Knowledge graph relationships:\n{context_block}\n\n"
            f"Question: {question}\n\nAnswer concisely using only the relationships above.",
            temperature=0.2,
        )

    return {"question": question, "answer": answer, "context": triples[:60]}


def _keywords(question: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", question)
    kws = [w for w in words if w.lower() not in _STOPWORDS and len(w) > 2]
    # keep original casing for matching, dedup
    seen, out = set(), []
    for w in kws:
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out[:8]


def _retrieve_triples(bucket_id: str, keywords: List[str]) -> List[Dict[str, str]]:
    triples: List[Dict[str, str]] = []
    seen_edges = set()
    for kw in keywords:
        for node in neo4j_client.list_nodes(bucket_id, search=kw, limit=5):
            detail = neo4j_client.get_node_with_edges(node["id"])
            if not detail:
                continue
            for edge in detail["outgoing_edges"] + detail["incoming_edges"]:
                if edge["id"] in seen_edges:
                    continue
                seen_edges.add(edge["id"])
                triples.append(_triple(bucket_id, edge))
    return [t for t in triples if t]


def _sample_triples(bucket_id: str) -> List[Dict[str, str]]:
    edges = neo4j_client.list_edges(bucket_id, limit=40)
    return [t for t in (_triple(bucket_id, e) for e in edges) if t]


def _triple(bucket_id: str, edge: Dict[str, Any]) -> Dict[str, str] | None:
    src = neo4j_client.get_node_with_edges(edge["source_id"])
    tgt = neo4j_client.get_node_with_edges(edge["target_id"])
    if not src or not tgt:
        return None
    return {
        "source": src["node"]["name"],
        "type": edge["type"],
        "target": tgt["node"]["name"],
        "confidence": edge.get("confidence", 1.0),
    }
