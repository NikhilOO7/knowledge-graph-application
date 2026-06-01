# Knowledge Graph — Context Bucket System

A full-stack system that turns **any uploaded document** into a queryable **knowledge graph** using a multi-agent AI pipeline. It reads a document, infers a domain ontology, extracts entities and the relationships between them, and stores the result in a graph database.

The graph is organised into **context buckets**. When you upload a document, the system detects whether its subject already exists in memory: if so it **appends** the newly-extracted knowledge into that bucket's graph (merging/deduping entities); if not, it **creates a new bucket**. From the UI you pick which bucket's graph to explore, visualise, and ask questions about.

> One coherent graph per subject — uploading several documents about the same topic keeps enriching the same graph instead of producing fragmented, disconnected ones.

---

## High-level design

![High-level architecture](docs/architecture.svg)

The system is split into four cooperating layers:

| Layer | Tech | Responsibility |
|-------|------|----------------|
| **Frontend** | React, Vite, TailwindCSS, React Flow | Bucket selector, graph explorer, upload, natural-language Q&A |
| **Backend** | FastAPI (Python) | REST API + orchestration |
| **Orchestration** | **LangGraph** + **CrewAI** | LangGraph runs the ingestion state machine; CrewAI runs the extraction crew |
| **Storage** | **PostgreSQL** + **Neo4j** | Postgres for operational data; Neo4j for the graph itself |

### Why two databases?
- **Neo4j** stores the knowledge graph — native traversal and Cypher make multi-hop queries (neighbourhoods, sub-graphs) natural and fast. Every node and relationship carries a `bucket_id`, so buckets are cleanly isolated.
- **PostgreSQL** stores relational/operational data: buckets, documents, job status, and edge → source-text provenance.

### Why LangGraph *and* CrewAI?
They work at different levels. **LangGraph** owns the overall pipeline as an explicit, observable, retryable state machine. **CrewAI** is the multi-agent *unit* that does the actual extraction inside one step of that machine. Orchestration vs. the agent team.

---

## How a document becomes a graph

![Context-bucket routing](docs/bucket-routing.svg)

The ingestion pipeline is a **LangGraph `StateGraph`**:

```
prepare ─► route ─► ontology ─► extract ─► finalize
```

| Step | What happens | Agent / component |
|------|--------------|-------------------|
| `prepare`  | Extract text (PDF/text), summarise, embed → a *context signature*; chunk the text | Summarizer / Embedding tool |
| `route`    | Compare the signature to existing buckets; append to the best match or create a new bucket | **Context-Router agent** |
| `ontology` | Infer / extend the bucket's entity & relationship **types** from the document | **Ontology agent** |
| `extract`  | Per chunk: extract → resolve/dedup → validate, then persist to Neo4j + provenance to Postgres | **CrewAI crew** |
| `finalize` | Roll the document's signature into the bucket, refresh ontology + cached counts | persistence |

### The agents

- **Context-Router** — decides *append vs. create* using embedding cosine similarity against each bucket's signature, with an LLM tie-breaker for borderline cases and LLM naming for new buckets.
- **Ontology / Schema** — infers domain-appropriate entity and relationship types per bucket (no hardcoded domain), always extending, never discarding, the bucket's existing ontology.
- **CrewAI Extraction Crew** — three cooperating agents:
  - *Extractor* — high-recall entity & candidate-relationship extraction.
  - *Resolver* — canonicalises mentions and dedups against entities already in the bucket (via a tool that queries the live graph).
  - *Validator* — drops ill-typed or low-confidence relationships.
- **Graph-QA** — GraphRAG-style: retrieves relevant relationships from the selected bucket and answers a natural-language question grounded in them.

> Graceful degradation: with no LLM key, embeddings fall back to a deterministic vector so routing still works; if CrewAI is unavailable, a direct-LLM path implements the same extract → resolve → validate logic.

---

## Data model

### PostgreSQL (operational)
- **`buckets`** — `name, description, entity_types[], relationship_types[], signature_vector, signature_summary, node_count, edge_count`
- **`documents`** — `bucket_id, title, source_type, raw_text, processing_status, processing_progress`
- **`sources`** — provenance: `edge_id` (Neo4j relationship), `document_id, section, extracted_text`

### Neo4j (the graph)
```cypher
(:Entity {id, bucket_id, type, name, normalized_name, description})
(:Entity)-[:REL {id, bucket_id, type, confidence}]->(:Entity)
```
- Entities dedup on `(bucket_id, normalized_name)` via `MERGE` — same concept across documents merges into one node.
- A single `:REL` type carries a `type` **property**, so arbitrary, ontology-inferred relationship names are stored safely.

---

## Tech stack

**Backend** — FastAPI, LangGraph, CrewAI, SQLAlchemy (PostgreSQL), Neo4j Python driver, OpenAI-compatible LLM client (OpenAI **or** local Ollama), pypdf.

**Frontend** — React 18, Vite, TailwindCSS, React Router, React Query, React Flow.

**Infrastructure** — Docker Compose (PostgreSQL + Neo4j), pnpm (web), pip (server).

---

## Getting started

### Prerequisites
- Python ≥ 3.10
- Node.js ≥ 18 and pnpm ≥ 8
- Docker + Docker Compose
- An LLM provider: an OpenAI API key **or** a local [Ollama](https://ollama.com)

### 1. Start the databases
```bash
docker-compose up -d        # PostgreSQL :5433 · Neo4j :7687 (browser :7474)
```

### 2. Backend (FastAPI)
```bash
cd apps/server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set OPENAI_API_KEY, or LLM_PROVIDER=ollama
uvicorn app.main:app --reload --port 3000
```
Postgres tables and Neo4j constraints are created automatically on startup.

### 3. Frontend (React)
```bash
pnpm install
cp apps/web/.env.example apps/web/.env    # VITE_API_URL=http://localhost:3000
pnpm --filter web dev
```

App → http://localhost:5173 · API → http://localhost:3000 · Neo4j browser → http://localhost:7474

### First run
1. Open **Upload**, drop a PDF or paste text, leave the target on **Auto-route**.
2. The job status reports whether the document **created** a new bucket or was **appended** to one, plus how many nodes/edges were extracted.
3. Use the **bucket selector** (top bar) to choose a bucket.
4. Open **Explorer** to see the graph, or **Ask** to query it.
5. Upload another document on the same topic — it merges into the same bucket.

---

## API reference

### Buckets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/buckets` | List buckets with counts + inferred ontology |
| POST | `/api/buckets` | Create a bucket |
| GET | `/api/buckets/{id}` | Bucket detail |
| DELETE | `/api/buckets/{id}` | Delete a bucket and its graph |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents?bucket_id=…` | List documents |
| GET | `/api/documents/processing` | Documents currently processing |
| POST | `/api/documents/{id}/process` | (Re)run the pipeline |

### Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/upload` | Upload a file (PDF/text), auto-routed or forced to a bucket |
| POST | `/api/ingest/text` | Ingest raw text |
| POST | `/api/ingest/bulk` | Upload multiple files |
| GET | `/api/ingest/status/{job_id}` | Job status (stage, progress, bucket decision, stats) |

### Graph (scoped by `bucket_id`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/nodes` | List nodes (filter by type/search) |
| GET | `/api/graph/nodes/{id}` | Node + its relationships |
| GET | `/api/graph/edges` | List relationships |
| GET | `/api/graph/subgraph?node_id=…&depth=N` | N-hop neighbourhood |
| GET | `/api/graph/stats?bucket_id=…` | Counts by entity/relationship type |

### Graph-QA
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/qa` | `{ bucket_id, question }` → grounded answer + evidence triples |

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
│   │   │   ├── db/              # postgres.py (SQLAlchemy) · neo4j_client.py
│   │   │   ├── services/        # llm · embeddings · documents (pdf/chunking)
│   │   │   ├── agents/          # crew (CrewAI) · ontology · context_router · graph_qa · tools
│   │   │   ├── pipeline/        # graph.py (LangGraph) · state.py · persist.py
│   │   │   ├── routers/         # buckets · documents · graph · ingest · qa
│   │   │   └── jobs.py          # background processing queue
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── web/                      # React frontend
│       └── src/
│           ├── lib/             # api client · types · BucketContext
│           ├── components/      # BucketSelector
│           └── pages/           # Dashboard · Explorer · Ask · Upload
├── docs/                         # architecture.svg · bucket-routing.svg
└── docker-compose.yml            # PostgreSQL + Neo4j
```

---

## Configuration (`apps/server/.env`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg2://postgres:postgres@localhost:5433/knowledge_graph` |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j connection | `bolt://localhost:7687` / `neo4j` / `password` |
| `LLM_PROVIDER` | `openai` or `ollama` | `openai` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI access | — / `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `BUCKET_MATCH_THRESHOLD` | Cosine similarity to append vs. create | `0.78` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Extraction chunking | `2000` / `200` |

---

## Limitations & future work

- **In-process job queue** (single instance) — swap for Redis + workers (Celery/RQ/BullMQ) to scale.
- **No authentication** yet — add JWT + rate limiting before exposing publicly.
- **Threshold-based routing** — `BUCKET_MATCH_THRESHOLD` may need per-domain tuning; could be learned.
- **No bucket-management UI** — merging/splitting buckets or re-routing a document is future work.
- **Graph-QA is retrieval-grounded** — a Cypher-generation path would broaden answerable questions.
- **Status updates use polling** — Server-Sent Events would cut load at higher concurrency.

## License

MIT
