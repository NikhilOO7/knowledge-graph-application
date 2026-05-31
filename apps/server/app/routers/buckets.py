"""Context bucket endpoints — list/create/inspect/delete buckets."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db.neo4j_client import neo4j_client
from ..db.postgres import BucketRow, DocumentRow, get_session
from ..schemas import Bucket, BucketCreate

router = APIRouter(prefix="/api/buckets", tags=["buckets"])


def _to_schema(row: BucketRow, doc_count: int) -> Bucket:
    return Bucket(
        id=row.id,
        name=row.name,
        description=row.description,
        entity_types=row.entity_types or [],
        relationship_types=row.relationship_types or [],
        document_count=doc_count,
        node_count=row.node_count or 0,
        edge_count=row.edge_count or 0,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("")
def list_buckets():
    session = get_session()
    try:
        rows = session.query(BucketRow).order_by(BucketRow.created_at.desc()).all()
        out = []
        for row in rows:
            doc_count = (
                session.query(DocumentRow).filter(DocumentRow.bucket_id == row.id).count()
            )
            out.append(_to_schema(row, doc_count).model_dump())
        return {"buckets": out}
    finally:
        session.close()


@router.post("")
def create_bucket(body: BucketCreate):
    session = get_session()
    try:
        row = BucketRow(name=body.name, description=body.description)
        session.add(row)
        session.commit()
        return _to_schema(row, 0).model_dump()
    finally:
        session.close()


@router.get("/{bucket_id}")
def get_bucket(bucket_id: str):
    session = get_session()
    try:
        row = session.get(BucketRow, bucket_id)
        if not row:
            raise HTTPException(404, "Bucket not found")
        doc_count = (
            session.query(DocumentRow).filter(DocumentRow.bucket_id == bucket_id).count()
        )
        return _to_schema(row, doc_count).model_dump()
    finally:
        session.close()


@router.delete("/{bucket_id}")
def delete_bucket(bucket_id: str):
    session = get_session()
    try:
        row = session.get(BucketRow, bucket_id)
        if not row:
            raise HTTPException(404, "Bucket not found")
        neo4j_client.delete_bucket_graph(bucket_id)
        session.delete(row)
        session.commit()
        return {"deleted": bucket_id}
    finally:
        session.close()
