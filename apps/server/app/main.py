"""FastAPI application entry point.

  React (web)  ──►  FastAPI (this service)
                       ├─ Postgres  : buckets, documents, provenance
                       ├─ Neo4j     : the knowledge graph (per bucket)
                       ├─ LangGraph : pipeline orchestration
                       └─ CrewAI    : extraction crew
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.neo4j_client import neo4j_client
from .db.postgres import init_db
from .routers import buckets, documents, graph, ingest, qa


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Postgres tables
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] Postgres init failed: {exc}")
    # Neo4j constraints/indexes
    try:
        neo4j_client.ensure_constraints()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] Neo4j init failed: {exc}")
    yield
    neo4j_client.close()


app = FastAPI(title="Context Bucket Knowledge Graph API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(buckets.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(ingest.router)
app.include_router(qa.router)


@app.get("/")
def root():
    return {
        "name": "Context Bucket Knowledge Graph API",
        "version": "2.0.0",
        "llm_provider": settings.llm_provider,
        "llm_configured": settings.llm_is_configured,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "neo4j": neo4j_client.check_connection(),
        "llm_configured": settings.llm_is_configured,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
