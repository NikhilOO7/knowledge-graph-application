# Knowledge Graph — Context Bucket System

A full-stack system that turns **any uploaded document** into a queryable knowledge graph using a multi-agent AI pipeline. It reads documents, infers a domain ontology, extracts entities and relationships, and stores them in a graph database.

The graph is organised into **context buckets**. When you upload a document, the system detects whether its context already exists in memory: if so it **appends** the new knowledge into that bucket's graph; if not it **creates a new bucket**. From the UI you choose which context bucket's knowledge graph to view, explore, and query.

---

## Core idea: context buckets

A **context bucket** is a named container for one knowledge graph built around a subject/corpus. Each bucket has its own entities, relationships, inferred ontology, and a *context signature* (an embedding + summary) used to decide where new uploads belong.

```
Upload document
      │
      ▼
 Summarise + embed  ──►  context signature
      │
      ▼
 Context-Router agent: compare signature to existing buckets
      │
   ┌──┴───────────────┐
match ≥ threshold     no match
   │                   │
   ▼                   ▼
 Append graph to     Create new bucket
 existing bucket     and seed graph
   └──────┬────────────┘
          ▼
  User picks a bucket in the UI to explore its graph
```

Uploading several documents on the same subject keeps enriching **one coherent graph** (entities dedup/merge) instead of producing fragmented, disconnected graphs.

---

## Architecture

```
 React (web, TypeScript)
        │  REST
        ▼
 FastAPI backend (Python)
        ├── LangGraph    orchestrates the ingestion pipeline (state machine)
        ├── CrewAI       multi-agent extraction crew (extractor→resolver→validator)
        ├── PostgreSQL   buckets, documents, jobs, provenance
        └── Neo4j        the knowledge graph itself (entities + relationships, per bucket)
```

### Ingestion pipeline (LangGraph)

```
prepare ─► route ─► ontology ─► extract ─► finalize
```

| Step       | What happens | Agent / component |
|------------|--------------|-------------------|
| `prepare`  | Extract text, summarise, embed → context signature | Summariser/Embedding tool |
| `route`    | Append to an existing bucket or create a new one | **Context-Router agent** |
| `ontology` | Infer/extend the bucket's entity & relationship types | **Ontology agent** |
| `extract`  | Per chunk: extract → resolve → validate, then persist to Neo4j | **CrewAI extraction crew** |
| `finalize` | Roll signature into the bucket, refresh ontology + counts | persistence |

CrewAI runs *inside* the `extract` step; LangGraph owns the overall, observable, retryable state machine.

### Agents

- **Extractor / Resolver / Validator** (CrewAI crew) — high-recall extraction, canonicalisation + dedup against the bucket, then type/logic validation.
- **Context-Router** — decides append-vs-create using embedding cosine similarity (+ an LLM tie-breaker for borderline cases).
- **Ontology / Schema** — infers domain-appropriate entity & relationship types per bucket (no hardcoded domain).
- **Graph-QA** — GraphRAG-style: answers natural-language questions grounded in a bucket's relationships.

---

## Tech stack

**Backend (Python)** — FastAPI, LangGraph, CrewAI, SQLAlchemy (PostgreSQL), Neo4j Python driver, OpenAI-compatible LLM client (OpenAI or local Ollama), pypdf.

**Frontend (TypeScript)** — React 18, Vite, TailwindCSS, React Router, React Query, React Flow.

**Infrastructure** — Docker Compose (PostgreSQL + Neo4j), pnpm for the web app, pip for the server.

### Why two databases?
- **PostgreSQL** holds operational/relational data: buckets, documents, job status, and edge → source provenance.
- **Neo4j** holds the graph itself — native traversal and Cypher make multi-hop graph queries natural, and buckets are isolated via a `bucket_id` property on every node and relationship.

---

## Prerequisites

- Python >= 3.10
- Node.js >= 18 and pnpm >= 8
- Docker + Docker Compose
- An LLM provider: an OpenAI API key **or** a local [Ollama](https://ollama.com) install

> The system degrades gracefully without an LLM key (deterministic hashing-based context routing still works), but extraction quality requires a configured provider.

---

## Setup

### 1. Start the databases
```bash
docker-compose up -d        # PostgreSQL on :5433, Neo4j on :7687 (browser :7474)
```

### 2. Backend (FastAPI)
```bash
cd apps/server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # then edit OPENAI_API_KEY (or set LLM_PROVIDER=ollama)
uvicorn app.main:app --reload --port 3000
```
Tables and Neo4j constraints are created automatically on startup.

### 3. Frontend (React)
```bash
pnpm install
cp apps/web/.env.example apps/web/.env   # VITE_API_URL=http://localhost:3000
pnpm --filter web dev
```

App: http://localhost:5173 · API: http://localhost:3000 · Neo4j browser: http://localhost:7474

---

## Quick start

1. Open **Upload**, drop a PDF or paste text, leave the target on **Auto-route**.
2. Watch the job status — it reports whether the document **created** a new bucket or was **appended** to an existing one, plus how many nodes/edges were extracted.
3. Use the **bucket selector** (top bar) to choose a bucket.
4. Open **Explorer** to see that bucket's graph, or **Ask** to query it in natural language.
5. Upload another document on the same subject — it merges into the same bucket and enriches the graph.

---

## API reference

### Buckets
- `GET /api/buckets` — list buckets with counts and inferred ontology
- `POST /api/buckets` — create a bucket
- `GET /api/buckets/{id}` — bucket detail
- `DELETE /api/buckets/{id}` — delete a bucket and its graph

### Documents
- `GET /api/documents?bucket_id=…` — list documents
- `GET /api/documents/processing` — documents currently processing
- `POST /api/documents/{id}/process` — (re)run the pipeline

### Ingestion
- `POST /api/ingest/upload` — upload a file (PDF/text), auto-routed or forced to a bucket
- `POST /api/ingest/text` — ingest raw text
- `POST /api/ingest/bulk` — upload multiple files
- `GET /api/ingest/status/{job_id}` — job status (stage, progress, bucket decision, stats)

### Graph (all scoped by `bucket_id`)
- `GET /api/graph/nodes` · `GET /api/graph/nodes/{id}` · `GET /api/graph/edges`
- `GET /api/graph/subgraph?node_id=…&depth=N`
- `GET /api/graph/stats?bucket_id=…`

### Graph-QA
- `POST /api/qa` — `{ bucket_id, question }` → grounded answer + evidence triples

---

## Project structure

```
knowledge-graph-application/
├── apps/
│   ├── server/                  # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py          # FastAPI app + lifespan (DB init)
│   │   │   ├── config.py        # settings (.env)
│   │   │   ├── schemas.py       # Pydantic models
│   │   │   ├── db/              # postgres.py (SQLAlchemy) + neo4j_client.py
│   │   │   ├── services/        # llm, embeddings, documents (pdf/chunking)
│   │   │   ├── agents/          # crew (CrewAI), ontology, context_router, graph_qa, tools
│   │   │   ├── pipeline/        # LangGraph graph.py, state.py, persist.py
│   │   │   ├── routers/         # buckets, documents, graph, ingest, qa
│   │   │   └── jobs.py          # background processing queue
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── web/                      # React frontend
│       └── src/
│           ├── lib/             # api client, types, BucketContext
│           ├── components/      # BucketSelector
│           └── pages/           # Dashboard, Explorer, Ask, Upload
└── docker-compose.yml           # PostgreSQL + Neo4j
```

---

## Key environment variables (`apps/server/.env`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg2://postgres:postgres@localhost:5433/knowledge_graph` |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j connection | `bolt://localhost:7687` / `neo4j` / `password` |
| `LLM_PROVIDER` | `openai` or `ollama` | `openai` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI access | — / `gpt-4o-mini` |
| `BUCKET_MATCH_THRESHOLD` | Cosine similarity to append vs. create | `0.78` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Extraction chunking | `2000` / `200` |

---

## Limitations & future work

- In-process job queue (single instance) — swap for Redis/BullMQ-style workers for scale.
- No authentication yet; add JWT + rate limiting for production.
- Bucket routing relies on a similarity threshold that may need per-domain tuning.
- No UI yet for merging/splitting buckets or re-routing a document between buckets.
- Graph-QA is retrieval-grounded; a Cypher-generation path could broaden answerable questions.

## License

MIT
