from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.agents.state import ResearchReport, ReportSection
from app.models import (
    ClaimEvidence,
    ResearchClaim,
    ResearchReportRecord,
    ResearchSource,
    ResearchTask,
    ResearchTaskStatus,
    ReportVersion,
    ReportVerificationStatus,
    ReviewDecision,
    ReviewDecisionType,
    ReviewStatus,
    TaskEvent,
)
from app.schemas.report import (
    ClaimEvidenceResponse,
    ClaimResponse,
    ReportDetailResponse,
    ReportReviewRequest,
    ReportReviewResponse,
    ReportRevisionRequest,
    ReportVersionResponse,
    SourceResponse,
)
from app.services.report_rendering import render_report_markdown
from app.services.report_exports import render_docx, render_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


def _owned_report(db: DbSession, owner_id: UUID, report_id: UUID) -> ResearchReportRecord:
    report = db.scalar(
        select(ResearchReportRecord)
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(
            ResearchReportRecord.id == report_id,
            ResearchTask.owner_id == owner_id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


def _report_detail(db: DbSession, report: ResearchReportRecord) -> ReportDetailResponse:
    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == report.current_version,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current report version is unavailable.",
        )

    task = db.get(ResearchTask, report.task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    sources = db.scalars(
        select(ResearchSource)
        .options(selectinload(ResearchSource.passages))
        .where(ResearchSource.task_id == task.id)
        .order_by(ResearchSource.created_at, ResearchSource.id)
    ).all()
    claim_records = db.scalars(
        select(ResearchClaim)
        .options(
            selectinload(ResearchClaim.evidence_links).selectinload(ClaimEvidence.evidence),
            selectinload(ResearchClaim.verifications),
        )
        .where(ResearchClaim.task_id == task.id)
        .order_by(ResearchClaim.created_at, ResearchClaim.id)
    ).all()
    claims = [
        ClaimResponse(
            id=claim.id,
            claim_key=claim.claim_key,
            text=claim.text,
            claim_type=claim.claim_type,
            evidence=[
                ClaimEvidenceResponse(
                    evidence_id=link.evidence.id,
                    source_id=link.evidence.source_id,
                    provider_source_id=link.evidence.source.provider_source_id,
                    passage=link.evidence.text,
                )
                for link in claim.evidence_links
            ],
            verifications=claim.verifications,
        )
        for claim in claim_records
    ]
    return ReportDetailResponse(
        id=report.id,
        task_id=task.id,
        review_status=report.review_status,
        current_version=report.current_version,
        version=ReportVersionResponse.model_validate(version),
        sources=[SourceResponse.model_validate(source) for source in sources],
        claims=claims,
    )


@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report(report_id: UUID, db: DbSession, user: CurrentUser) -> ReportDetailResponse:
    return _report_detail(db, _owned_report(db, user.id, report_id))


@router.get("/tasks/{task_id}/report", response_model=ReportDetailResponse)
def get_task_report(task_id: UUID, db: DbSession, user: CurrentUser) -> ReportDetailResponse:
    report = db.scalar(
        select(ResearchReportRecord)
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(
            ResearchTask.id == task_id,
            ResearchTask.owner_id == user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return _report_detail(db, report)


@router.get("/{report_id}/versions", response_model=list[ReportVersionResponse])
def list_report_versions(
    report_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[ReportVersion]:
    report = _owned_report(db, user.id, report_id)
    return list(
        db.scalars(
            select(ReportVersion)
            .where(ReportVersion.report_id == report.id)
            .order_by(ReportVersion.version.desc())
        ).all()
    )


@router.post(
    "/{report_id}/versions/{version_number}/reverify",
    response_model=ReportReviewResponse,
)
def retry_report_verification(
    report_id: UUID,
    version_number: int,
    db: DbSession,
    user: CurrentUser,
) -> ReportReviewResponse:
    report = db.scalar(
        select(ResearchReportRecord)
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(
            ResearchReportRecord.id == report_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    task = db.scalar(
        select(ResearchTask)
        .where(
            ResearchTask.id == report.task_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if (
        task.status != ResearchTaskStatus.WAITING_REVIEW
        or report.review_status != ReviewStatus.PENDING
        or version_number != report.current_version
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the current unreviewed report version can be re-verified.",
        )
    version = db.scalar(
        select(ReportVersion)
        .where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == version_number,
        )
        .with_for_update()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")
    if version.verification_status != ReportVerificationStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a failed verification can be retried.",
        )
    version.verification_status = ReportVerificationStatus.PENDING
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type="report.verification.retried",
            stage="human_review",
            payload={"version": version_number},
        )
    )
    db.commit()
    return ReportReviewResponse(
        report_id=report.id,
        task_id=task.id,
        review_status=report.review_status,
        task_status=task.status.value,
        current_version=version_number,
    )


@router.post("/{report_id}/review", response_model=ReportReviewResponse)
def review_report(
    report_id: UUID,
    body: ReportReviewRequest,
    db: DbSession,
    user: CurrentUser,
) -> ReportReviewResponse:
    report = db.scalar(
        select(ResearchReportRecord)
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(
            ResearchReportRecord.id == report_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    task = db.scalar(
        select(ResearchTask)
        .where(
            ResearchTask.id == report.task_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if task.status != ResearchTaskStatus.WAITING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only reports awaiting review can be approved or rejected.",
        )
    if report.review_status != ReviewStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report already has a review decision.",
        )

    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == report.current_version,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current report version is unavailable.",
        )
    if version.verification_status != ReportVerificationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report version is not ready for review verification.",
        )
    decision = ReviewDecisionType(body.decision)
    report.review_status = (
        ReviewStatus.APPROVED
        if decision == ReviewDecisionType.APPROVED
        else ReviewStatus.REJECTED
    )
    task.status = ResearchTaskStatus.COMPLETED
    db.add(
        ReviewDecision(
            report_version_id=version.id,
            reviewer_id=user.id,
            decision=decision,
            comment=body.comment.strip() if body.comment else None,
        )
    )
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type=f"report.{decision.value}",
            stage="human_review",
            payload={"review_status": report.review_status.value},
        )
    )
    db.commit()
    db.refresh(report)
    db.refresh(task)
    return ReportReviewResponse(
        report_id=report.id,
        task_id=task.id,
        review_status=report.review_status,
        task_status=task.status.value,
        current_version=report.current_version,
    )


@router.post("/{report_id}/revisions", response_model=ReportReviewResponse)
def create_report_revision(
    report_id: UUID,
    body: ReportRevisionRequest,
    db: DbSession,
    user: CurrentUser,
) -> ReportReviewResponse:
    report = db.scalar(
        select(ResearchReportRecord)
        .join(ResearchTask, ResearchTask.id == ResearchReportRecord.task_id)
        .where(
            ResearchReportRecord.id == report_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    task = db.scalar(
        select(ResearchTask)
        .where(
            ResearchTask.id == report.task_id,
            ResearchTask.owner_id == user.id,
        )
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if (
        report.review_status == ReviewStatus.PENDING
        or task.status != ResearchTaskStatus.COMPLETED
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an already reviewed report can be revised.",
        )
    if body.base_version != report.current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The report changed since this revision was opened. Reload and try again.",
        )

    sources = db.scalars(
        select(ResearchSource).where(ResearchSource.task_id == task.id)
    ).all()
    source_by_provider_id = {source.provider_source_id: source for source in sources}
    referenced_ids = set(body.source_ids).union(
        source_id for section in body.sections for source_id in section.source_ids
    )
    if not referenced_ids.issubset(source_by_provider_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A report citation does not belong to this research task.",
        )

    previous_version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == report.current_version,
        )
    )
    if previous_version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current report version is unavailable.",
        )

    next_version_number = report.current_version + 1
    revised_content = ResearchReport(
        executive_summary=body.executive_summary,
        sections=[
            ReportSection.model_validate(section.model_dump())
            for section in body.sections
        ],
        methodology=body.methodology,
        limitations=body.limitations,
        source_ids=body.source_ids,
    )
    db.add(
        ReviewDecision(
            report_version_id=previous_version.id,
            reviewer_id=user.id,
            decision=ReviewDecisionType.REVISION_REQUESTED,
            comment=f"Revised as version {next_version_number}.",
        )
    )
    db.add(
        ReportVersion(
            report_id=report.id,
            version=next_version_number,
            executive_summary=revised_content.executive_summary,
            sections=[
                section.model_dump(mode="json") for section in revised_content.sections
            ],
            methodology=revised_content.methodology,
            limitations=revised_content.limitations,
            markdown=render_report_markdown(revised_content, source_by_provider_id),
            created_by_id=user.id,
            verification_status=ReportVerificationStatus.PENDING,
            verification_results=[],
        )
    )
    report.current_version = next_version_number
    report.review_status = ReviewStatus.PENDING
    task.status = ResearchTaskStatus.WAITING_REVIEW
    task.completed_at = None
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type="report.revised",
            stage="human_review",
            payload={"version": next_version_number},
        )
    )
    db.commit()
    db.refresh(report)
    db.refresh(task)
    return ReportReviewResponse(
        report_id=report.id,
        task_id=task.id,
        review_status=report.review_status,
        task_status=task.status.value,
        current_version=report.current_version,
    )


@router.get("/{report_id}/export/markdown")
def export_markdown(report_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    report = _owned_report(db, user.id, report_id)
    if report.review_status != ReviewStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an approved report version can be exported.",
        )
    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == report.current_version,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current report version is unavailable.",
        )
    return Response(
        content=version.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="research-report-{report.id}.md"'
        },
    )


def _approved_export_data(
    report_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> tuple[ReportVersion, dict[str, ResearchSource]]:
    report = _owned_report(db, user.id, report_id)
    if report.review_status != ReviewStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an approved report version can be exported.",
        )
    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version == report.current_version,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current report version is unavailable.",
        )
    task = db.get(ResearchTask, report.task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    sources = db.scalars(
        select(ResearchSource).where(ResearchSource.task_id == task.id)
    ).all()
    return version, {source.provider_source_id: source for source in sources}


@router.get("/{report_id}/export/docx")
def export_docx(report_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    version, sources = _approved_export_data(report_id, db, user)
    return Response(
        content=render_docx(version, sources),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="research-report-{report_id}.docx"'
        },
    )


@router.get("/{report_id}/export/pdf")
def export_pdf(report_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    version, sources = _approved_export_data(report_id, db, user)
    return Response(
        content=render_pdf(version, sources),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="research-report-{report_id}.pdf"'},
    )
