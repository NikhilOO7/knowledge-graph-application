"""Ontology / Schema agent.

Given a document (and any ontology a bucket already has), infer the entity and
relationship *types* relevant to the domain. This keeps the graph generic with no hardcoded
domain enums: a legal-contracts bucket
gets {party, clause, obligation, ...} while a biology bucket gets
{gene, protein, pathway, ...}.
"""
from __future__ import annotations

from typing import Dict, List

from ..services import llm

SYSTEM = """You are a knowledge-engineering specialist who designs lightweight ontologies.
Given a document, infer the ENTITY TYPES and RELATIONSHIP TYPES that best capture
the knowledge in its domain. Keep them generic, reusable, and lowercase_snake_case.

Return JSON:
{
  "domain": "short label for the subject area",
  "entity_types": ["...", "..."],        // 4-8 types, e.g. concept, method, organization, person, dataset, metric, event, location
  "relationship_types": ["...", "..."]   // 5-10 verbs, e.g. relates_to, part_of, uses, causes, located_in, authored_by
}

Rules:
- Always include generic fallbacks "concept" (entity) and "relates_to" (relationship).
- Prefer broadly applicable types over hyper-specific ones."""

_DEFAULT_ENTITY_TYPES = ["concept", "entity", "method", "organization", "person", "dataset", "metric"]
_DEFAULT_REL_TYPES = ["relates_to", "part_of", "uses", "causes", "authored_by", "located_in"]


def infer_ontology(
    sample_text: str,
    existing_entity_types: List[str] | None = None,
    existing_relationship_types: List[str] | None = None,
) -> Dict[str, List[str]]:
    existing_entity_types = existing_entity_types or []
    existing_relationship_types = existing_relationship_types or []

    if not llm.settings.llm_is_configured:
        return _merge(
            {"entity_types": _DEFAULT_ENTITY_TYPES, "relationship_types": _DEFAULT_REL_TYPES},
            existing_entity_types,
            existing_relationship_types,
        )

    user = (
        "Existing bucket ontology (extend, do not discard):\n"
        f"  entity_types: {existing_entity_types}\n"
        f"  relationship_types: {existing_relationship_types}\n\n"
        f"Document sample:\n\"\"\"\n{sample_text[:6000]}\n\"\"\""
    )
    try:
        data = llm.chat_json(SYSTEM, user, temperature=0.2)
    except Exception:
        data = {"entity_types": _DEFAULT_ENTITY_TYPES, "relationship_types": _DEFAULT_REL_TYPES}
    return _merge(data, existing_entity_types, existing_relationship_types)


def _merge(
    data: Dict, existing_entities: List[str], existing_rels: List[str]
) -> Dict[str, List[str]]:
    entities = _dedup(existing_entities + list(data.get("entity_types") or []) + ["concept"])
    rels = _dedup(existing_rels + list(data.get("relationship_types") or []) + ["relates_to"])
    return {
        "domain": data.get("domain", ""),
        "entity_types": entities,
        "relationship_types": rels,
    }


def _dedup(items: List[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        key = str(item).strip().lower().replace(" ", "_")
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
