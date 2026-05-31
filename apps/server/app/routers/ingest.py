"""Ingestion endpoints — upload documents (file or raw text) into the system.

The uploaded document is stored, then (optionally) handed to the LangGraph
pipeline, which routes it to a new or existing context bucket and builds the
graph. The bucket decision is made *inside* the pipeline (Context-Router), so
the immediate response reports ``bucket_action: "pending"`` unless a bucket was
explicitly forced by the caller.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import jobs
from ..db.postgres import DocumentRow, get_session
from ..schemas import IngestResponse, TextIngestRequest
from ..services import documents as doc_svc

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _store_document(title: str, text: str, source_type: str, filename: Optional[str],
                    bucket_id: Optional[str]) -> str:
    session = get_session()
    try:
        row = DocumentRow(
            title=title,
            raw_text=text,
            char_count=len(text),
            source_type=source_type,
            filename=filename,
            bucket_id=bucket_id,
            processing_status="pending",
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _start(document_id: str, bucket_id: Optional[str], auto_process: bool) -> IngestResponse:
    if not auto_process:
        return IngestResponse(
            job_id="", document_id=document_id, bucket_id=bucket_id,
            bucket_action="pending", status="stored",
        )
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    jobs.enqueue(job_id, document_id, bucket_id)
    return IngestResponse(
        job_id=job_id,
        document_id=document_id,
        bucket_id=bucket_id,
        bucket_action="appended" if bucket_id else "pending",
        status="queued",
    )


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    bucket_id: Optional[str] = Form(default=None),
    auto_process: bool = Form(default=True),
):
    data = await file.read()
    filename = file.filename or "document"
    if filename.lower().endswith(".pdf") or (file.content_type or "").endswith("pdf"):
        try:
            text = doc_svc.extract_text_from_pdf(data)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Failed to parse PDF: {exc}")
    else:
        text = doc_svc.clean_text(data.decode("utf-8", errors="ignore"))

    if len(text.strip()) < 30:
        raise HTTPException(400, "Document has too little extractable text.")

    title = filename.rsplit(".", 1)[0]
    doc_id = _store_document(title, text, "upload", filename, bucket_id or None)
    return _start(doc_id, bucket_id or None, auto_process)


@router.post("/text", response_model=IngestResponse)
def ingest_text(body: TextIngestRequest):
    text = doc_svc.clean_text(body.text)
    if len(text.strip()) < 30:
        raise HTTPException(400, "Text is too short to build a graph from.")
    doc_id = _store_document(body.title, text, "text", None, body.bucket_id)
    return _start(doc_id, body.bucket_id, body.auto_process)


@router.post("/bulk")
async def bulk_upload(
    files: List[UploadFile] = File(...),
    bucket_id: Optional[str] = Form(default=None),
    auto_process: bool = Form(default=True),
):
    responses = []
    for f in files:
        data = await f.read()
        name = f.filename or "document"
        try:
            if name.lower().endswith(".pdf"):
                text = doc_svc.extract_text_from_pdf(data)
            else:
                text = doc_svc.clean_text(data.decode("utf-8", errors="ignore"))
            if len(text.strip()) < 30:
                continue
            doc_id = _store_document(name.rsplit(".", 1)[0], text, "upload", name, bucket_id or None)
            responses.append(_start(doc_id, bucket_id or None, auto_process).model_dump())
        except Exception as exc:  # noqa: BLE001
            responses.append({"filename": name, "error": str(exc)})
    return {"results": responses}


@router.get("/status/{job_id}")
def job_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
