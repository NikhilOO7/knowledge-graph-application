# Submission Summary

## What this is

A generic, full-stack **context-bucket knowledge graph system**. It ingests arbitrary documents (PDF or text), uses a multi-agent AI pipeline to extract entities and relationships, and stores them as a graph. Documents are automatically routed into **context buckets**: if a document's context already exists in memory it is appended to that bucket's graph; otherwise a new bucket is created. Users pick which bucket's graph to explore and query from the UI.

## Architecture

- **Frontend** — React + Vite + TailwindCSS + React Flow. Pages: Dashboard, Explorer, Ask (Graph-QA), Upload, plus a global context-bucket selector.
- **Backend** — Python FastAPI.
  - **LangGraph** orchestrates the ingestion pipeline as a state machine: `prepare → route → ontology → extract → finalize`.
  - **CrewAI** runs the extraction crew (Extractor → Resolver → Validator) inside the `extract` step.
- **Storage**
  - **PostgreSQL** — buckets, documents, processing jobs, and edge provenance.
  - **Neo4j** — the knowledge graph itself (entities + relationships), isolated per bucket via a `bucket_id` property.

## Agents

| Agent | Role |
|-------|------|
| Context-Router | Decides append-to-existing vs. create-new bucket via embedding similarity (+ LLM tie-breaker) |
| Ontology / Schema | Infers per-bucket entity & relationship types — no hardcoded domain |
| Extractor / Resolver / Validator | CrewAI crew: extract, canonicalise/dedup, validate |
| Graph-QA | Answers natural-language questions grounded in the bucket's graph |

## Key design decisions

- **Context buckets** keep unrelated subjects in separate graphs while letting related documents enrich a shared one (entities dedup/merge within a bucket).
- **Two databases**: Postgres for relational/operational data, Neo4j for native graph traversal.
- **Generic ontology**: entity/relationship types are inferred per bucket, so the same system works for research papers, legal contracts, biology, business docs, etc.
- **Provider-agnostic LLM**: OpenAI or local Ollama via an OpenAI-compatible client; degrades gracefully (deterministic context routing) when no key is set.

## How to run

```bash
docker-compose up -d                     # PostgreSQL + Neo4j
cd apps/server && pip install -r requirements.txt && uvicorn app.main:app --reload --port 3000
pnpm install && pnpm --filter web dev    # http://localhost:5173
```

See [README.md](README.md) for full setup, the API reference, and the project structure.
