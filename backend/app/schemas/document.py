from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    file_name: str
    file_type: str
    size_bytes: int
    extracted_characters: int
    chunk_count: int
    created_at: datetime
