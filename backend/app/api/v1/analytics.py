from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import (
    ProjectStatus,
    ResearchProject,
    ResearchReportRecord,
    ResearchSource,
    ResearchTask,
    ResearchTaskStatus,
    ReviewStatus,
)
from app.schemas.analytics import (
    DailyTaskCount,
    RecentTask,
    StatusCount,
    WorkspaceAnalytics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/workspace", response_model=WorkspaceAnalytics)
def workspace_analytics(
    db: DbSession,
    user: CurrentUser,
    days: int = Query(default=30, ge=7, le=90),
) -> WorkspaceAnalytics:
    if days not in (7, 30, 90):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The analytics period must be 7, 30, or 90 days.",
        )
    now = datetime.now(UTC)
    first_day = now.date() - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=UTC)
    task_scope = (
        ResearchTask.owner_id == user.id,
        ResearchTask.created_at >= since,
    )

    projects_total = db.scalar(
        select(func.count())
        .select_from(ResearchProject)
        .where(ResearchProject.owner_id == user.id)
    ) or 0
    projects_active = db.scalar(
        select(func.count())
        .select_from(ResearchProject)
        .where(
            ResearchProject.owner_id == user.id,
            ResearchProject.status == ProjectStatus.ACTIVE,
        )
    ) or 0
    task_status_rows = db.execute(
        select(ResearchTask.status, func.count())
        .where(*task_scope)
        .group_by(ResearchTask.status)
    ).all()
    task_day = func.date(func.timezone("UTC", ResearchTask.created_at))
    daily_rows = db.execute(
        select(
            task_day,
            ResearchTask.status,
            func.count(),
        )
        .where(*task_scope)
        .group_by(task_day, ResearchTask.status)
    ).all()
    report_status_rows = db.execute(
        select(ResearchReportRecord.review_status, func.count())
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(*task_scope)
        .group_by(ResearchReportRecord.review_status)
    ).all()
    sources_total = db.scalar(
        select(func.count())
        .select_from(ResearchSource)
        .join(ResearchTask, ResearchTask.id == ResearchSource.task_id)
        .where(*task_scope)
    ) or 0
    recent_rows = db.execute(
        select(
            ResearchTask.id,
            ResearchTask.project_id,
            ResearchProject.title,
            ResearchTask.status,
            ResearchTask.created_at,
        )
        .join(ResearchProject, ResearchProject.id == ResearchTask.project_id)
        .where(*task_scope, ResearchProject.owner_id == user.id)
        .order_by(ResearchTask.created_at.desc(), ResearchTask.id)
        .limit(8)
    ).all()

    task_counts = {status: count for status, count in task_status_rows}
    report_counts = {status: count for status, count in report_status_rows}
    daily_counts: dict[date, dict[str, int]] = {}
    for day_value, task_status, count in daily_rows:
        day = day_value if isinstance(day_value, date) else date.fromisoformat(day_value)
        counts = daily_counts.setdefault(day, {"total": 0, "failed": 0})
        counts["total"] += count
        if task_status == ResearchTaskStatus.FAILED:
            counts["failed"] += count

    return WorkspaceAnalytics(
        period_days=days,
        generated_at=now,
        projects_total=projects_total,
        projects_active=projects_active,
        tasks_total=sum(task_counts.values()),
        tasks_by_status=[
            StatusCount(status=status.value, count=task_counts.get(status, 0))
            for status in ResearchTaskStatus
        ],
        reports_total=sum(report_counts.values()),
        reports_by_status=[
            StatusCount(status=status.value, count=report_counts.get(status, 0))
            for status in ReviewStatus
        ],
        sources_total=sources_total,
        daily_tasks=[
            DailyTaskCount(
                day=first_day + timedelta(days=offset),
                total=daily_counts.get(first_day + timedelta(days=offset), {}).get("total", 0),
                failed=daily_counts.get(first_day + timedelta(days=offset), {}).get("failed", 0),
            )
            for offset in range(days)
        ],
        recent_tasks=[
            RecentTask(
                id=task_id,
                project_id=project_id,
                project_title=project_title,
                status=task_status,
                created_at=created_at,
            )
            for task_id, project_id, project_title, task_status, created_at in recent_rows
        ],
    )
