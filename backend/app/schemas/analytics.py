from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.research import ResearchTaskStatus, ReviewStatus


class StatusCount(BaseModel):
    status: str
    count: int


class DailyTaskCount(BaseModel):
    day: date
    total: int
    failed: int


class RecentTask(BaseModel):
    id: UUID
    project_id: UUID
    project_title: str
    status: ResearchTaskStatus
    created_at: datetime


class WorkspaceAnalytics(BaseModel):
    period_days: Literal[7, 30, 90]
    generated_at: datetime
    projects_total: int
    projects_active: int
    tasks_total: int
    tasks_by_status: list[StatusCount]
    reports_total: int
    reports_by_status: list[StatusCount]
    sources_total: int
    daily_tasks: list[DailyTaskCount]
    recent_tasks: list[RecentTask]
