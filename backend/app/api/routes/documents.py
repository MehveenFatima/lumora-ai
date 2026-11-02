import asyncio
import math
import os
import re
import secrets
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request, status
from pydantic import BaseModel, Field as PydanticField
from backend.app.api.deps import CurrentUser, get_current_user, ensure_document_access, require_workspace
from fastapi.responses import Response
from backend.app.schemas.documents import (
    DocumentResponse,
    DocumentUploadResponse,
    DocumentListResponse,
)
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.secondary import activity_repo
from backend.app.services.document_parser import document_parser
from backend.app.services.chunker import chunker_service
from backend.app.services.embeddings import EmbeddingUnavailableError, embedding_service
from backend.app.services.storage import storage_service
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Documents"])

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}
LEGACY_OFFICE_EXTENSIONS = {".doc": ".docx", ".ppt": ".pptx"}


class DocumentContentError(Exception):
    """The file is valid but contains nothing that can be indexed."""


def _safe_filename(name: str) -> str:
    """Strips characters that could break or inject into the Content-Disposition header."""
    cleaned = "".join(ch for ch in (name or "document") if ch.isprintable() and ch not in '"\\\r\n;')
    return cleaned.strip() or "document"


def _validate_extension(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in LEGACY_OFFICE_EXTENSIONS:
        modern = LEGACY_OFFICE_EXTENSIONS[ext]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{ext}' is an older Office format. Open the file and use Save As to save it as "
            f"{modern}, or export it as PDF, then upload it again.",
        )
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: PDF, DOCX, PPTX, TXT.",
        )
    return ext


def _validate_size(file_size: int) -> None:
    if file_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.max_file_size_bytes / (1024 * 1024):.0f} MB.",
        )


async def _accept_document(
    workspace_id: str,
    response: Response,
    filename: str,
    content_type: str,
    file_bytes: bytes,
    title: str = None,
) -> DocumentResponse:
    """Validates a complete file and indexes it (shared by direct and chunked uploads)."""
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    ext = _validate_extension(filename)
    file_size = len(file_bytes)
    _validate_size(file_size)

    # Validate the file signature so a renamed or corrupt file is rejected as a client error
    if ext == ".pdf" and not file_bytes.lstrip()[:5] == b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid PDF document.",
        )
    if ext in (".docx", ".pptx") and not file_bytes.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file is not a valid {ext.lstrip('.').upper()} document.",
        )

    doc_title = title.strip() if title and title.strip() else os.path.splitext(filename)[0].replace("_", " ")
    file_type = ext.lstrip(".")

    # Create the document record, then process it. Small files finish within the wait window
    # and return 201 with status "ready"; larger ones return 202 and keep processing in the
    # background while the UI polls GET /documents/{id}.
    doc_record = await document_repo.create(
        workspace_id=workspace_id,
        title=doc_title,
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        status="processing",
    )
    doc_id = doc_record["id"]
    mode = {"background": False}
    task = asyncio.create_task(
        _ingest_document(
            mode, workspace_id, doc_id, doc_title, filename, file_type, file_bytes,
            content_type or "application/octet-stream",
        )
    )
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)

    done, _ = await asyncio.wait({task}, timeout=INGEST_WAIT_SECONDS)
    if task not in done:
        mode["background"] = True  # set before the next await, so failures are recorded, not raised
        response.status_code = status.HTTP_202_ACCEPTED
        current = await document_repo.get_by_id(doc_id) or doc_record
        return DocumentResponse(**current)

    exc = task.exception()
    if exc is None:
        return DocumentResponse(**task.result())
    if isinstance(exc, (DocumentContentError, EmbeddingUnavailableError)):
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(exc, EmbeddingUnavailableError)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_GENERIC_INGEST_ERROR)


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: str,
    response: Response,
    file: UploadFile = File(...),
    title: str = Form(None),
    workspace: dict = Depends(require_workspace),
) -> DocumentResponse:
    _validate_extension(file.filename)
    file_bytes = await file.read()
    return await _accept_document(
        workspace_id, response, file.filename, file.content_type or "application/octet-stream", file_bytes, title
    )


# ----------------------------------------------------------------------------------------------
# Chunked uploads
#
# Serverless hosts cap the size of one request body (Vercel: 4.5 MB), so a larger file sent in a
# single request never reaches the API and the browser only reports "Failed to fetch". The web app
# therefore sends larger files in parts below that cap: start an upload, send each part (a failed
# part is simply sent again), then complete it, which indexes the file like a direct upload.
# Parts are kept in memory for UPLOAD_SESSION_TTL_SECONDS on the single API process.
# ----------------------------------------------------------------------------------------------
UPLOAD_CHUNK_BYTES = 3 * 1024 * 1024
UPLOAD_SESSION_TTL_SECONDS = 30 * 60
MAX_OPEN_UPLOADS_PER_WORKSPACE = 4
_UPLOAD_SESSIONS: dict = {}


class UploadStartRequest(BaseModel):
    filename: str = PydanticField(..., min_length=1, max_length=255)
    size: int = PydanticField(..., ge=1)
    title: Optional[str] = PydanticField(None, max_length=255)
    content_type: Optional[str] = PydanticField(None, max_length=120)


class UploadStartResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int


def _expire_upload_sessions() -> None:
    now = time.monotonic()
    for key in [k for k, v in _UPLOAD_SESSIONS.items() if now - v["created"] > UPLOAD_SESSION_TTL_SECONDS]:
        _UPLOAD_SESSIONS.pop(key, None)


def _upload_session(workspace_id: str, upload_id: str) -> dict:
    _expire_upload_sessions()
    session = _UPLOAD_SESSIONS.get(upload_id)
    if not session or session["workspace_id"] != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This upload has expired or does not exist. Please upload the file again.",
        )
    return session


@router.post(
    "/workspaces/{workspace_id}/uploads",
    response_model=UploadStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_chunked_upload(
    workspace_id: str,
    request: UploadStartRequest,
    workspace: dict = Depends(require_workspace),
) -> UploadStartResponse:
    _validate_extension(request.filename)
    _validate_size(request.size)
    _expire_upload_sessions()
    open_here = [s for s in _UPLOAD_SESSIONS.values() if s["workspace_id"] == workspace_id]
    if len(open_here) >= MAX_OPEN_UPLOADS_PER_WORKSPACE:
        # Drop the oldest unfinished upload of this workspace rather than refusing a new one
        oldest = min(open_here, key=lambda s: s["created"])
        _UPLOAD_SESSIONS.pop(oldest["id"], None)

    upload_id = f"upl_{secrets.token_urlsafe(16)}"
    total_chunks = math.ceil(request.size / UPLOAD_CHUNK_BYTES)
    _UPLOAD_SESSIONS[upload_id] = {
        "id": upload_id,
        "workspace_id": workspace_id,
        "filename": os.path.basename(request.filename),
        "title": request.title,
        "content_type": request.content_type or "application/octet-stream",
        "size": request.size,
        "total_chunks": total_chunks,
        "chunks": {},
        "created": time.monotonic(),
    }
    return UploadStartResponse(upload_id=upload_id, chunk_size=UPLOAD_CHUNK_BYTES, total_chunks=total_chunks)


@router.put("/workspaces/{workspace_id}/uploads/{upload_id}/chunks/{index}")
async def upload_chunk(
    workspace_id: str,
    upload_id: str,
    index: int,
    http_request: Request,
    workspace: dict = Depends(require_workspace),
) -> dict:
    session = _upload_session(workspace_id, upload_id)
    if index < 0 or index >= session["total_chunks"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload part number.")
    data = await http_request.body()
    is_last = index == session["total_chunks"] - 1
    expected = session["size"] - UPLOAD_CHUNK_BYTES * index if is_last else UPLOAD_CHUNK_BYTES
    if len(data) != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload part {index + 1} is {len(data)} bytes; expected {expected}.",
        )
    session["chunks"][index] = data
    return {"upload_id": upload_id, "received_chunks": len(session["chunks"]), "total_chunks": session["total_chunks"]}


@router.post(
    "/workspaces/{workspace_id}/uploads/{upload_id}/complete",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_chunked_upload(
    workspace_id: str,
    upload_id: str,
    response: Response,
    workspace: dict = Depends(require_workspace),
) -> DocumentResponse:
    session = _upload_session(workspace_id, upload_id)
    missing = [i + 1 for i in range(session["total_chunks"]) if i not in session["chunks"]]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The upload is missing part(s) {', '.join(map(str, missing[:5]))}.",
        )
    _UPLOAD_SESSIONS.pop(upload_id, None)
    file_bytes = b"".join(session["chunks"][i] for i in range(session["total_chunks"]))
    return await _accept_document(
        workspace_id, response, session["filename"], session["content_type"], file_bytes, session["title"]
    )


INGEST_WAIT_SECONDS = 20
_INGEST_TASKS: set = set()
_GENERIC_INGEST_ERROR = "This file could not be processed. Check that it is a valid, text-based document and try again."
_IN_PROGRESS = ("uploading", "processing", "extracting", "indexing")


async def _ingest_document(
    mode: dict,
    workspace_id: str,
    doc_id: str,
    doc_title: str,
    filename: str,
    file_type: str,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """Parses, (OCRs), chunks, embeds and stores one document. Returns the updated record."""
    from backend.app.services.notification_service import notification_service
    from backend.app.services.ocr import ocr_available, ocr_pages, pages_needing_ocr, pdf_page_count

    try:
        # Step A: parse text, headings and page numbers
        parsed_pages = await asyncio.to_thread(document_parser.parse, file_bytes, file_type)
        page_count = len(parsed_pages)

        # Step B: scanned or image-only PDF pages are read with OCR
        ocr_used = 0
        if file_type == "pdf":
            total = await asyncio.to_thread(pdf_page_count, file_bytes)
            page_count = max(page_count, total)
            missing = pages_needing_ocr(parsed_pages, total)
            if missing and ocr_available():
                await document_repo.update_status(doc_id, status="extracting", page_count=page_count)
                ocr_results = await ocr_pages(file_bytes, missing)
                if ocr_results:
                    ocr_used = len(ocr_results)
                    by_page = {p.page_number: p for p in parsed_pages}
                    by_page.update({p.page_number: p for p in ocr_results})
                    parsed_pages = [by_page[n] for n in sorted(by_page)]

        readable = [
            p for p in parsed_pages
            if (p.text or "").strip() and not re.fullmatch(r"\[[^\]]*\]", (p.text or "").strip())
        ]
        if not readable:
            raise DocumentContentError(
                "No readable text was found in this document. If it is a scan, make sure the pages are clear; "
                "scanned pages are read with AI only when an AI key is configured."
            )

        await document_repo.update_status(doc_id, status="extracting", page_count=page_count)

        # Step C: chunk pages into overlapping, heading-aware chunks
        chunks = chunker_service.chunk_pages(
            workspace_id=workspace_id,
            document_id=doc_id,
            pages=parsed_pages,
            document_title=doc_title,
            source_filename=filename,
        )
        if not chunks:
            raise DocumentContentError("No readable text was found in this document.")

        # Step D: embeddings in batches, tagged with the model used
        await document_repo.update_status(doc_id, status="indexing")
        vectors, model_tag = await embedding_service.embed_documents([c.text for c in chunks])
        chunk_dicts = []
        for c, embedding in zip(chunks, vectors):
            c_dict = c.to_dict()
            c_dict["embedding"] = embedding
            c_dict["metadata"] = {**(c_dict.get("metadata") or {}), "embedding_model": model_tag}
            c_dict["document_name"] = filename
            c_dict["document_title"] = doc_title
            chunk_dicts.append(c_dict)

        # Step E: store the original file and the chunks
        storage_path = await storage_service.upload_file(
            workspace_id=workspace_id,
            document_id=doc_id,
            filename=filename,
            file_bytes=file_bytes,
            content_type=content_type,
        )
        await document_repo.update_status(doc_id, status="indexing", storage_path=storage_path)
        await chunk_repo.insert_chunks(chunk_dicts)

        summary_text = f"Indexed {len(chunks)} semantic chunks across {page_count} pages for grounded AI retrieval."
        if ocr_used:
            summary_text += f" {ocr_used} scanned page{'s were' if ocr_used != 1 else ' was'} read with OCR."
        updated_doc = await document_repo.update_status(
            doc_id,
            status="ready",
            page_count=page_count,
            chunk_count=len(chunks),
            summary=summary_text,
        )
        await workspace_repo.increment_doc_count(workspace_id, delta=1)
        try:
            await activity_repo.add_activity(
                workspace_id=workspace_id,
                event_type="source_added",
                title=f"Source Added: {filename}",
                description=f"Indexed {page_count} pages ({len(chunks)} vectors) for grounded RAG.",
            )
        except Exception:
            pass
        await notification_service.document_ready(workspace_id, updated_doc)
        try:
            # Topic map, flashcards and quiz questions for the new document are prepared in the background
            from backend.app.services.study_prep import study_prep_service

            study_prep_service.schedule(workspace_id, force=True)
        except Exception as prep_err:
            logger.warning(f"Could not schedule study material preparation for {workspace_id}: {prep_err}")
        return updated_doc

    except Exception as e:
        expected = isinstance(e, (DocumentContentError, EmbeddingUnavailableError))
        if expected:
            logger.warning(f"Document ingestion rejected for doc {doc_id}: {e}")
        else:
            logger.error(f"Document ingestion failed for doc {doc_id}: {e}", exc_info=True)
        await chunk_repo.delete_by_document(doc_id)
        if not mode["background"]:
            # The uploader is still waiting: remove the record and report the error directly
            await document_repo.delete(doc_id)
            raise
        # Processing continued in the background: keep the record so the failure is visible
        reason = str(e) if expected else _GENERIC_INGEST_ERROR
        failed = await document_repo.update_status(doc_id, status="failed", error_message=reason)
        await notification_service.document_failed(workspace_id, failed or {"id": doc_id, "title": doc_title}, reason)
        return failed or {}


async def mark_interrupted_documents() -> int:
    """Documents left mid-processing by a restart are marked failed so they don't spin forever."""
    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if not pool:
        return 0
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE documents SET status = 'failed', error_message = $1, updated_at = NOW() "
            "WHERE status = ANY($2::text[]) AND updated_at < NOW() - INTERVAL '10 minutes'",
            "Processing was interrupted. Please delete this file and upload it again.",
            list(_IN_PROGRESS),
        )
    return int(result.split()[-1]) if result else 0


@router.get(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentListResponse,
)
async def list_workspace_documents(
    workspace_id: str, workspace: dict = Depends(require_workspace)
) -> DocumentListResponse:
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    docs = await document_repo.list_by_workspace(workspace_id)
    return DocumentListResponse(
        workspace_id=workspace_id,
        documents=[DocumentResponse(**d) for d in docs],
        total_count=len(docs),
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, user: CurrentUser = Depends(get_current_user)) -> DocumentResponse:
    doc = await ensure_document_access(await document_repo.get_by_id(document_id), user)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DocumentResponse(**doc)


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    doc = await ensure_document_access(await document_repo.get_by_id(document_id), user)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage path for document '{document_id}' not found.",
        )
    file_bytes = await storage_service.get_file_bytes(storage_path)
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content could not be retrieved.",
        )
    filename = _safe_filename(doc.get("filename", "document.pdf"))
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/documents/{document_id}/view")
async def view_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    doc = await ensure_document_access(await document_repo.get_by_id(document_id), user)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage path for document '{document_id}' not found.",
        )
    file_bytes = await storage_service.get_file_bytes(storage_path)
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content could not be retrieved.",
        )
    filename = _safe_filename(doc.get("filename", "document.pdf"))
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    doc = await ensure_document_access(await document_repo.get_by_id(document_id), user)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    workspace_id = doc["workspace_id"]
    # Study material written from this document goes with it
    from backend.app.repositories.concepts import concept_repo
    from backend.app.repositories.quizzes import quiz_repo
    from backend.app.repositories.secondary import flashcard_repo

    await concept_repo.delete_by_document(document_id)
    await quiz_repo.delete_question_bank_by_document(workspace_id, document_id)
    await flashcard_repo.delete_by_document(workspace_id, document_id)
    await chunk_repo.delete_by_document(document_id)
    await document_repo.delete(document_id)
    await storage_service.delete_file(doc.get("storage_path"))
    await workspace_repo.increment_doc_count(workspace_id, delta=-1)

    return {"success": True, "message": f"Document '{document_id}' deleted successfully."}
