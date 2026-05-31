"""Shared state object for the LangGraph extraction pipeline."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypedDict


class PipelineState(TypedDict, total=False):
    # Inputs
    document_id: str
    forced_bucket_id: Optional[str]
    progress: Callable[[str, int], None]  # (stage, percent) -> None

    # Derived
    raw_text: str
    summary: str
    vector: List[float]
    chunks: List[str]

    # Routing
    bucket_id: str
    bucket_action: str  # "created" | "appended"
    route_reason: str

    # Ontology
    ontology: Dict[str, List[str]]

    # Accumulators
    stats: Dict[str, int]
    error: Optional[str]
