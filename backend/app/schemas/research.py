from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.research import ResearchTaskStatus


class ResearchTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    brief_id: UUID
    status: ResearchTaskStatus
    current_stage: str | None
    attempt_count: int
    safe_error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ResearchTaskPage(BaseModel):
    items: list[ResearchTaskResponse]
    total: int
    limit: int
    offset: int
