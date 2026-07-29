"""
SigmaFlow Core Models
=====================
SQLAlchemy 2.0 models for enterprise persistence.

Entities:
- Tenant: Multi-tenant organization boundary
- Plant: Physical location (factory, site) within a tenant
- Project: DMAIC project within a plant
- User: Platform user with role-based access
- Dataset: Versioned data artifact with lineage
- Run: Single execution of the DMAIC pipeline
- PhaseResult: Results per DMAIC phase
- Insight: Structured insight with severity
- ActionItem: CAPA / improvement action with tracking
- ScheduledRun: Recurring pipeline schedules
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from sigmaflow.core.models import (
        Tenant,
        Plant,
        Project,
        User,
        Dataset,
        Run,
        PhaseResult,
        Insight,
        ActionItem,
        ScheduledRun,
    )


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Tenant(Base):
    """Multi-tenant organization boundary - top-level isolation unit."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)  # for subdomain routing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    plants: Mapped[list["Plant"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    projects: Mapped[list["Project"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.code}: {self.name}>"


class UserRole(str, enum.Enum):
    """User roles with increasing permissions."""
    VIEWER = "viewer"
    GREEN_BELT = "green_belt"
    BLACK_BELT = "black_belt"
    MASTER_BLACK_BELT = "master_black_belt"
    ADMIN = "admin"


class RunStatus(str, enum.Enum):
    """Pipeline run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class PhaseName(str, enum.Enum):
    """DMAIC phase names."""
    DEFINE = "define"
    MEASURE = "measure"
    ANALYZE = "analyze"
    IMPROVE = "improve"
    CONTROL = "control"


class InsightSeverity(str, enum.Enum):
    """Insight severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActionStatus(str, enum.Enum):
    """Action item status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    VERIFIED = "verified"
    CANCELLED = "cancelled"


class Plant(Base):
    """Physical plant / site / factory within a tenant."""
    __tablename__ = "plants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="BR")
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="plants")
    projects: Mapped[list["Project"]] = relationship(
        back_populates="plant", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(back_populates="plant")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_plant_tenant_code"),
        Index("ix_plants_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Plant {self.code}: {self.name} (tenant={self.tenant_id})>"


class User(Base):
    """Platform user with role-based access."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.VIEWER, nullable=False
    )
    plant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    plant: Mapped[Optional["Plant"]] = relationship(back_populates="users")
    owned_projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", foreign_keys="Project.owner_id"
    )
    assigned_actions: Mapped[list["ActionItem"]] = relationship(
        back_populates="assignee", foreign_keys="ActionItem.assignee_id"
    )

    __table_args__ = (
        Index("ix_users_tenant_role", "tenant_id", "role"),
        Index("ix_users_tenant_plant", "tenant_id", "plant_id"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value}) tenant={self.tenant_id}>"


class Project(Base):
    """DMAIC project within a plant and tenant."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_in: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_out: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_metric: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    baseline_value: Mapped[Optional[float]] = mapped_column(nullable=True)
    target_value: Mapped[Optional[float]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="projects")
    plant: Mapped["Plant"] = relationship(back_populates="projects")
    owner: Mapped["User"] = relationship(back_populates="owned_projects", foreign_keys=[owner_id])
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_project_tenant_code"),
        Index("ix_projects_tenant_plant_status", "tenant_id", "plant_id", "status"),
        Index("ix_projects_tenant_owner", "tenant_id", "owner_id"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.code}: {self.name} (tenant={self.tenant_id})>"


class Dataset(Base):
    """Versioned dataset with lineage tracking."""
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # csv, excel, sql, api, mqtt, opcua
    source_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA256
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    schema_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    detection_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analysis_plan_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship(back_populates="datasets")
    created_by: Mapped["User"] = relationship()
    runs: Mapped[list["Run"]] = relationship(back_populates="dataset")

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "name", "version", name="uq_dataset_tenant_project_name_version"),
        Index("ix_datasets_tenant_project", "tenant_id", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<Dataset {self.name} v{self.version} (project={self.project_id}, tenant={self.tenant_id})>"


class Run(Base):
    """Single execution of the DMAIC pipeline."""
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.PENDING, nullable=False
    )
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    insights_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_insights_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_insights_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship(back_populates="runs")
    dataset: Mapped[Optional["Dataset"]] = relationship(back_populates="runs")
    phase_results: Mapped[list["PhaseResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="PhaseResult.phase_order"
    )
    insights: Mapped[list["Insight"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    created_by: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "run_number", name="uq_run_tenant_project_number"),
        Index("ix_runs_tenant_project_status", "tenant_id", "project_id", "status"),
        Index("ix_runs_tenant_dataset", "tenant_id", "dataset_id"),
    )

    def __repr__(self) -> str:
        return f"<Run #{self.run_number} project={self.project_id} tenant={self.tenant_id} status={self.status.value}>"


class PhaseResult(Base):
    """Results for a single DMAIC phase within a run."""
    __tablename__ = "phase_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False
    )
    phase: Mapped[PhaseName] = mapped_column(Enum(PhaseName), nullable=False)
    phase_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.PENDING, nullable=False
    )
    analyses_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    insights_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    plots: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    run: Mapped["Run"] = relationship(back_populates="phase_results")

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "phase", name="uq_phase_result_tenant_run_phase"),
        Index("ix_phase_results_tenant_run", "tenant_id", "run_id"),
    )

    def __repr__(self) -> str:
        return f"<PhaseResult run={self.run_id} phase={self.phase.value} status={self.status.value}>"


class Insight(Base):
    """Structured insight generated by the rules engine."""
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False
    )
    phase: Mapped[Optional[PhaseName]] = mapped_column(Enum(PhaseName), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meaning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[InsightSeverity] = mapped_column(
        Enum(InsightSeverity), default=InsightSeverity.INFO, nullable=False
    )
    data_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    run: Mapped["Run"] = relationship(back_populates="insights")

    __table_args__ = (
        Index("ix_insights_tenant_run_severity", "tenant_id", "run_id", "severity"),
        Index("ix_insights_tenant_rule", "tenant_id", "rule_id"),
    )

    def __repr__(self) -> str:
        return f"<Insight run={self.run_id} rule={self.rule_id} severity={self.severity.value}>"


class ActionItem(Base):
    """CAPA / improvement action with tracking."""
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True
    )
    insight_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insights.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=True)  # process, equipment, method, material, environment, people
    priority: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus), default=ActionStatus.OPEN, nullable=False
    )
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    evidence_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effectiveness_check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # post-implementation metrics
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship(back_populates="action_items")
    run: Mapped[Optional["Run"]] = relationship()
    insight: Mapped[Optional["Insight"]] = relationship()
    assignee: Mapped[Optional["User"]] = relationship(back_populates="assigned_actions", foreign_keys=[assignee_id])
    verified_by: Mapped[Optional["User"]] = relationship(foreign_keys=[verified_by_id])

    __table_args__ = (
        Index("ix_action_items_tenant_project_status", "tenant_id", "project_id", "status"),
        Index("ix_action_items_tenant_assignee", "tenant_id", "assignee_id"),
        Index("ix_action_items_tenant_due_date", "tenant_id", "due_date"),
    )

    def __repr__(self) -> str:
        return f"<ActionItem {self.title} [{self.status.value}] project={self.project_id} tenant={self.tenant_id}>"


class ScheduledRun(Base):
    """Scheduled recurring pipeline runs."""
    __tablename__ = "scheduled_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    dataset_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    run_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship()

    __table_args__ = (
        Index("ix_scheduled_runs_tenant_project_enabled", "tenant_id", "project_id", "enabled"),
        Index("ix_scheduled_runs_tenant_next_run", "tenant_id", "next_run_at"),
    )

    def __repr__(self) -> str:
        return f"<ScheduledRun {self.cron_expression} project={self.project_id} tenant={self.tenant_id} enabled={self.enabled}>"