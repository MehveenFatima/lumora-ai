import os
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
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
from backend.app.services.embeddings import embedding_service
from backend.app.services.storage import storage_service
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Documents"])

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: str,
    file: UploadFile = File(...),
    title: str = Form(None),
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
        parsed_pages = document_parser.parse(file_bytes, file_type)
        page_count = len(parsed_pages)

        # Step C: Upload original file to Supabase storage
        storage_path = await storage_service.upload_file(
            workspace_id=workspace_id,
            document_id=doc_id,
            filename=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )

        # Step D: Update status to extracting with storage path
        await document_repo.update_status(
            doc_id, status="extracting", page_count=page_count, storage_path=storage_path
        )

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

        # Step G: Generate embeddings for chunks
        chunk_dicts = []
        for c in chunks:
            embedding = await embedding_service.get_embedding(c.text)
            c_dict = c.to_dict()
            c_dict["embedding"] = embedding
            c_dict["document_name"] = file.filename
            c_dict["document_title"] = doc_title
            chunk_dicts.append(c_dict)

        # Step H: Store chunks in database
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

    except Exception as e:
        logger.error(f"Document ingestion failed for doc {doc_id}: {e}")
        failed_doc = await document_repo.update_status(
            doc_id, status="failed", error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing pipeline failed: {str(e)}",
        )


@router.get(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentListResponse,
)
async def list_workspace_documents(workspace_id: str) -> DocumentListResponse:
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
async def get_document(document_id: str) -> DocumentResponse:
    doc = await document_repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DocumentResponse(**doc)


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    doc = await document_repo.get_by_id(document_id)
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
    filename = doc.get("filename", "document.pdf")
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/documents/{document_id}/view")
async def view_document(document_id: str):
    doc = await document_repo.get_by_id(document_id)
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
    filename = doc.get("filename", "document.pdf")
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(document_id: str):
    doc = await document_repo.get_by_id(document_id)
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
