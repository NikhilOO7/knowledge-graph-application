"""CrewAI extraction crew.

A crew of three cooperating agents turns a chunk of document text into
validated graph data, guided by the bucket's inferred ontology:

  1. Extractor  — pulls entity mentions + candidate relationships (high recall)
  2. Resolver   — maps mentions to canonical names, dedups against the bucket
  3. Validator  — checks type/logic consistency, drops weak relationships

This is the unit LangGraph invokes inside its ``extract`` node (one run per
chunk). If CrewAI is unavailable or the LLM is unconfigured, a direct-LLM
fallback implements the same three steps so the pipeline still runs.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ..services import llm
from .tools import make_existing_entities_tool


def run_extraction_crew(
    text: str,
    section: str,
    entity_types: List[str],
    relationship_types: List[str],
    existing_entities: List[Dict[str, str]],
    bucket_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return {"entities": [...], "relationships": [...]} for one chunk."""
    crew_result = _try_crewai(
        text, section, entity_types, relationship_types, existing_entities, bucket_id
    )
    if crew_result is not None:
        return crew_result
    return _fallback_direct(text, section, entity_types, relationship_types, existing_entities)


# --------------------------------------------------------------------------- #
# CrewAI path
# --------------------------------------------------------------------------- #
def _try_crewai(
    text, section, entity_types, relationship_types, existing_entities, bucket_id
):
    if not llm.settings.llm_is_configured:
        return None
    try:
        from crewai import Agent, Crew, Process, Task
    except Exception:
        return None

    try:
        crew_llm = llm.get_crew_llm()
        et = ", ".join(entity_types)
        rt = ", ".join(relationship_types)

        extractor = Agent(
            role="Knowledge Extractor",
            goal="Extract every entity mention and candidate relationship from a "
            "passage, favouring recall.",
            backstory="You read documents from any domain and surface the entities "
            "and how they connect, using the provided ontology.",
            llm=crew_llm,
            verbose=False,
            allow_delegation=False,
        )
        resolver = Agent(
            role="Entity Resolver",
            goal="Map raw mentions to canonical entity names and dedup them against "
            "entities already in this context bucket.",
            backstory="You normalise names, expand acronyms, and avoid creating "
            "duplicate nodes for the same real-world entity.",
            llm=crew_llm,
            tools=[t for t in [make_existing_entities_tool(bucket_id)] if t],
            verbose=False,
            allow_delegation=False,
        )
        validator = Agent(
            role="Graph Validator",
            goal="Keep only well-typed, well-evidenced relationships.",
            backstory="You enforce ontology type compatibility and reject weak or "
            "contradictory relationships.",
            llm=crew_llm,
            verbose=False,
            allow_delegation=False,
        )

        extract_task = Task(
            description=(
                f"Document section: {section}\n"
                f"Allowed entity types: {et}\n"
                f"Allowed relationship types: {rt}\n\n"
                f'TEXT:\n"""\n{text}\n"""\n\n'
                "Extract entities and relationships. Output JSON:\n"
                '{"entities":[{"mention":"...","type":"<one of entity types>","confidence":0.0}],'
                '"relationships":[{"source_name":"...","target_name":"...",'
                '"type":"<one of relationship types>","evidence":"...","confidence":0.0}]}'
            ),
            expected_output="A JSON object with entities and relationships arrays.",
            agent=extractor,
        )
        resolve_task = Task(
            description=(
                "Using the extractor output and the existing bucket entities "
                "(call the existing_bucket_entities tool), canonicalise entity names "
                "and rewrite relationships to use canonical names. Keep the same JSON "
                "shape. Use existing canonical names when a mention refers to the same "
                "entity."
            ),
            expected_output="A JSON object with canonicalised entities and relationships.",
            agent=resolver,
            context=[extract_task],
        )
        validate_task = Task(
            description=(
                f"Allowed relationship types: {rt}. Drop relationships whose type is "
                "not allowed, whose endpoints are not in entities, or whose confidence "
                "is below 0.4. Return the final JSON with the same shape."
            ),
            expected_output="Final validated JSON object with entities and relationships.",
            agent=validator,
            context=[resolve_task],
        )

        crew = Crew(
            agents=[extractor, resolver, validator],
            tasks=[extract_task, resolve_task, validate_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        raw = getattr(result, "raw", None) or str(result)
        return _coerce(raw, entity_types, relationship_types)
    except Exception as exc:  # noqa: BLE001
        print(f"[crew] CrewAI run failed, falling back: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Direct-LLM fallback (same 3 logical steps, one call)
# --------------------------------------------------------------------------- #
def _fallback_direct(text, section, entity_types, relationship_types, existing_entities):
    if not llm.settings.llm_is_configured:
        return {"entities": [], "relationships": []}
    et, rt = ", ".join(entity_types), ", ".join(relationship_types)
    existing = json.dumps(existing_entities[:60])
    system = (
        "You are a 3-in-1 knowledge graph pipeline: extract entities/relationships, "
        "resolve them to canonical names (dedup against existing entities), and "
        "validate types. Use ONLY the allowed types."
    )
    user = (
        f"Section: {section}\nEntity types: {et}\nRelationship types: {rt}\n"
        f"Existing bucket entities (dedup against these): {existing}\n\n"
        f'TEXT:\n"""\n{text}\n"""\n\n'
        "Return JSON: {\"entities\":[{\"mention\":\"...\",\"type\":\"...\",\"confidence\":0.0}],"
        "\"relationships\":[{\"source_name\":\"...\",\"target_name\":\"...\",\"type\":\"...\","
        "\"evidence\":\"...\",\"confidence\":0.0}]}"
    )
    try:
        data = llm.chat_json(system, user, temperature=0.2)
        return _coerce(json.dumps(data), entity_types, relationship_types)
    except Exception as exc:  # noqa: BLE001
        print(f"[crew] fallback extraction failed: {exc}")
        return {"entities": [], "relationships": []}


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def _coerce(raw: str, entity_types, relationship_types) -> Dict[str, List[Dict[str, Any]]]:
    try:
        data = json.loads(_extract_json(raw))
    except Exception:
        return {"entities": [], "relationships": []}

    et_set = {t.lower() for t in entity_types}
    rt_set = {t.lower() for t in relationship_types}

    entities = []
    for e in data.get("entities", []) or []:
        name = (e.get("mention") or e.get("name") or "").strip()
        if not name:
            continue
        etype = (e.get("type") or "concept").strip().lower().replace(" ", "_")
        if etype not in et_set:
            etype = "concept"
        entities.append(
            {"mention": name, "type": etype, "confidence": float(e.get("confidence", 0.7) or 0.7)}
        )

    rels = []
    for r in data.get("relationships", []) or []:
        src = (r.get("source_name") or r.get("source") or r.get("subject") or "").strip()
        tgt = (r.get("target_name") or r.get("target") or r.get("object") or "").strip()
        rtype = (r.get("type") or r.get("predicate") or "relates_to").strip().lower().replace(" ", "_")
        if not src or not tgt:
            continue
        if rtype not in rt_set:
            rtype = "relates_to"
        conf = float(r.get("confidence", 0.6) or 0.6)
        if conf < 0.4:
            continue
        rels.append(
            {
                "source_name": src,
                "target_name": tgt,
                "type": rtype,
                "evidence": (r.get("evidence") or "")[:500],
                "confidence": conf,
            }
        )
    return {"entities": entities, "relationships": rels}


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if "```" in raw:
        segs = raw.split("```")
        for seg in segs:
            seg = seg[4:] if seg.startswith("json") else seg
            if "{" in seg:
                raw = seg
                break
    start, end = raw.find("{"), raw.rfind("}")
    return raw[start : end + 1] if start != -1 and end != -1 else "{}"
