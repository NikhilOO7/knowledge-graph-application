"""LangGraph orchestration of the ingestion pipeline.

Flow (a StateGraph, so each step is observable and individually retryable):

    prepare ─► route ─► ontology ─► extract ─► finalize

  prepare   load document text, summarise + embed it (the context signature)
  route     Context-Router decides append-to-existing vs create-new bucket
  ontology  Ontology agent infers/extends the bucket's entity & relation types
  extract   per chunk, run the CrewAI extraction crew and persist to Neo4j
  finalize  roll signature into the bucket, refresh counts, mark doc complete

CrewAI lives *inside* the extract node; LangGraph owns the overall state machine.
"""
from __future__ import annotations

from typing import Optional

from langgraph.graph import END, START, StateGraph

from ..agents import context_router, ontology as ontology_agent
from ..agents.crew import run_extraction_crew
from ..db.neo4j_client import neo4j_client
from ..db.postgres import BucketRow, DocumentRow, get_session
from ..services import documents as doc_svc
from ..services import embeddings
from . import persist
from .state import PipelineState


def _emit(state: PipelineState, stage: str, percent: int) -> None:
    cb = state.get("progress")
    if cb:
        try:
            cb(stage, percent)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def node_prepare(state: PipelineState) -> PipelineState:
    _emit(state, "preparing", 5)
    session = get_session()
    try:
        doc = session.get(DocumentRow, state["document_id"])
        if not doc or not doc.raw_text:
            return {"error": "Document has no extractable text."}
        text = doc.raw_text
    finally:
        session.close()

    _emit(state, "summarizing", 12)
    summary = embeddings.summarize(text)
    vector = embeddings.embed(summary or text[:4000])
    chunks = doc_svc.chunk_text(text)
    return {"raw_text": text, "summary": summary, "vector": vector, "chunks": chunks}


def node_route(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return {}
    _emit(state, "routing_context", 20)
    session = get_session()
    try:
        # Explicit bucket wins.
        if state.get("forced_bucket_id"):
            bucket = session.get(BucketRow, state["forced_bucket_id"])
            if bucket:
                return {
                    "bucket_id": bucket.id,
                    "bucket_action": "appended",
                    "route_reason": "User selected this bucket.",
                }

        existing = [
            context_router.BucketSignature(
                id=b.id,
                name=b.name,
                summary=b.signature_summary or "",
                vector=b.signature_vector or [],
            )
            for b in session.query(BucketRow).all()
        ]
        decision = context_router.route(state["summary"], state["vector"], existing)

        if decision.action == "append" and decision.bucket_id:
            return {
                "bucket_id": decision.bucket_id,
                "bucket_action": "appended",
                "route_reason": decision.reason,
            }

        bucket = BucketRow(name=decision.bucket_name, description=state["summary"][:500])
        session.add(bucket)
        session.commit()
        bucket_id = bucket.id
    finally:
        session.close()

    return {"bucket_id": bucket_id, "bucket_action": "created", "route_reason": decision.reason}


def node_ontology(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return {}
    _emit(state, "inferring_ontology", 30)
    session = get_session()
    try:
        bucket = session.get(BucketRow, state["bucket_id"])
        existing_e = (bucket.entity_types or []) if bucket else []
        existing_r = (bucket.relationship_types or []) if bucket else []
    finally:
        session.close()

    onto = ontology_agent.infer_ontology(state["raw_text"][:6000], existing_e, existing_r)
    return {"ontology": onto}


def node_extract(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return {}
    bucket_id = state["bucket_id"]
    chunks = state.get("chunks", [])
    onto = state.get("ontology", {})
    entity_types = onto.get("entity_types", ["concept"])
    rel_types = onto.get("relationship_types", ["relates_to"])

    total_nodes = total_edges = 0
    n = max(len(chunks), 1)
    for i, chunk in enumerate(chunks):
        section = doc_svc.detect_section(chunk, i, len(chunks))
        existing = neo4j_client.list_nodes(bucket_id, limit=60)
        existing_min = [{"name": e["name"], "type": e["type"]} for e in existing]

        result = run_extraction_crew(
            text=chunk,
            section=section,
            entity_types=entity_types,
            relationship_types=rel_types,
            existing_entities=existing_min,
            bucket_id=bucket_id,
        )
        counts = persist.persist_chunk(
            bucket_id,
            state["document_id"],
            section,
            result["entities"],
            result["relationships"],
        )
        total_nodes += counts["nodes"]
        total_edges += counts["edges"]
        _emit(state, "extracting", 30 + int(60 * (i + 1) / n))

    return {"stats": {"nodes_added": total_nodes, "edges_added": total_edges, "chunks": len(chunks)}}


def node_finalize(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return {}
    _emit(state, "finalizing", 95)
    persist.update_bucket_after_document(
        state["bucket_id"], state["vector"], state["summary"], state.get("ontology", {})
    )
    _emit(state, "completed", 100)
    return {}


# --------------------------------------------------------------------------- #
# Graph construction
# --------------------------------------------------------------------------- #
def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("prepare", node_prepare)
    graph.add_node("route", node_route)
    graph.add_node("ontology", node_ontology)
    graph.add_node("extract", node_extract)
    graph.add_node("finalize", node_finalize)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "route")
    graph.add_edge("route", "ontology")
    graph.add_edge("ontology", "extract")
    graph.add_edge("extract", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def run_pipeline(document_id: str, forced_bucket_id: Optional[str], progress) -> PipelineState:
    initial: PipelineState = {
        "document_id": document_id,
        "forced_bucket_id": forced_bucket_id,
        "progress": progress,
    }
    return get_pipeline().invoke(initial)
