import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.api.v1.projects import _owned_project
from app.models import (
    ProjectStatus,
    ResearchBrief,
    ResearchTask,
    ResearchTaskStatus,
    TaskEvent,
)
from app.providers.llm import validate_llm_configuration
from app.providers.search import validate_search_configuration
from app.schemas.research import ResearchTaskPage, ResearchTaskResponse

logger = logging.getLogger("researchpilot.research")
router = APIRouter(tags=["research"])


@router.post(
    "/projects/{project_id}/briefs/{brief_id}/tasks",
    response_model=ResearchTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_research(
    project_id: UUID,
    brief_id: UUID,
    response: Response,
    db: DbSession,
    user: CurrentUser,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> ResearchTask:
    project = _owned_project(db, user.id, project_id)
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived projects cannot start research.",
        )
    brief = db.scalar(
        select(ResearchBrief).where(
            ResearchBrief.id == brief_id,
            ResearchBrief.project_id == project.id,
        )
    )
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research brief not found.")

    if idempotency_key:
        existing = db.scalar(
            select(ResearchTask).where(
                ResearchTask.owner_id == user.id,
                ResearchTask.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.brief_id != brief.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for a different research brief.",
                )
            response.status_code = status.HTTP_200_OK
            return existing

    try:
        validate_llm_configuration()
        validate_search_configuration()
    except RuntimeError as error:
        logger.info("research.provider_not_configured", extra={"reason": str(error)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from None

    task = ResearchTask(
        owner_id=user.id,
        project_id=project.id,
        brief_id=brief.id,
        idempotency_key=idempotency_key,
        status=ResearchTaskStatus.QUEUED,
    )
    db.add(task)
    db.flush()
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type="task.queued",
            payload={"status": ResearchTaskStatus.QUEUED.value},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.scalar(
                select(ResearchTask).where(
                    ResearchTask.owner_id == user.id,
                    ResearchTask.idempotency_key == idempotency_key,
                )
            )
            if existing is not None and existing.brief_id == brief.id:
                response.status_code = status.HTTP_200_OK
                return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research task could not be queued due to a conflicting request.",
        ) from None
    db.refresh(task)
    logger.info("research.task.queued", extra={"task_id": str(task.id)})
    return task


@router.get("/projects/{project_id}/tasks", response_model=ResearchTaskPage)
def list_project_tasks(
    project_id: UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ResearchTaskPage:
    project = _owned_project(db, user.id, project_id)
    base = select(ResearchTask).where(
        ResearchTask.project_id == project.id,
        ResearchTask.owner_id == user.id,
    )
    total = db.scalar(
        select(func.count())
        .select_from(ResearchTask)
        .where(
            ResearchTask.project_id == project.id,
            ResearchTask.owner_id == user.id,
        )
    ) or 0
    tasks = db.scalars(
        base.order_by(ResearchTask.created_at.desc(), ResearchTask.id).limit(limit).offset(offset)
    ).all()
    return ResearchTaskPage(
        items=[ResearchTaskResponse.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


def _owned_task(db: DbSession, user_id: UUID, task_id: UUID) -> ResearchTask:
    task = db.scalar(
        select(ResearchTask).where(
            ResearchTask.id == task_id,
            ResearchTask.owner_id == user_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found.")
    return task


@router.get("/tasks", response_model=ResearchTaskPage)
def list_research_tasks(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ResearchTaskPage:
    owner_filter = ResearchTask.owner_id == user.id
    total = db.scalar(
        select(func.count()).select_from(ResearchTask).where(owner_filter)
    ) or 0
    tasks = db.scalars(
        select(ResearchTask)
        .where(owner_filter)
        .order_by(ResearchTask.created_at.desc(), ResearchTask.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return ResearchTaskPage(
        items=[ResearchTaskResponse.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}", response_model=ResearchTaskResponse)
def get_research_task(task_id: UUID, db: DbSession, user: CurrentUser) -> ResearchTask:
    return _owned_task(db, user.id, task_id)


@router.post("/tasks/{task_id}/cancel", response_model=ResearchTaskResponse)
def cancel_research_task(task_id: UUID, db: DbSession, user: CurrentUser) -> ResearchTask:
    task = _owned_task(db, user.id, task_id)
    if task.status in {
        ResearchTaskStatus.COMPLETED,
        ResearchTaskStatus.FAILED,
        ResearchTaskStatus.CANCELLED,
        ResearchTaskStatus.WAITING_REVIEW,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task in '{task.status.value}' state cannot be cancelled.",
        )
    if task.status == ResearchTaskStatus.QUEUED:
        task.status = ResearchTaskStatus.CANCELLED
        task.completed_at = datetime.now(UTC)
        event_type = "task.cancelled"
    else:
        task.cancellation_requested = True
        event_type = "task.cancellation_requested"
    db.add(TaskEvent(task_id=task.id, event_type=event_type, payload={}))
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/resume", response_model=ResearchTaskResponse)
def resume_research_task(task_id: UUID, db: DbSession, user: CurrentUser) -> ResearchTask:
    task = _owned_task(db, user.id, task_id)
    if task.status != ResearchTaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed research tasks can be resumed.",
        )
    if task.attempt_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task retry limit reached. Create a new research task instead.",
        )
    try:
        validate_llm_configuration()
        validate_search_configuration()
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from None
    task.status = ResearchTaskStatus.QUEUED
    task.safe_error_code = None
    task.completed_at = None
    task.cancellation_requested = False
    task.worker_id = None
    task.lease_expires_at = None
    db.add(TaskEvent(task_id=task.id, event_type="task.resumed", payload={}))
    db.commit()
    db.refresh(task)
    return task


def _read_events(task_id: UUID, after_id: int):
    from app.database import get_session_factory

    with get_session_factory()() as db:
        events = db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id, TaskEvent.id > after_id)
            .order_by(TaskEvent.id)
            .limit(100)
        ).all()
        task = db.get(ResearchTask, task_id)
        return events, task.status if task else None


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: UUID,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    last_event_id: int = Header(default=0, alias="Last-Event-ID", ge=0),
) -> StreamingResponse:
    _owned_task(db, user.id, task_id)

    async def events() -> AsyncIterator[str]:
        cursor = last_event_id
        yield "retry: 2000\n\n"
        while not await request.is_disconnected():
            rows, task_status = await asyncio.to_thread(_read_events, task_id, cursor)
            for event in rows:
                cursor = event.id
                envelope = {
                    "task_id": str(task_id),
                    "type": event.event_type,
                    "stage": event.stage,
                    "agent": event.agent_name,
                    "timestamp": event.created_at.isoformat(),
                    "payload": event.payload,
                }
                yield f"id: {event.id}\nevent: {event.event_type}\ndata: {json.dumps(envelope)}\n\n"
            if task_status is None:
                return
            if task_status in {
                ResearchTaskStatus.WAITING_REVIEW,
                ResearchTaskStatus.COMPLETED,
                ResearchTaskStatus.FAILED,
                ResearchTaskStatus.CANCELLED,
            }:
                return
            if not rows:
                yield f": heartbeat {int(time.time())}\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
