"""
SigmaFlow Alert Models
======================
Database models for webhooks, alert rules, and alert events.
Multi-tenant support added.
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from sigmaflow.core.models import Project, User, Run, Tenant


class WebhookEventType(str, enum.Enum):
    """Events that can trigger webhooks."""
    # SPC Events
    SPC_OUT_OF_CONTROL = "spc.out_of_control"
    SPC_RULE_VIOLATION = "spc.rule_violation"
    SPC_TREND_DETECTED = "spc.trend_detected"
    SPC_SHIFT_DETECTED = "spc.shift_detected"
    
    # Capability Events
    CAPABILITY_BELOW_THRESHOLD = "capability.below_threshold"
    CAPABILITY_DPMO_EXCEEDED = "capability.dpmo_exceeded"
    
    # Run Events
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    
    # Insight Events
    INSIGHT_CRITICAL = "insight.critical"
    INSIGHT_WARNING = "insight.warning"
    
    # Action Item Events
    ACTION_DUE_SOON = "action.due_soon"
    ACTION_OVERDUE = "action.overdue"
    ACTION_COMPLETED = "action.completed"
    
    # Custom
    CUSTOM = "custom"


class WebhookStatus(str, enum.Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Webhook(Base):
    """Webhook endpoint configuration."""
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # HMAC secret
    events: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    headers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[WebhookStatus] = mapped_column(
        Enum(WebhookStatus), default=WebhookStatus.PENDING
    )
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship()
    created_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_webhooks_tenant_project_active", "tenant_id", "project_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Webhook {self.name} project={self.project_id} tenant={self.tenant_id} events={self.events}>"


class AlertRule(Base):
    """Alert rule configuration for automatic notifications."""
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[WebhookEventType] = mapped_column(
        Enum(WebhookEventType), nullable=False
    )
    condition_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), default=AlertSeverity.WARNING
    )
    webhook_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # UUIDs
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)  # Prevent spam
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship()
    created_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_alert_rules_tenant_project_active", "tenant_id", "project_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.name} event={self.event_type.value} severity={self.severity.value}>"


class AlertEvent(Base):
    """Record of an alert being triggered."""
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True
    )
    event_type: Mapped[WebhookEventType] = mapped_column(
        Enum(WebhookEventType), nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), default=AlertSeverity.WARNING
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    webhook_deliveries: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    project: Mapped["Project"] = relationship()
    rule: Mapped[Optional["AlertRule"]] = relationship()
    run: Mapped[Optional["Run"]] = relationship()
    acknowledged_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_alert_events_tenant_project_created", "tenant_id", "project_id", "created_at"),
        Index("ix_alert_events_tenant_severity", "tenant_id", "severity"),
        Index("ix_alert_events_tenant_acknowledged", "tenant_id", "acknowledged"),
    )

    def __repr__(self) -> str:
        return f"<AlertEvent {self.event_type.value} severity={self.severity.value} project={self.project_id} tenant={self.tenant_id}>"


class WebhookDelivery(Base):
    """Record of a webhook delivery attempt."""
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=False
    )
    alert_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_events.id"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(
        Enum(WebhookStatus), default=WebhookStatus.PENDING
    )
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    webhook: Mapped["Webhook"] = relationship()
    alert_event: Mapped[Optional["AlertEvent"]] = relationship()

    __table_args__ = (
        Index("ix_webhook_deliveries_tenant_webhook_started", "tenant_id", "webhook_id", "started_at"),
        Index("ix_webhook_deliveries_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery webhook={self.webhook_id} status={self.status.value} attempt={self.attempt}>"
