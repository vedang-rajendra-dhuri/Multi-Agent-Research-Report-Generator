from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, ProjectDocument
from app.providers.search import SearchSource

MAX_RETRIEVED_DOCUMENT_CHUNKS = 12
MAX_RETRIEVAL_QUERY_CHARACTERS = 1_000


def retrieve_project_evidence(
    db: Session,
    project_id: UUID,
    query: str,
) -> list[SearchSource]:
    bounded_query = " ".join(query.split())[:MAX_RETRIEVAL_QUERY_CHARACTERS]
    if not bounded_query:
        return []

    text_vector = func.to_tsvector("english", DocumentChunk.text)
    query_vector = func.plainto_tsquery("english", bounded_query)
    rows = db.execute(
        select(DocumentChunk, ProjectDocument)
        .join(ProjectDocument, ProjectDocument.id == DocumentChunk.document_id)
        .where(
            ProjectDocument.project_id == project_id,
            DocumentChunk.text.match(bounded_query, postgresql_regconfig="english"),
        )
        .order_by(func.ts_rank_cd(text_vector, query_vector).desc())
        .limit(MAX_RETRIEVED_DOCUMENT_CHUNKS)
    ).all()
    retrieved_at = datetime.now(UTC)
    return [
        SearchSource(
            source_id=f"doc-{document.id}-chunk-{chunk.chunk_index}",
            title=document.file_name,
            url=f"document://{document.id}",
            retrieved_at=retrieved_at,
            published_date=None,
            passage=chunk.text,
            publisher="Uploaded project document",
            source_type="document",
            locator=f"Section {chunk.chunk_index + 1}",
        )
        for chunk, document in rows
    ]
