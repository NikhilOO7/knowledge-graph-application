"""Persistence helpers shared by the LangGraph pipeline.

Writes go to two stores:
  * Neo4j   — the graph itself (entities + relationships), scoped by bucket_id
  * Postgres — provenance rows + the bucket's signature/ontology/count cache
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..db.neo4j_client import neo4j_client
from ..db.postgres import BucketRow, SourceRow, get_session
from ..services import embeddings


def persist_chunk(
    bucket_id: str,
    document_id: str,
    section: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Upsert a chunk's entities + relationships into Neo4j and record provenance."""
    created_nodes = 0
    for ent in entities:
        neo4j_client.upsert_entity(
            bucket_id=bucket_id,
            name=ent["mention"],
            type_=ent.get("type", "concept"),
            description=ent.get("description", ""),
        )
        created_nodes += 1

    # Make sure both endpoints of every relationship exist as nodes.
    for rel in relationships:
        for endpoint in (rel["source_name"], rel["target_name"]):
            neo4j_client.upsert_entity(bucket_id=bucket_id, name=endpoint, type_="concept")

    created_edges = 0
    for rel in relationships:
        edge_id = neo4j_client.create_relationship(
            bucket_id=bucket_id,
            source_name=rel["source_name"],
            target_name=rel["target_name"],
            type_=rel["type"],
            confidence=rel.get("confidence", 0.6),
            properties={"evidence": rel.get("evidence", "")},
        )
        if edge_id:
            created_edges += 1
            _record_source(bucket_id, document_id, edge_id, section, rel.get("evidence", ""))

    return {"nodes": created_nodes, "edges": created_edges}


def _record_source(bucket_id, document_id, edge_id, section, evidence) -> None:
    if not evidence:
        return
    session = get_session()
    try:
        session.add(
            SourceRow(
                edge_id=edge_id,
                bucket_id=bucket_id,
                document_id=document_id,
                section=section,
                extracted_text=evidence[:1000],
            )
        )
        session.commit()
    finally:
        session.close()


def update_bucket_after_document(
    bucket_id: str,
    doc_vector: List[float],
    doc_summary: str,
    ontology: Dict[str, List[str]],
) -> None:
    """Roll the document's signature into the bucket, refresh ontology + counts."""
    session = get_session()
    try:
        bucket = session.get(BucketRow, bucket_id)
        if not bucket:
            return

        # Rolling mean of signature vectors weighted by prior doc count.
        prior = bucket.signature_doc_count or 0
        existing_vec = bucket.signature_vector or []
        if existing_vec and len(existing_vec) == len(doc_vector) and prior > 0:
            merged = [
                (existing_vec[i] * prior + doc_vector[i]) / (prior + 1)
                for i in range(len(doc_vector))
            ]
        else:
            merged = doc_vector
        bucket.signature_vector = merged
        bucket.signature_doc_count = prior + 1

        # Keep a concise rolling summary.
        if doc_summary:
            if bucket.signature_summary:
                bucket.signature_summary = (bucket.signature_summary + " | " + doc_summary)[:1200]
            else:
                bucket.signature_summary = doc_summary

        bucket.entity_types = ontology.get("entity_types", bucket.entity_types or [])
        bucket.relationship_types = ontology.get(
            "relationship_types", bucket.relationship_types or []
        )

        counts = neo4j_client.counts(bucket_id)
        bucket.node_count = counts["nodes"]
        bucket.edge_count = counts["edges"]
        session.commit()
    finally:
        session.close()
