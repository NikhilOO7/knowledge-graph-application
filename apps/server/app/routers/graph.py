"""Graph endpoints — all scoped to a context bucket."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..db.neo4j_client import neo4j_client

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/nodes")
def list_nodes(
    bucket_id: str = Query(...),
    type: str | None = None,
    search: str | None = None,
    limit: int = Query(default=200, le=1000),
):
    nodes = neo4j_client.list_nodes(bucket_id, type_=type, search=search, limit=limit)
    return {"nodes": nodes}


@router.get("/nodes/{node_id}")
def get_node(node_id: str):
    detail = neo4j_client.get_node_with_edges(node_id)
    if not detail:
        raise HTTPException(404, "Node not found")
    return detail


@router.get("/edges")
def list_edges(
    bucket_id: str = Query(...),
    type: str | None = None,
    limit: int = Query(default=400, le=2000),
):
    return {"edges": neo4j_client.list_edges(bucket_id, type_=type, limit=limit)}


@router.get("/subgraph")
def subgraph(node_id: str = Query(...), depth: int = Query(default=1, ge=1, le=4)):
    return neo4j_client.subgraph(node_id, depth)


@router.get("/stats")
def stats(bucket_id: str = Query(...)):
    data = neo4j_client.stats(bucket_id)
    data["bucket_id"] = bucket_id
    return data
