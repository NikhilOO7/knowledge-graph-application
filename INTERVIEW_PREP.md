# Interview Preparation — Context-Bucket Knowledge Graph System

A talking-points guide for explaining the project: what it does, why each piece is there, and the trade-offs.

---

## 1. One-paragraph pitch

A full-stack system that converts **any uploaded document** into a queryable knowledge graph using a multi-agent AI pipeline. Documents are grouped into **context buckets**: on upload, a Context-Router agent decides whether the document's context already exists in memory (append to that bucket's graph) or is new (create a bucket). The pipeline is orchestrated by **LangGraph** as an explicit state machine, with **CrewAI** running the extraction crew. The graph lives in **Neo4j**, operational data in **PostgreSQL**, and a **React** frontend lets users pick which bucket to explore and ask natural-language questions.

---

## 2. The core concept: context buckets

**Q: What is a context bucket and why does it exist?**
A named container for one knowledge graph. It exists so that uploading several documents on the same subject **enriches one coherent graph** (entities dedup/merge), while unrelated subjects stay in separate, navigable graphs. It gives users a simple mental model: pick a bucket, explore its graph.

**Q: How does the system decide append-vs-create?**
Each document gets a *context signature* = embedding of its summary + the summary text. The Context-Router compares it (cosine similarity) against every existing bucket's rolling signature. Above the threshold → append; in a borderline band → an LLM tie-breaker confirms topical overlap from the summaries; otherwise → create a new bucket (named by the LLM). Threshold is `BUCKET_MATCH_THRESHOLD` (default 0.78).

**Q: How does appending avoid duplicates?**
Entities dedup on `(bucket_id, normalized_name)` in Neo4j via `MERGE`. The resolver agent also canonicalises mentions against existing bucket entities (via a CrewAI tool), so an acronym maps onto the already-present full name instead of creating a second node.

---

## 3. Architecture decisions

**Q: Why LangGraph *and* CrewAI — isn't that redundant?**
They operate at different levels. **LangGraph** owns the overall pipeline as an explicit, observable, retryable state machine (`prepare → route → ontology → extract → finalize`) — good for branching and per-step control. **CrewAI** is the multi-agent *unit* inside the `extract` step: a crew of Extractor → Resolver → Validator agents that cooperate per chunk. LangGraph = orchestration; CrewAI = the agent team doing extraction.

**Q: Why two databases (PostgreSQL + Neo4j)?**
- **Neo4j** stores the graph itself — native traversal and Cypher make multi-hop queries (`subgraph`, neighbourhoods) natural and fast; buckets are isolated by a `bucket_id` property.
- **PostgreSQL** stores relational/operational data: buckets, documents, job status, and edge→source provenance. ACID and mature tooling fit that well.
Splitting concerns keeps each store doing what it's best at.

**Q: Why infer the ontology instead of hardcoding entity/relationship types?**
To make the system **domain-generic**. A research-papers bucket needs {method, dataset, metric, …}; a legal bucket needs {party, clause, obligation, …}. The Ontology agent infers types per bucket from the document and *extends* (never discards) the bucket's existing ontology, always keeping generic fallbacks (`concept`, `relates_to`).

**Q: Why a single `:REL` relationship type in Neo4j?**
Relationship type names are inferred at runtime and can contain spaces/arbitrary text. Encoding them as dynamic Cypher relationship types would be unsafe/injection-prone, so we use one `:REL` type with a `type` *property*. Queries filter on `r.type`.

---

## 4. The pipeline (step by step)

1. **prepare** — extract text (pypdf / plain), summarise, embed → context signature; chunk the text.
2. **route** — Context-Router picks an existing bucket or creates one (unless the caller forced a bucket).
3. **ontology** — infer/extend the bucket's entity & relationship types.
4. **extract** — for each chunk: run the CrewAI crew (extract → resolve/dedup → validate), then persist entities + relationships to Neo4j and provenance to Postgres.
5. **finalize** — roll the document signature into the bucket (weighted mean), refresh ontology + cached counts, mark the document complete.

---

## 5. The agents

| Agent | Job | Key technique |
|-------|-----|---------------|
| Context-Router | append vs. create bucket | cosine similarity + LLM tie-breaker |
| Ontology/Schema | infer entity & relationship types | LLM, merge with existing, generic fallbacks |
| Extractor | high-recall entity/relationship extraction | CrewAI agent |
| Resolver | canonicalise + dedup against the bucket | CrewAI agent + `existing_bucket_entities` tool |
| Validator | drop ill-typed/weak relationships | CrewAI agent, confidence floor 0.4 |
| Graph-QA | answer questions from the graph | GraphRAG retrieval + grounded LLM answer |

---

## 6. Robustness & graceful degradation

- **No LLM key?** Embeddings fall back to a deterministic hashing bag-of-words vector, so context routing still works; extraction degrades but the pipeline doesn't crash.
- **CrewAI unavailable / fails?** `crew.py` falls back to a direct-LLM call implementing the same extract→resolve→validate logic.
- **LLM JSON drift?** `chat_json` uses native JSON mode where available, with tolerant parsing and retries; crew output is coerced against the allowed ontology types.
- **Read-only QA Cypher** is guarded against write keywords.

---

## 7. Scaling & production talking points

- **Job queue**: today an in-process thread pool mirrors status onto the document row; swap for Redis + workers (Celery/RQ/BullMQ) to scale and isolate failures.
- **Status updates**: polling every ~1.5–2s today; SSE/WebSockets would cut load at higher concurrency.
- **Auth**: add JWT + rate limiting before exposing publicly.
- **Search**: add a vector index (Neo4j vector / pgvector) for semantic entity lookup.
- **Bucket ops**: UI for merge/split/rename and re-routing a misfiled document.

---

## 8. Likely follow-up questions

- *What happens if a document spans two subjects?* It routes to the single best-matching bucket; cross-bucket linking is future work. Could split by section and route each.
- *How is provenance tracked?* Every persisted edge writes a `sources` row (document, section, extracted text) keyed by the Neo4j relationship id.
- *How do you prevent the graph from degenerating into one giant bucket?* The threshold + LLM tie-breaker; tunable per domain; borderline matches require summary-level agreement.
- *Why FastAPI?* Async-friendly, Pydantic validation, minimal boilerplate, plays well with the Python agent ecosystem (CrewAI/LangGraph are Python).
