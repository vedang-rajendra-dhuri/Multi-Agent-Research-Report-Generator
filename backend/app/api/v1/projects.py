from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import ProjectStatus, ResearchBrief, ResearchProject
from app.schemas.project import (
    ProjectCreate,
    ProjectPage,
    ProjectResponse,
    ProjectUpdate,
    ResearchBriefCreate,
    ResearchBriefResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
) -> ResearchProject:
    project = ResearchProject(
        owner_id=user.id,
        title=body.title,
        description=body.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=ProjectPage)
def list_projects(
    db: DbSession,
    user: CurrentUser,
    query: str | None = Query(default=None, max_length=200),
    status_filter: ProjectStatus | None = Query(default=ProjectStatus.ACTIVE, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProjectPage:
    statement = select(ResearchProject).where(ResearchProject.owner_id == user.id)
    count_statement = select(func.count()).select_from(ResearchProject).where(
        ResearchProject.owner_id == user.id
    )
    if status_filter is not None:
        statement = statement.where(ResearchProject.status == status_filter)
        count_statement = count_statement.where(ResearchProject.status == status_filter)
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(ResearchProject.title.ilike(pattern))
        count_statement = count_statement.where(ResearchProject.title.ilike(pattern))

    total = db.scalar(count_statement) or 0
    projects = db.scalars(
        statement.order_by(ResearchProject.updated_at.desc(), ResearchProject.id).limit(limit).offset(offset)
    ).all()
    return ProjectPage(
        items=[ProjectResponse.model_validate(project) for project in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


def _owned_project(db: DbSession, user_id: UUID, project_id: UUID) -> ResearchProject:
    project = db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.owner_id == user_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, db: DbSession, user: CurrentUser) -> ResearchProject:
    return _owned_project(db, user.id, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: DbSession,
    user: CurrentUser,
) -> ResearchProject:
    project = _owned_project(db, user.id, project_id)
    changes = body.model_dump(exclude_unset=True)
    if changes:
        for field, value in changes.items():
            setattr(project, field, value)
        db.commit()
        db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    project = _owned_project(db, user.id, project_id)
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/briefs",
    response_model=ResearchBriefResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_research_brief(
    project_id: UUID,
    body: ResearchBriefCreate,
    db: DbSession,
    user: CurrentUser,
) -> ResearchBrief:
    project = _owned_project(db, user.id, project_id)
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived projects cannot accept new research briefs.",
        )
    brief = ResearchBrief(project_id=project.id, **body.model_dump())
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


@router.get("/{project_id}/briefs", response_model=list[ResearchBriefResponse])
def list_research_briefs(
    project_id: UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ResearchBrief]:
    project = _owned_project(db, user.id, project_id)
    return list(
        db.scalars(
            select(ResearchBrief)
            .where(ResearchBrief.project_id == project.id)
            .order_by(ResearchBrief.created_at.desc(), ResearchBrief.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
