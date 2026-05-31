"""Neo4j layer — stores the knowledge graph itself.

Model:
  (:Entity {id, bucket_id, type, name, normalized_name, description, properties})
  (:Entity)-[:REL {id, bucket_id, type, confidence, properties}]->(:Entity)

Entities and relationships are *scoped to a bucket* via the ``bucket_id``
property, so every query filters on it. We use a single relationship type
``:REL`` with a ``type`` property (rather than dynamic Cypher relationship
types) so arbitrary, ontology-inferred relationship names are safe to store.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

from ..config import settings


def _uuid() -> str:
    return str(uuid.uuid4())


def _norm(name: str) -> str:
    return (name or "").strip().lower()


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @contextmanager
    def session(self):
        sess = self.driver.session(database=settings.neo4j_database)
        try:
            yield sess
        finally:
            sess.close()

    # --------------------------------------------------------------------- #
    # Schema / health
    # --------------------------------------------------------------------- #
    def ensure_constraints(self) -> None:
        with self.session() as s:
            s.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )
            s.run(
                "CREATE INDEX entity_bucket IF NOT EXISTS "
                "FOR (e:Entity) ON (e.bucket_id)"
            )
            s.run(
                "CREATE INDEX entity_norm IF NOT EXISTS "
                "FOR (e:Entity) ON (e.bucket_id, e.normalized_name)"
            )

    def check_connection(self) -> bool:
        try:
            with self.session() as s:
                s.run("RETURN 1").consume()
            return True
        except Exception:
            return False

    # --------------------------------------------------------------------- #
    # Writes
    # --------------------------------------------------------------------- #
    def upsert_entity(
        self,
        bucket_id: str,
        name: str,
        type_: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or update an entity within a bucket. Returns its node id.

        Dedup is by (bucket_id, normalized_name) so the same concept appearing
        in multiple documents merges into one node — this is what makes
        appending to an existing bucket *enrich* rather than duplicate.
        """
        normalized = _norm(name)
        with self.session() as s:
            rec = s.run(
                """
                MERGE (e:Entity {bucket_id: $bucket_id, normalized_name: $normalized})
                ON CREATE SET e.id = $new_id, e.name = $name, e.type = $type,
                              e.description = $description, e.properties = $properties
                ON MATCH SET e.description = CASE WHEN $description <> '' THEN $description ELSE e.description END
                RETURN e.id AS id
                """,
                bucket_id=bucket_id,
                normalized=normalized,
                new_id=_uuid(),
                name=name,
                type=type_,
                description=description or "",
                properties=properties or {},
            ).single()
            return rec["id"]

    def create_relationship(
        self,
        bucket_id: str,
        source_name: str,
        target_name: str,
        type_: str,
        confidence: float = 0.6,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a relationship between two existing entities (by name)."""
        edge_id = _uuid()
        with self.session() as s:
            rec = s.run(
                """
                MATCH (a:Entity {bucket_id: $bucket_id, normalized_name: $src})
                MATCH (b:Entity {bucket_id: $bucket_id, normalized_name: $tgt})
                MERGE (a)-[r:REL {bucket_id: $bucket_id, type: $type}]->(b)
                ON CREATE SET r.id = $edge_id, r.confidence = $confidence,
                              r.properties = $properties
                ON MATCH SET r.confidence = (r.confidence + $confidence) / 2.0
                RETURN r.id AS id
                """,
                bucket_id=bucket_id,
                src=_norm(source_name),
                tgt=_norm(target_name),
                type=type_,
                edge_id=edge_id,
                confidence=confidence,
                properties=properties or {},
            ).single()
            return rec["id"] if rec else None

    def delete_bucket_graph(self, bucket_id: str) -> None:
        with self.session() as s:
            s.run(
                "MATCH (e:Entity {bucket_id: $bucket_id}) DETACH DELETE e",
                bucket_id=bucket_id,
            )

    # --------------------------------------------------------------------- #
    # Reads
    # --------------------------------------------------------------------- #
    def list_nodes(
        self,
        bucket_id: str,
        type_: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        cypher = "MATCH (e:Entity {bucket_id: $bucket_id}) WHERE 1=1"
        params: Dict[str, Any] = {"bucket_id": bucket_id, "limit": limit}
        if type_:
            cypher += " AND e.type = $type"
            params["type"] = type_
        if search:
            cypher += " AND toLower(e.name) CONTAINS toLower($search)"
            params["search"] = search
        cypher += " RETURN e LIMIT $limit"
        with self.session() as s:
            return [self._node_dict(r["e"]) for r in s.run(cypher, **params)]

    def list_edges(
        self, bucket_id: str, type_: Optional[str] = None, limit: int = 400
    ) -> List[Dict[str, Any]]:
        cypher = (
            "MATCH (a:Entity)-[r:REL {bucket_id: $bucket_id}]->(b:Entity) WHERE 1=1"
        )
        params: Dict[str, Any] = {"bucket_id": bucket_id, "limit": limit}
        if type_:
            cypher += " AND r.type = $type"
            params["type"] = type_
        cypher += " RETURN r, a.id AS source_id, b.id AS target_id LIMIT $limit"
        with self.session() as s:
            return [self._edge_dict(r) for r in s.run(cypher, **params)]

    def get_node_with_edges(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self.session() as s:
            node_rec = s.run(
                "MATCH (e:Entity {id: $id}) RETURN e", id=node_id
            ).single()
            if not node_rec:
                return None
            out = s.run(
                """
                MATCH (e:Entity {id: $id})-[r:REL]->(b:Entity)
                RETURN r, e.id AS source_id, b.id AS target_id
                """,
                id=node_id,
            )
            inc = s.run(
                """
                MATCH (a:Entity)-[r:REL]->(e:Entity {id: $id})
                RETURN r, a.id AS source_id, e.id AS target_id
                """,
                id=node_id,
            )
            return {
                "node": self._node_dict(node_rec["e"]),
                "outgoing_edges": [self._edge_dict(r) for r in out],
                "incoming_edges": [self._edge_dict(r) for r in inc],
            }

    def subgraph(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        depth = max(1, min(depth, 4))
        with self.session() as s:
            result = s.run(
                f"""
                MATCH path = (e:Entity {{id: $id}})-[:REL*1..{depth}]-(other:Entity)
                WITH collect(path) AS paths
                UNWIND paths AS p
                WITH nodes(p) AS ns, relationships(p) AS rs
                UNWIND ns AS n
                WITH collect(DISTINCT n) AS allNodes, collect(rs) AS relLists
                RETURN allNodes,
                       reduce(acc = [], rl IN relLists | acc + rl) AS allRels
                """,
                id=node_id,
            ).single()
            if not result:
                return {"nodes": [], "edges": []}
            nodes = [self._node_dict(n) for n in result["allNodes"]]
            edges = []
            seen = set()
            for rel in result["allRels"]:
                if rel.id in seen:
                    continue
                seen.add(rel.id)
                edges.append(
                    {
                        "id": rel.get("id"),
                        "bucket_id": rel.get("bucket_id"),
                        "source_id": rel.start_node.get("id"),
                        "target_id": rel.end_node.get("id"),
                        "type": rel.get("type"),
                        "confidence": rel.get("confidence", 1.0),
                        "properties": rel.get("properties", {}),
                    }
                )
            return {"nodes": nodes, "edges": edges}

    def stats(self, bucket_id: str) -> Dict[str, Any]:
        with self.session() as s:
            node_rows = s.run(
                """
                MATCH (e:Entity {bucket_id: $bucket_id})
                RETURN e.type AS type, count(*) AS count
                """,
                bucket_id=bucket_id,
            )
            nodes_by_type = [{"type": r["type"], "count": r["count"]} for r in node_rows]
            edge_rows = s.run(
                """
                MATCH ()-[r:REL {bucket_id: $bucket_id}]->()
                RETURN r.type AS type, count(*) AS count
                """,
                bucket_id=bucket_id,
            )
            edges_by_type = [{"type": r["type"], "count": r["count"]} for r in edge_rows]
        return {
            "nodes": {
                "total": sum(x["count"] for x in nodes_by_type),
                "byType": nodes_by_type,
            },
            "edges": {
                "total": sum(x["count"] for x in edges_by_type),
                "byType": edges_by_type,
            },
        }

    def counts(self, bucket_id: str) -> Dict[str, int]:
        with self.session() as s:
            rec = s.run(
                """
                MATCH (e:Entity {bucket_id: $bucket_id})
                OPTIONAL MATCH ()-[r:REL {bucket_id: $bucket_id}]->()
                RETURN count(DISTINCT e) AS nodes, count(DISTINCT r) AS edges
                """,
                bucket_id=bucket_id,
            ).single()
            return {"nodes": rec["nodes"], "edges": rec["edges"]}

    def run_read_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a *read-only* Cypher query (used by the Graph-QA agent)."""
        lowered = cypher.lower()
        forbidden = ("create", "merge", "delete", "set ", "remove", "drop", "detach")
        if any(tok in lowered for tok in forbidden):
            raise ValueError("Only read-only Cypher queries are allowed.")
        with self.session() as s:
            return [dict(r) for r in s.run(cypher, **(params or {}))]

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _node_dict(node) -> Dict[str, Any]:
        return {
            "id": node.get("id"),
            "bucket_id": node.get("bucket_id"),
            "type": node.get("type"),
            "name": node.get("name"),
            "description": node.get("description", ""),
            "properties": node.get("properties", {}),
        }

    @staticmethod
    def _edge_dict(record) -> Dict[str, Any]:
        rel = record["r"]
        return {
            "id": rel.get("id"),
            "bucket_id": rel.get("bucket_id"),
            "source_id": record["source_id"],
            "target_id": record["target_id"],
            "type": rel.get("type"),
            "confidence": rel.get("confidence", 1.0),
            "properties": rel.get("properties", {}),
        }


neo4j_client = Neo4jClient()
