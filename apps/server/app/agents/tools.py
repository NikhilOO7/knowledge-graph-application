"""CrewAI tools the extraction crew can call.

The resolver agent uses ``ExistingEntitiesTool`` to look up entities already in
the bucket's graph, so it can dedup/merge against them (e.g. map an acronym to
an existing fully-spelled-out entity) instead of creating duplicates.
"""
from __future__ import annotations

import json
from typing import Optional, Type

try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field

    _CREW_TOOLS_AVAILABLE = True
except Exception:  # pragma: no cover - crewai optional at import time
    _CREW_TOOLS_AVAILABLE = False
    BaseTool = object  # type: ignore


if _CREW_TOOLS_AVAILABLE:

    class _ExistingEntitiesInput(BaseModel):
        search: Optional[str] = Field(
            default=None, description="Optional substring to filter entity names"
        )

    class ExistingEntitiesTool(BaseTool):
        name: str = "existing_bucket_entities"
        description: str = (
            "Return entities that already exist in the current context bucket's "
            "knowledge graph, so you can match/dedup extracted mentions against them. "
            "Returns a JSON list of {name, type}."
        )
        args_schema: Type[BaseModel] = _ExistingEntitiesInput
        bucket_id: str = ""

        def _run(self, search: Optional[str] = None) -> str:
            from ..db.neo4j_client import neo4j_client

            if not self.bucket_id:
                return "[]"
            nodes = neo4j_client.list_nodes(self.bucket_id, search=search, limit=80)
            return json.dumps([{"name": n["name"], "type": n["type"]} for n in nodes])

    def make_existing_entities_tool(bucket_id: str) -> "ExistingEntitiesTool":
        return ExistingEntitiesTool(bucket_id=bucket_id)

else:  # pragma: no cover

    def make_existing_entities_tool(bucket_id: str):
        return None
