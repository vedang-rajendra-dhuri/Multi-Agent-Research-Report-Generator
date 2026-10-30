import hashlib
import logging
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.api.v1.projects import _owned_project
from app.models import DocumentChunk, ProjectDocument, ProjectStatus
from app.schemas.document import ProjectDocumentResponse
from app.services.document_ingestion import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_TYPES,
    DocumentIngestionError,
    chunk_text,
    extract_text,
    sanitize_file_name,
)

logger = logging.getLogger("researchpilot.documents")
router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


@router.post("", response_model=ProjectDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_project_document(
    project_id: UUID,
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> ProjectDocument:
    project = _owned_project(db, user.id, project_id)
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived projects cannot accept documents.",
        )
    try:
        file_name = sanitize_file_name(file.filename or "")
        file_type = file_name.rsplit(".", 1)[-1].lower()
        if f".{file_type}" not in SUPPORTED_TYPES:
            raise DocumentIngestionError("Upload a PDF, DOCX, TXT, or Markdown file.")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise DocumentIngestionError("Documents are limited to 10 MB.")
        text = extract_text(file_name, data)
        chunks = chunk_text(text)
    except DocumentIngestionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    finally:
        await file.close()

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(ProjectDocument.id).where(
            ProjectDocument.project_id == project.id,
            ProjectDocument.sha256 == digest,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document has already been uploaded to the project.",
        )

    document = ProjectDocument(
        project_id=project.id,
        file_name=file_name,
        file_type=f".{file_type}",
        sha256=digest,
        size_bytes=len(data),
        extracted_characters=len(text),
    )
    db.add(document)
    db.flush()
    db.add_all(
        [
            DocumentChunk(document_id=document.id, chunk_index=index, text=chunk)
            for index, chunk in enumerate(chunks)
        ]
    )
    try:
        db.commit()
        db.refresh(document)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document has already been uploaded to the project.",
        ) from None
    logger.info(
        "document.uploaded",
        extra={
            "project_id": str(project.id),
            "document_id": str(document.id),
            "chunk_count": len(chunks),
        },
    )
    return document


@router.get("", response_model=list[ProjectDocumentResponse])
def list_project_documents(
    project_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[ProjectDocument]:
    project = _owned_project(db, user.id, project_id)
    return list(
        db.scalars(
            select(ProjectDocument)
            .options(selectinload(ProjectDocument.chunks))
            .where(ProjectDocument.project_id == project.id)
            .order_by(ProjectDocument.created_at.desc(), ProjectDocument.id)
        ).all()
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_document(
    project_id: UUID,
    document_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    project = _owned_project(db, user.id, project_id)
    document = db.scalar(
        select(ProjectDocument).where(
            ProjectDocument.id == document_id,
            ProjectDocument.project_id == project.id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project document not found.",
        )
    db.delete(document)
    db.commit()
