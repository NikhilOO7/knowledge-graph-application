"""Pydantic models for API request/response and inter-agent data."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Buckets
# --------------------------------------------------------------------------- #
class BucketCreate(BaseModel):
    name: str
    description: Optional[str] = None


class Bucket(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    # Inferred per-bucket ontology (entity + relationship types)
    entity_types: List[str] = Field(default_factory=list)
    relationship_types: List[str] = Field(default_factory=list)
    document_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
class Document(BaseModel):
    id: str
    bucket_id: Optional[str] = None
    title: str
    source_type: str = "upload"  # upload | text | url
    filename: Optional[str] = None
    char_count: int = 0
    processing_status: str = "pending"
    processing_progress: int = 0
    processing_error: Optional[str] = None
    created_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
class GraphNode(BaseModel):
    id: str
    bucket_id: str
    type: str
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    bucket_id: str
    source_id: str
    target_id: str
    type: str
    confidence: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class Subgraph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class TypeCount(BaseModel):
    type: str
    count: int


class GraphStats(BaseModel):
    bucket_id: Optional[str] = None
    nodes: Dict[str, Any]  # {"total": int, "byType": [TypeCount]}
    edges: Dict[str, Any]


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
class TextIngestRequest(BaseModel):
    title: str
    text: str
    bucket_id: Optional[str] = None  # force a specific bucket; else auto-route
    auto_process: bool = True


class IngestResponse(BaseModel):
    job_id: str
    document_id: str
    bucket_id: Optional[str] = None
    bucket_action: str  # "created" | "appended" | "pending"
    status: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    stage: Optional[str] = None
    progress: int = 0
    document_id: Optional[str] = None
    bucket_id: Optional[str] = None
    bucket_action: Optional[str] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Graph QA
# --------------------------------------------------------------------------- #
class QARequest(BaseModel):
    bucket_id: str
    question: str


class QAResponse(BaseModel):
    question: str
    answer: str
    cypher: Optional[str] = None
    context: List[Dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Internal agent payloads (used between pipeline stages)
# --------------------------------------------------------------------------- #
class ExtractedEntity(BaseModel):
    mention: str
    type: str
    confidence: float = 0.7


class ExtractedRelationship(BaseModel):
    source_name: str
    target_name: str
    type: str
    evidence: str = ""
    confidence: float = 0.6


class ResolvedEntity(BaseModel):
    mention: str
    canonical_name: str
    type: str
    is_new: bool = True
    confidence: float = 1.0
