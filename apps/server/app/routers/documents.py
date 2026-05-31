"""Document endpoints — list/inspect documents and (re)trigger processing."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from ..db.postgres import DocumentRow, get_session
from .. import jobs

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_dict(row: DocumentRow) -> dict:
    return {
        "id": row.id,
        "bucket_id": row.bucket_id,
        "title": row.title,
        "source_type": row.source_type,
        "filename": row.filename,
        "char_count": row.char_count or 0,
        "processing_status": row.processing_status,
        "processing_progress": row.processing_progress or 0,
        "processing_error": row.processing_error,
        "created_at": row.created_at,
    }


@router.get("")
def list_documents(
    bucket_id: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = 0,
):
    session = get_session()
    try:
        q = session.query(DocumentRow)
        if bucket_id:
            q = q.filter(DocumentRow.bucket_id == bucket_id)
        rows = (
            q.order_by(DocumentRow.created_at.desc()).limit(limit).offset(offset).all()
        )
        return {"documents": [_to_dict(r) for r in rows]}
    finally:
        session.close()


@router.get("/processing")
def processing_documents():
    """Documents not yet completed — used by the dashboard live view."""
    session = get_session()
    try:
        rows = (
            session.query(DocumentRow)
            .filter(DocumentRow.processing_status.notin_(["completed", "failed"]))
            .order_by(DocumentRow.created_at.desc())
            .all()
        )
        return {"documents": [_to_dict(r) for r in rows]}
    finally:
        session.close()


@router.get("/{document_id}")
def get_document(document_id: str):
    session = get_session()
    try:
        row = session.get(DocumentRow, document_id)
        if not row:
            raise HTTPException(404, "Document not found")
        return _to_dict(row)
    finally:
        session.close()


@router.post("/{document_id}/process")
def process_document(document_id: str):
    session = get_session()
    try:
        row = session.get(DocumentRow, document_id)
        if not row:
            raise HTTPException(404, "Document not found")
        forced_bucket = row.bucket_id
    finally:
        session.close()

    job_id = f"job-{uuid.uuid4().hex[:12]}"
    jobs.enqueue(job_id, document_id, forced_bucket)
    return {"job_id": job_id, "document_id": document_id, "status": "queued"}
