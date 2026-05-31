# Implementation Plan — Context-Bucket Knowledge Graph System

This document describes how the system is built and how to extend it. The goal: turn **any uploaded document** into a knowledge graph, automatically grouped into **context buckets** so related documents enrich one graph and unrelated ones stay separate.

---

## 1. Goals & non-goals

**Goals**
- Ingest arbitrary documents (PDF / text), not a fixed domain.
- Infer a per-bucket ontology instead of hardcoding entity/relationship types.
- Detect whether an upload's context already exists in memory; append to that bucket or create a new one.
- Let users pick which bucket's graph to view, explore, and query.
- Use a multi-agent pipeline (CrewAI) orchestrated by an explicit state machine (LangGraph).
- Store the graph in a real graph database (Neo4j) and operational data in PostgreSQL.

**Non-goals (for now)**
- Auth/multi-tenant access control.
- Distributed worker fleet (single-instance in-process queue is enough to start).
- Manual graph editing UI.

---

## 2. High-level architecture

```
React (web)  ──REST──►  FastAPI (server)
                          ├── LangGraph   pipeline state machine
                          ├── CrewAI      extraction crew
                          ├── PostgreSQL  buckets, documents, jobs, provenance
                          └── Neo4j       entities + relationships (per bucket)
```

Pipeline (LangGraph): `prepare → route → ontology → extract → finalize`.

---

## 3. Data model

### PostgreSQL (operational)
- `buckets` — `id, name, description, entity_types[], relationship_types[], signature_vector, signature_summary, signature_doc_count, node_count, edge_count, timestamps`
- `documents` — `id, bucket_id, title, source_type, filename, raw_text, char_count, processing_status, processing_progress, processing_error, timestamps`
- `sources` — provenance: `id, edge_id (Neo4j rel id), bucket_id, document_id, section, extracted_text`

### Neo4j (graph)
- `(:Entity {id, bucket_id, type, name, normalized_name, description, properties})`
- `(:Entity)-[:REL {id, bucket_id, type, confidence, properties}]->(:Entity)`
- Dedup key: `(bucket_id, normalized_name)` — same concept across documents merges into one node.
- Single `:REL` type with a `type` property so arbitrary inferred relationship names are safe.
- Constraints/indexes: unique `Entity.id`; indexes on `bucket_id` and `(bucket_id, normalized_name)`.

---

## 4. Build phases (status)

### Phase 0 — Infrastructure ✅
- `docker-compose.yml` with PostgreSQL (`:5433`) and Neo4j (`:7687` / browser `:7474`).
- `apps/server` Python package; `apps/web` React app; `.env.example` templates.

### Phase 1 — Data layer ✅
- `db/postgres.py`: SQLAlchemy models + session; `init_db()` auto-creates tables.
- `db/neo4j_client.py`: driver wrapper with upsert/query/stats/subgraph/read-only-cypher; `ensure_constraints()`.

### Phase 2 — Services ✅
- `services/llm.py`: OpenAI-compatible client (OpenAI **or** Ollama), `chat`, `chat_json`, `get_crew_llm`.
- `services/embeddings.py`: embed + summarise + cosine similarity; deterministic hashing fallback offline.
- `services/documents.py`: PDF/text extraction, cleaning, chunking, section detection.

### Phase 3 — Agents ✅
- `agents/crew.py`: CrewAI crew (Extractor → Resolver → Validator) with a direct-LLM fallback.
- `agents/ontology.py`: infer/extend per-bucket entity & relationship types.
- `agents/context_router.py`: append-vs-create decision (cosine + LLM tie-breaker + bucket naming).
- `agents/graph_qa.py`: GraphRAG retrieval + grounded answer.
- `agents/tools.py`: CrewAI tool exposing existing bucket entities to the resolver.

### Phase 4 — Pipeline ✅
- `pipeline/state.py`: `PipelineState` TypedDict.
- `pipeline/graph.py`: LangGraph `StateGraph` wiring the five nodes.
- `pipeline/persist.py`: write entities/edges to Neo4j, record provenance, roll up bucket signature/counts.

### Phase 5 — API ✅
- `routers/buckets.py`, `documents.py`, `graph.py`, `ingest.py`, `qa.py`.
- `jobs.py`: in-process thread-pool queue mirroring status onto the document row.
- `main.py`: FastAPI app, CORS, lifespan DB init.

### Phase 6 — Frontend ✅
- `lib/BucketContext.tsx` + `components/BucketSelector.tsx`: choose which bucket to view.
- Pages: `Dashboard` (per-bucket stats + ontology + live processing), `Explorer` (React Flow graph), `Ask` (Graph-QA), `Upload` (file/text ingest with bucket decision feedback).

---

## 5. Request flows

**Upload → graph**
1. `POST /api/ingest/upload` stores the document (Postgres) and enqueues a job.
2. LangGraph runs: summarise+embed → Context-Router picks/creates a bucket → Ontology agent → CrewAI crew per chunk → persist to Neo4j → finalize bucket signature/counts.
3. Job status (stage, progress, `bucket_action`, stats) is polled by the UI.

**View / query**
- `GET /api/graph/* ?bucket_id=…` returns nodes/edges/stats for the selected bucket.
- `POST /api/qa` answers a question grounded in that bucket's relationships.

---

## 6. Testing strategy

- **Unit**: chunking/section detection; cosine similarity & routing thresholds; ontology merge/dedup; crew output coercion.
- **Integration**: ingest a small text doc end-to-end against ephemeral PG + Neo4j; assert nodes/edges created and bucket counts updated.
- **Routing**: upload two same-topic docs → second appends (asserts `bucket_action == "appended"`); upload an unrelated doc → new bucket.
- **API**: FastAPI `TestClient` for each router.

---

## 7. Future work / extension points

- Replace the in-process queue with Redis + workers (BullMQ/Celery/RQ).
- Add auth (JWT) + rate limiting.
- Bucket management UI: merge/split/rename, re-route a document.
- Cypher-generation path in Graph-QA for broader questions.
- Vector index in Neo4j (or pgvector) for semantic entity search.
- Per-domain tuning of `BUCKET_MATCH_THRESHOLD`, optionally learned.
