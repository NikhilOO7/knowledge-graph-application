"""PostgreSQL layer (SQLAlchemy).

Postgres stores the *operational* data:
  - buckets            : context buckets + their inferred ontology + signature
  - documents          : uploaded documents and processing status
  - sources            : provenance linking graph edges back to document text

The knowledge graph itself (nodes + relationships) lives in Neo4j; see
``neo4j_client.py``. Postgres keeps a lightweight count cache on the bucket so
the UI can list buckets without touching Neo4j.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from ..config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _uuid() -> str:
    return str(uuid.uuid4())


# JSONB on Postgres, plain JSON elsewhere (keeps SQLite/tests working).
JsonType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class BucketRow(Base):
    __tablename__ = "buckets"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    description = Column(Text)

    # Inferred ontology for this bucket (lists of strings, JSON-encoded)
    entity_types = Column(JsonType, default=list)
    relationship_types = Column(JsonType, default=list)

    # Context signature: mean embedding vector + rolling summary, used by the
    # Context-Router agent to decide append-vs-create.
    signature_vector = Column(JsonType)  # List[float] | None
    signature_summary = Column(Text)
    signature_doc_count = Column(Integer, default=0)

    # Cached counts (authoritative graph is in Neo4j)
    node_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("DocumentRow", back_populates="bucket", cascade="all, delete-orphan")


class DocumentRow(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    bucket_id = Column(String, ForeignKey("buckets.id", ondelete="SET NULL"))
    title = Column(String, nullable=False)
    source_type = Column(String, default="upload")
    filename = Column(String)
    raw_text = Column(Text)
    char_count = Column(Integer, default=0)

    processing_status = Column(String, default="pending")
    processing_progress = Column(Integer, default=0)
    processing_error = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bucket = relationship("BucketRow", back_populates="documents")


class SourceRow(Base):
    """Provenance: which document/text span produced a given graph edge."""

    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=_uuid)
    edge_id = Column(String, nullable=False)  # Neo4j relationship id
    bucket_id = Column(String, ForeignKey("buckets.id", ondelete="CASCADE"))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    section = Column(String)
    extracted_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
