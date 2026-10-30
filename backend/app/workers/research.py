import logging
import os
import socket
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Iterator
from uuid import UUID

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.agents.graph import build_research_graph
from app.config import get_settings
from app.database import get_engine, get_session_factory
from app.models import (
    ClaimEvidence,
    ClaimVerification,
    ClaimVerificationStatus,
    EvidencePassage,
    ResearchBrief,
    ResearchClaim,
    ResearchProject,
    ResearchReportRecord,
    ResearchSource,
    ResearchTask,
    ResearchTaskStatus,
    ReportVerificationStatus,
    ReportVersion,
    ReportVerificationStatus,
    ReviewStatus,
    TaskEvent,
)
from app.services.report_rendering import render_report_markdown
from app.services.document_retrieval import retrieve_project_evidence
from app.services.report_verification import verify_report_revision

logger = logging.getLogger("researchpilot.worker")
WORKER_LOCK_ID = 731_825_147


class TaskCancelled(Exception):
    pass


def _event(
    db: Session,
    task_id: UUID,
    event_type: str,
    stage: str | None = None,
    agent_name: str | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        TaskEvent(
            task_id=task_id,
            event_type=event_type,
            stage=stage,
            agent_name=agent_name,
            payload=payload or {},
        )
    )


def _persist_result(db: Session, task: ResearchTask, result: dict) -> None:
    source_by_provider_id: dict[str, ResearchSource] = {}
    evidence_by_provider_id: dict[str, EvidencePassage] = {}
    for source_data in result.get("sources", []):
        source = ResearchSource(
            task_id=task.id,
            provider_source_id=source_data.source_id,
            url=source_data.url,
            title=source_data.title,
            published_date=source_data.published_date,
            retrieval_status="retrieved",
            metadata_json={"retrieved_at": source_data.retrieved_at.isoformat()},
            publisher=source_data.publisher,
            source_type=source_data.source_type,
        )
        db.add(source)
        db.flush()
        source_by_provider_id[source.provider_source_id] = source
        if source_data.passage:
            evidence = EvidencePassage(
                source_id=source.id,
                text=source_data.passage,
                locator=source_data.locator,
            )
            db.add(evidence)
            db.flush()
            evidence_by_provider_id[source.provider_source_id] = evidence

    verification_by_key = {
        claim.claim_id: claim for claim in result.get("claims", [])
    }
    analysis = result.get("analysis")
    for index, finding in enumerate(analysis.findings if analysis else []):
        claim_key = f"claim-{index + 1}"
        claim = ResearchClaim(
            task_id=task.id,
            claim_key=claim_key,
            text=finding.text,
            claim_type=finding.claim_type,
        )
        db.add(claim)
        db.flush()
        for provider_source_id in finding.evidence_ids:
            evidence = evidence_by_provider_id.get(provider_source_id)
            if evidence is not None:
                db.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id))
        verification = verification_by_key.get(claim_key)
        if verification is not None:
            db.add(
                ClaimVerification(
                    claim_id=claim.id,
                    status=ClaimVerificationStatus(verification.status),
                    explanation=verification.explanation,
                )
            )

    report_draft = result["report"]
    report_record = ResearchReportRecord(
        task_id=task.id,
        review_status=ReviewStatus.PENDING,
        current_version=1,
    )
    db.add(report_record)
    db.flush()
    db.add(
        ReportVersion(
            report_id=report_record.id,
            version=1,
            executive_summary=report_draft.executive_summary,
            sections=[
                section.model_dump(mode="json") for section in report_draft.sections
            ],
            methodology=report_draft.methodology,
            limitations=report_draft.limitations,
            markdown=render_report_markdown(report_draft, source_by_provider_id),
            verification_status=ReportVerificationStatus.COMPLETED,
            verification_results=[
                {
                    "claim_id": claim.claim_id,
                    "status": claim.status,
                    "explanation": claim.explanation,
                }
                for claim in result.get("claims", [])
            ],
        )
    )
    task.status = ResearchTaskStatus.WAITING_REVIEW
    task.current_stage = "human_review"
    task.completed_at = datetime.now(UTC)
    task.lease_expires_at = None
    task.worker_id = None
    _event(db, task.id, "task.awaiting_review", stage="human_review")
    db.commit()


def run_task_once(
    session_factory: sessionmaker[Session],
    checkpointer,
    worker_id: str,
) -> bool:
    with session_factory() as db:
        task = db.scalar(
            select(ResearchTask)
            .where(ResearchTask.status == ResearchTaskStatus.QUEUED)
            .order_by(ResearchTask.created_at, ResearchTask.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if task is None:
            return False
        task.status = ResearchTaskStatus.RUNNING
        task.worker_id = worker_id
        task.lease_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        task.started_at = task.started_at or datetime.now(UTC)
        task.attempt_count += 1
        _event(db, task.id, "task.started", payload={"attempt": task.attempt_count})
        db.commit()
        task_id = task.id

    def persist_stage(stage: str, outcome: str, payload: dict) -> None:
        with session_factory() as event_db:
            current_task = event_db.get(ResearchTask, task_id)
            if current_task is None:
                raise RuntimeError("Research task no longer exists.")
            if current_task.cancellation_requested:
                current_task.status = ResearchTaskStatus.CANCELLED
                current_task.completed_at = datetime.now(UTC)
                current_task.worker_id = None
                current_task.lease_expires_at = None
                _event(event_db, task_id, "task.cancelled", stage=current_task.current_stage)
                event_db.commit()
                raise TaskCancelled()
            if outcome == "started":
                current_task.current_stage = stage
            current_task.lease_expires_at = datetime.now(UTC) + timedelta(minutes=10)
            _event(
                event_db,
                task_id,
                f"agent.{outcome}",
                stage=stage,
                agent_name=stage,
                payload=payload,
            )
            event_db.commit()

    with session_factory() as db:
        task = db.get(ResearchTask, task_id)
        if task is None:
            logger.warning(
                "research.task.disappeared_before_execution",
                extra={"task_id": str(task_id)},
            )
            return True
        brief = db.get(ResearchBrief, task.brief_id)
        project = db.get(ResearchProject, task.project_id)
        if brief is None or project is None or project.owner_id != task.owner_id:
            task.status = ResearchTaskStatus.FAILED
            task.safe_error_code = "research_input_unavailable"
            task.completed_at = datetime.now(UTC)
            task.worker_id = None
            task.lease_expires_at = None
            _event(db, task.id, "task.failed", payload={"code": task.safe_error_code})
            db.commit()
            return True
        initial_state = {
            "research_question": brief.research_question,
            "objectives": brief.objectives,
            "scope": brief.scope,
            "source_preferences": brief.source_preferences,
            "recency_days": brief.recency_days,
            "output_language": brief.output_language,
            "local_sources": retrieve_project_evidence(
                db,
                project.id,
                " ".join(
                    [
                        brief.research_question,
                        *brief.objectives,
                        brief.scope or "",
                    ]
                ),
            ),
        }

    graph = build_research_graph(event_sink=persist_stage, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": str(task_id)}}
    try:
        snapshot = graph.get_state(config)
        if snapshot.values and snapshot.next:
            result = graph.invoke(None, config=config)
        elif snapshot.values.get("report"):
            result = snapshot.values
        else:
            result = graph.invoke(initial_state, config=config)
        with session_factory() as db:
            task = db.get(ResearchTask, task_id)
            if task is None:
                raise RuntimeError("Research task disappeared before results were saved.")
            _persist_result(db, task, result)
    except TaskCancelled:
        logger.info("research.task.cancelled", extra={"task_id": str(task_id)})
    except Exception as error:
        logger.error(
            "research.task.failed task_id=%s stage=%s error_type=%s",
            task_id,
            task.current_stage,
            type(error).__name__,
        )
        with session_factory() as db:
            task = db.get(ResearchTask, task_id)
            if task is not None and task.status == ResearchTaskStatus.RUNNING:
                task.status = ResearchTaskStatus.FAILED
                task.safe_error_code = "research_provider_or_workflow_error"
                task.completed_at = datetime.now(UTC)
                task.worker_id = None
                task.lease_expires_at = None
                _event(
                    db,
                    task_id,
                    "task.failed",
                    stage=task.current_stage,
                    payload={"code": task.safe_error_code},
                )
                db.commit()
    return True


def _recover_interrupted_tasks(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        tasks = db.scalars(
            select(ResearchTask).where(ResearchTask.status == ResearchTaskStatus.RUNNING)
        ).all()
        for task in tasks:
            task.status = ResearchTaskStatus.QUEUED
            task.worker_id = None
            task.lease_expires_at = None
            _event(db, task.id, "task.recovered", stage=task.current_stage)
        running_versions = db.scalars(
            select(ReportVersion).where(
                ReportVersion.verification_status == ReportVerificationStatus.RUNNING
            )
        ).all()
        for version in running_versions:
            version.verification_status = ReportVerificationStatus.PENDING
            report = db.get(ResearchReportRecord, version.report_id)
            if report is not None:
                _event(
                    db,
                    report.task_id,
                    "report.verification.recovered",
                    stage="human_review",
                    payload={"version": version.version},
                )
        db.commit()
        if tasks or running_versions:
            logger.info(
                "research.interrupted_work_recovered",
                extra={
                    "task_count": len(tasks),
                    "report_verification_count": len(running_versions),
                },
            )


def run_report_verification_once(
    session_factory: sessionmaker[Session],
) -> bool:
    with session_factory() as db:
        version = db.scalar(
            select(ReportVersion)
            .where(ReportVersion.verification_status == ReportVerificationStatus.PENDING)
            .order_by(ReportVersion.created_at, ReportVersion.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if version is None:
            return False
        version.verification_status = ReportVerificationStatus.RUNNING
        version_id = version.id
        db.commit()

    try:
        with session_factory() as db:
            version = db.get(ReportVersion, version_id)
            if version is None:
                logger.warning(
                    "research.report_version_missing_for_verification",
                    extra={"report_version_id": str(version_id)},
                )
                return True
            report = db.get(ResearchReportRecord, version.report_id)
            if report is None:
                raise RuntimeError("The revised report record is unavailable.")
            task = db.get(ResearchTask, report.task_id)
            if task is None:
                raise RuntimeError("The revised report task is unavailable.")
            source_records = db.scalars(
                select(ResearchSource)
                .options(selectinload(ResearchSource.passages))
                .where(ResearchSource.task_id == task.id)
                .order_by(ResearchSource.created_at, ResearchSource.id)
            ).all()
            cited_source_ids = {
                source.provider_source_id
                for source in source_records
                if f"[{source.provider_source_id}]" in version.markdown
            }
            candidates = sorted(
                source_records,
                key=lambda source: (
                    source.provider_source_id not in cited_source_ids,
                    source.created_at,
                    str(source.id),
                ),
            )
            evidence = [
                {
                    "evidence_id": str(passage.id),
                    "provider_source_id": source.provider_source_id,
                    "title": source.title,
                    "passage": passage.text[:4_000],
                }
                for source in candidates
                for passage in source.passages[:1]
            ][:40]
            markdown = version.markdown
            task_id = task.id

        results = verify_report_revision(markdown, evidence)
        with session_factory() as db:
            version = db.get(ReportVersion, version_id)
            if version is None or version.verification_status != ReportVerificationStatus.RUNNING:
                return True
            version.verification_results = results
            version.verification_status = ReportVerificationStatus.COMPLETED
            _event(
                db,
                task_id,
                "report.verification.completed",
                stage="human_review",
                payload={"version": version.version, "finding_count": len(results)},
            )
            db.commit()
    except Exception as error:
        logger.error(
            "research.report_revision_verification_failed",
            extra={
                "report_version_id": str(version_id),
                "error_type": type(error).__name__,
            },
        )
        with session_factory() as db:
            version = db.get(ReportVersion, version_id)
            if version is not None and version.verification_status == ReportVerificationStatus.RUNNING:
                version.verification_status = ReportVerificationStatus.FAILED
                report = db.get(ResearchReportRecord, version.report_id)
                if report is not None:
                    _event(
                        db,
                        report.task_id,
                        "report.verification.failed",
                        stage="human_review",
                        payload={"version": version.version},
                    )
                db.commit()
    return True


@contextmanager
def _worker_lock() -> Iterator[None]:
    connection = get_engine().connect()
    acquired = False
    try:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": WORKER_LOCK_ID},
        ).scalar_one()
        if not acquired:
            raise RuntimeError("Another ReportPilot worker already owns the PostgreSQL queue.")
        connection.commit()
        yield
    finally:
        if acquired:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": WORKER_LOCK_ID},
            )
            connection.commit()
        connection.close()


def _checkpointer_connection_string() -> str:
    from app.database import _database_url

    url = make_url(_database_url())
    return url.set(drivername="postgresql").update_query_dict(
        {"sslmode": get_settings().database_sslmode}
    ).render_as_string(hide_password=False)


def run_worker() -> None:
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    session_factory = get_session_factory()
    logger.info("research.worker.starting", extra={"worker_id": worker_id})
    with _worker_lock():
        with PostgresSaver.from_conn_string(_checkpointer_connection_string()) as saver:
            saver.setup()
            _recover_interrupted_tasks(session_factory)
            while True:
                if run_report_verification_once(session_factory):
                    continue
                if not run_task_once(session_factory, saver, worker_id):
                    time.sleep(get_settings().worker_poll_seconds)


if __name__ == "__main__":
    run_worker()
