import asyncio
import os
import re
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
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


class DocumentContentError(Exception):
    """The file is valid but contains nothing that can be indexed."""


def _safe_filename(name: str) -> str:
    """Strips characters that could break or inject into the Content-Disposition header."""
    cleaned = "".join(ch for ch in (name or "document") if ch.isprintable() and ch not in '"\\\r\n;')
    return cleaned.strip() or "document"


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: str,
    file: UploadFile = File(...),
    title: str = Form(None),
    workspace: dict = Depends(require_workspace),
) -> DocumentResponse:
    # 1. Validate workspace
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    # 2. Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: PDF, DOCX, PPTX, TXT.",
        )

    # 3. Read and validate file size
    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.max_file_size_bytes / (1024 * 1024):.0f} MB.",
        )

    # 3b. Validate the file signature so a renamed or corrupt file is rejected as a client error
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

    doc_title = title.strip() if title else os.path.splitext(file.filename)[0].replace("_", " ")
    file_type = ext.lstrip(".")

    # 4. Create document record (Status: uploading)
    doc_record = await document_repo.create(
        workspace_id=workspace_id,
        title=doc_title,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        status="uploading",
    )
    doc_id = doc_record["id"]

    try:
        # Step A: Update status to processing
        await document_repo.update_status(doc_id, status="processing")

        # Step B: Parse text and page numbers
        parsed_pages = await asyncio.to_thread(document_parser.parse, file_bytes, file_type)
        page_count = len(parsed_pages)
        readable = [
            p for p in parsed_pages
            if (p.text or "").strip() and not re.fullmatch(r"\[[^\]]*\]", (p.text or "").strip())
        ]
        if not readable:
            raise DocumentContentError(
                "No readable text was found in this document. Scanned or image-only files are not supported yet."
            )

        # Step D: Update status to extracting
        await document_repo.update_status(doc_id, status="extracting", page_count=page_count)

        # Step E: Chunk pages into semantic chunks
        chunks = chunker_service.chunk_pages(
            workspace_id=workspace_id,
            document_id=doc_id,
            pages=parsed_pages,
            document_title=doc_title,
            source_filename=file.filename,
        )

        # Step F: Update status to indexing
        await document_repo.update_status(doc_id, status="indexing")

        if not chunks:
            raise DocumentContentError("No readable text was found in this document.")

        # Step G: Generate embeddings for chunks in batches, tagged with the model used
        vectors, model_tag = await embedding_service.embed_documents([c.text for c in chunks])
        chunk_dicts = []
        for c, embedding in zip(chunks, vectors):
            c_dict = c.to_dict()
            c_dict["embedding"] = embedding
            c_dict["metadata"] = {**(c_dict.get("metadata") or {}), "embedding_model": model_tag}
            c_dict["document_name"] = file.filename
            c_dict["document_title"] = doc_title
            chunk_dicts.append(c_dict)

        # Step H: Store the original file (only once indexing has succeeded) and the chunks
        storage_path = await storage_service.upload_file(
            workspace_id=workspace_id,
            document_id=doc_id,
            filename=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )
        await document_repo.update_status(doc_id, status="indexing", storage_path=storage_path)
        await chunk_repo.insert_chunks(chunk_dicts)

        # Step I: Set status = ready
        summary_text = (
            f"Indexed {len(chunks)} semantic chunks across {page_count} pages for grounded AI retrieval."
        )
        updated_doc = await document_repo.update_status(
            doc_id,
            status="ready",
            page_count=page_count,
            chunk_count=len(chunks),
            summary=summary_text,
        )

        # Increment workspace document count
        await workspace_repo.increment_doc_count(workspace_id, delta=1)

        try:
            await activity_repo.add_activity(
                workspace_id=workspace_id,
                event_type="source_added",
                title=f"Source Added: {file.filename}",
                description=f"Indexed {page_count} pages ({len(chunks)} vectors) for grounded RAG.",
            )
        except Exception:
            pass

        return DocumentResponse(**updated_doc)

    except (DocumentContentError, EmbeddingUnavailableError) as e:
        # Expected, user-actionable failures: remove the partial record so it doesn't linger
        logger.warning(f"Document ingestion rejected for doc {doc_id}: {e}")
        await chunk_repo.delete_by_document(doc_id)
        await document_repo.delete(doc_id)
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(e, EmbeddingUnavailableError)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=str(e))
    except Exception as e:
        logger.error(f"Document ingestion failed for doc {doc_id}: {e}", exc_info=True)
        await chunk_repo.delete_by_document(doc_id)
        await document_repo.delete(doc_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This file could not be processed. Check that it is a valid, text-based document and try again.",
        )


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
    await chunk_repo.delete_by_document(document_id)
    await document_repo.delete(document_id)
    await workspace_repo.increment_doc_count(workspace_id, delta=-1)

    return {"success": True, "message": f"Document '{document_id}' deleted successfully."}
