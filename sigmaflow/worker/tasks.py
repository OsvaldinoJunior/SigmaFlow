"""
Celery Tasks for SigmaFlow
===========================
Background tasks for running DMAIC pipelines, scheduled runs, and other async operations.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from celery import shared_task
from celery.utils.log import get_task_logger

from sigmaflow.core.config import get_settings
from sigmaflow.core.database import get_sync_session, get_async_session
from sigmaflow.core.models import (
    Dataset,
    Project,
    Run,
    PhaseResult,
    Insight,
    PhaseName,
    RunStatus,
    InsightSeverity,
    ScheduledRun,
)

logger = get_task_logger(__name__)
settings = get_settings()


def _create_run_record(
    session,
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    config_json: dict,
    triggered_by: str = "scheduled",
    triggered_by_user_id: Optional[uuid.UUID] = None,
) -> Run:
    """Create a new Run record."""
    # Get next run number
    last_run = session.query(Run).filter(Run.project_id == project_id).order_by(Run.run_number.desc()).first()
    run_number = (last_run.run_number + 1) if last_run else 1

    run = Run(
        project_id=project_id,
        dataset_id=dataset_id,
        run_number=run_number,
        status=RunStatus.PENDING,
        config_json=config_json,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )
    session.add(run)
    session.flush()
    return run


def _update_run_status(session, run_id: uuid.UUID, status: RunStatus, **kwargs):
    """Update run status and optional fields."""
    run = session.query(Run).filter(Run.id == run_id).first()
    if run:
        run.status = status
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        session.flush()


def _create_phase_result(session, run_id: uuid.UUID, phase: PhaseName, phase_order: int, status: RunStatus = RunStatus.PENDING) -> PhaseResult:
    """Create a PhaseResult record."""
    phase_result = PhaseResult(
        run_id=run_id,
        phase=phase,
        phase_order=phase_order,
        status=status,
        analyses_json={},
        insights_json=[],
        plots=[],
    )
    session.add(phase_result)
    session.flush()
    return phase_result


def _update_phase_result(session, phase_result_id: uuid.UUID, status: RunStatus, **kwargs):
    """Update phase result."""
    pr = session.query(PhaseResult).filter(PhaseResult.id == phase_result_id).first()
    if pr:
        pr.status = status
        for key, value in kwargs.items():
            if hasattr(pr, key):
                setattr(pr, key, value)
        session.flush()


def _persist_insights(session, run_id: uuid.UUID, insights: list[dict], phase: Optional[PhaseName] = None):
    """Persist insights to database."""
    for ins in insights:
        insight = Insight(
            run_id=run_id,
            phase=phase,
            rule_id=ins.get("rule", "unknown"),
            description=ins.get("description", ""),
            meaning=ins.get("meaning"),
            recommendation=ins.get("recommendation"),
            severity=InsightSeverity(ins.get("severity", "info")),
            data_json=ins.get("data", {}),
        )
        session.add(insight)
    session.flush()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_pipeline(
    self,
    project_code: str,
    dataset_name: Optional[str] = None,
    run_config: Optional[dict] = None,
    triggered_by: str = "api",
    triggered_by_user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run the full DMAIC pipeline for a project.

    Args:
        project_code: Project code (e.g., "SF-001")
        dataset_name: Specific dataset name (optional, uses latest if not provided)
        run_config: Optional configuration overrides
        triggered_by: Source of trigger (api, scheduled, manual)
        triggered_by_user_id: User ID who triggered the run

    Returns:
        Dict with run_id, status, and summary
    """
    run_id = None
    try:
        with get_sync_session() as session:
            # Get project
            project = session.query(Project).filter(Project.code == project_code).first()
            if not project:
                return {"success": False, "error": f"Project not found: {project_code}"}

            # Get dataset
            if dataset_name:
                dataset = session.query(Dataset).filter(
                    Dataset.project_id == project.id,
                    Dataset.name == dataset_name,
                    Dataset.is_active == True
                ).first()
            else:
                # Use most recent active dataset
                dataset = session.query(Dataset).filter(
                    Dataset.project_id == project.id,
                    Dataset.is_active == True
                ).order_by(Dataset.created_at.desc()).first()

            if not dataset:
                return {"success": False, "error": "No active dataset found for project"}

            # Create run record
            config = run_config or {}
            run = _create_run_record(
                session,
                project.id,
                dataset.id,
                config,
                triggered_by,
                uuid.UUID(triggered_by_user_id) if triggered_by_user_id else None,
            )
            run_id = run.id
            session.commit()

        # Update status to RUNNING
        with get_sync_session() as session:
            _update_run_status(session, run_id, RunStatus.RUNNING, started_at=datetime.now(timezone.utc))
            session.commit()

        # Import and run the pipeline
        # This is where we'd integrate with the existing Engine
        from sigmaflow.core.engine import Engine
        from sigmaflow.core.dataset_registry import DatasetRegistry

        # Prepare input directory
        import tempfile
        import shutil
        from pathlib import Path
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            input_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)

            # Load dataset and save to temp CSV
            if dataset.source_type in ("csv", "excel") and dataset.file_path:
                src = Path(dataset.file_path)
                if src.exists():
                    if src.suffix == ".csv":
                        df = pd.read_csv(src)
                    else:
                        df = pd.read_excel(src)
                    df.to_csv(input_dir / f"{dataset.name}.csv", index=False)
                else:
                    # Try to reconstruct from sample data
                    if dataset.sample_data:
                        df = pd.DataFrame(dataset.sample_data)
                        df.to_csv(input_dir / f"{dataset.name}.csv", index=False)

            # Run pipeline
            registry = DatasetRegistry().discover()
            engine = Engine(
                input_dir=input_dir,
                output_dir=output_dir,
                registry=registry,
                run_dashboard=False,
            )
            results = engine.run()

        # Persist results
        with get_sync_session() as session:
            if results:
                result = results[0]

                # Update run
                run = session.query(Run).filter(Run.id == run_id).first()
                if run:
                    run.status = RunStatus.COMPLETED
                    run.completed_at = datetime.now(timezone.utc)
                    run.elapsed_seconds = result.get("elapsed_s", 0)
                    run.summary_json = result.get("summary", {})
                    run.insights_count = len(result.get("structured_insights", []))
                    critical_count = sum(1 for i in result.get("structured_insights", []) if i.get("severity") == "critical")
                    warning_count = sum(1 for i in result.get("structured_insights", []) if i.get("severity") == "warning")
                    run.critical_insights_count = critical_count
                    run.warning_insights_count = warning_count

                    # Create phase results
                    phases = [
                        (PhaseName.DEFINE, 1, result.get("analysis", {}).get("define", {})),
                        (PhaseName.MEASURE, 2, result.get("analysis", {}).get("measure", {})),
                        (PhaseName.ANALYZE, 3, result.get("analysis", {}).get("analyze", {})),
                        (PhaseName.IMPROVE, 4, result.get("analysis", {}).get("improve", {})),
                        (PhaseName.CONTROL, 5, result.get("analysis", {}).get("control", {})),
                    ]

                    for phase, order, phase_data in phases:
                        pr = _create_phase_result(session, run_id, phase, order, RunStatus.COMPLETED)
                        if phase_data:
                            pr.analyses_json = phase_data
                        pr.started_at = datetime.now(timezone.utc)
                        pr.completed_at = datetime.now(timezone.utc)

                    # Persist insights
                    _persist_insights(session, run_id, result.get("structured_insights", []))

                    # Copy output files to permanent storage
                    import shutil
                    from sigmaflow.core.config import get_settings
                    settings = get_settings()
                    storage_root = Path(settings.storage_local_root) / "runs" / str(run_id)
                    storage_root.mkdir(parents=True, exist_ok=True)

                    if output_dir.exists():
                        shutil.copytree(output_dir, storage_root, dirs_exist_ok=True)

                    run.reports_path = str(storage_root / "reports")
                    run.dashboard_path = str(storage_root / "dashboard")
                    run.insights_json_path = str(storage_root / "insights.json")
                    run.figures_path = str(storage_root / "figures")

                    # Save insights.json
                    import json
                    (storage_root / "insights.json").write_text(json.dumps(results, indent=2, default=str))

                    session.commit()

        # Evaluate alerts for completed run
        try:
            with get_sync_session() as session:
                run_obj = session.query(Run).filter(Run.id == run_id).first()
                if run_obj:
                    from sigmaflow.alerts.service import AlertService
                    import asyncio
                    
                    async def evaluate_alerts():
                        async with get_async_session() as async_session:
                            service = AlertService(async_session)
                            await service.evaluate_run_completion(run_obj)
                    
                    asyncio.run(evaluate_alerts())
        except Exception as alert_exc:
            logger.warning(f"Alert evaluation failed for run {run_id}: {alert_exc}")

        logger.info(f"Pipeline completed for project {project_code}, run {run_id}")
        return {
            "success": True,
            "run_id": str(run_id),
            "project_code": project_code,
            "status": "completed",
            "insights_count": len(results[0].get("structured_insights", [])) if results else 0,
        }

    except Exception as exc:
        logger.error(f"Pipeline failed for project {project_code}: {exc}")
        if run_id:
            try:
                with get_sync_session() as session:
                    _update_run_status(
                        session,
                        run_id,
                        RunStatus.FAILED,
                        error_message=str(exc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.commit()
            except Exception:
                pass

        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {"success": False, "run_id": str(run_id) if run_id else None, "error": str(exc)}


@shared_task
def run_scheduled_pipelines() -> dict[str, Any]:
    """
    Check for scheduled pipelines that need to run and queue them.
    This task is run by Celery Beat every minute.
    """
    from croniter import croniter

    now = datetime.now(timezone.utc)
    queued = 0

    with get_sync_session() as session:
        schedules = session.query(ScheduledRun).filter(
            ScheduledRun.enabled == True
        ).all()

        for schedule in schedules:
            # Check if it's time to run
            cron = croniter(schedule.cron_expression, now)
            next_run = cron.get_next(datetime)

            # If next run is within the last minute, queue it
            if schedule.last_run_at is None or schedule.last_run_at < next_run:
                # Get the dataset
                if schedule.dataset_name:
                    dataset = session.query(Dataset).filter(
                        Dataset.project_id == schedule.project_id,
                        Dataset.name == schedule.dataset_name,
                        Dataset.is_active == True
                    ).first()
                else:
                    dataset = session.query(Dataset).filter(
                        Dataset.project_id == schedule.project_id,
                        Dataset.is_active == True
                    ).order_by(Dataset.created_at.desc()).first()

                if dataset:
                    # Queue the pipeline
                    run_pipeline.delay(
                        project_code=schedule.project.code,
                        dataset_name=dataset.name,
                        run_config=schedule.run_config,
                        triggered_by="scheduled",
                    )
                    schedule.last_run_at = now
                    schedule.next_run_at = next_run
                    queued += 1
                else:
                    logger.warning(f"No dataset found for schedule {schedule.id}")

        session.commit()

    return {"success": True, "queued": queued}


@shared_task
def cleanup_old_runs(days: int = 90) -> dict[str, Any]:
    """Clean up old run data (keep last N days)."""
    from datetime import timedelta
    from pathlib import Path

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = 0

    with get_sync_session() as session:
        old_runs = session.query(Run).filter(
            Run.completed_at < cutoff,
            Run.status.in_([RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED])
        ).all()

        for run in old_runs:
            # Delete associated files
            from sigmaflow.core.config import get_settings
            settings = get_settings()
            storage_root = Path(settings.storage_local_root) / "runs" / str(run.id)
            if storage_root.exists():
                import shutil
                shutil.rmtree(storage_root, ignore_errors=True)

            session.delete(run)
            deleted += 1

        session.commit()

    return {"success": True, "deleted_runs": deleted}


@shared_task
def generate_run_report(run_id: str, format: str = "pdf") -> dict[str, Any]:
    """Generate a report for a specific run."""
    try:
        run_uuid = uuid.UUID(run_id)
        with get_sync_session() as session:
            run = session.query(Run).filter(Run.id == run_uuid).first()
            if not run:
                return {"success": False, "error": "Run not found"}

            # Load insights
            insights = session.query(Insight).filter(Insight.run_id == run_uuid).all()
            phase_results = session.query(PhaseResult).filter(PhaseResult.run_id == run_uuid).all()

            # Generate report using existing LaTeX engine
            from sigmaflow.report.latex_engine import LatexEngine

            results = [{
                "name": run.dataset.name if run.dataset else "Unknown",
                "dataset_type": "consolidated",
                "shape": (0, 0),
                "analysis": {},
                "plots": [],
                "insights": [],
                "structured_insights": [i.__dict__ for i in insights],
                "analysis_insights": [],
                "executive_summary": "",
                "recommendations": [],
                "risk_level": "info",
                "risk_label": "BAIXO",
                "risk_color": "corInfo",
                "root_cause": {},
                "elapsed_s": run.elapsed_seconds or 0,
            }]

            output_dir = Path(settings.storage_local_root) / "runs" / run_id / "reports" / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)

            latex_engine = LatexEngine(
                all_results=results,
                output_dir=output_dir,
                organization=run.project.name,
                compile_pdf=(format == "pdf"),
            )
            report_path = latex_engine.generate()

            return {"success": True, "report_path": str(report_path)}

    except Exception as exc:
        logger.error(f"Report generation failed for run {run_id}: {exc}")
        return {"success": False, "error": str(exc)}