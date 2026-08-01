"""
SigmaFlow Alerts API Routes
===========================
REST endpoints for managing webhooks, alert rules, and alert events.
Multi-tenant with RBAC authorization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigmaflow.core.database import get_async_session
from sigmaflow.core.models import Project, User, Tenant
from sigmaflow.alerts.models import (
    Webhook,
    WebhookEventType,
    WebhookStatus,
    AlertRule,
    AlertSeverity,
    AlertEvent,
    WebhookDelivery,
)
from sigmaflow.auth import (
    get_current_user_with_tenant,
    check_project_access,
    check_tenant_access,
    Permission,
    has_permission,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ── Pydantic Models ──────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    name: str = Field(..., max_length=100)
    url: HttpUrl
    secret: Optional[str] = None
    events: list[WebhookEventType] = Field(default_factory=list)
    headers: dict = Field(default_factory=dict)
    retry_count: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    events: Optional[list[WebhookEventType]] = None
    headers: Optional[dict] = None
    is_active: Optional[bool] = None
    retry_count: Optional[int] = Field(None, ge=1, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=60)


class WebhookResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    name: str
    url: str
    events: list[str]
    headers: dict
    is_active: bool
    retry_count: int
    timeout_seconds: int
    last_status: WebhookStatus
    last_triggered_at: Optional[datetime]
    failure_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertRuleCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    event_type: WebhookEventType
    condition_json: dict = Field(default_factory=dict)
    severity: AlertSeverity = AlertSeverity.WARNING
    webhook_ids: list[UUID] = Field(default_factory=list)
    cooldown_minutes: int = Field(default=60, ge=0)


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    condition_json: Optional[dict] = None
    severity: Optional[AlertSeverity] = None
    webhook_ids: Optional[list[UUID]] = None
    is_active: Optional[bool] = None
    cooldown_minutes: Optional[int] = Field(None, ge=0)


class AlertRuleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    event_type: WebhookEventType
    condition_json: dict
    severity: AlertSeverity
    webhook_ids: list
    is_active: bool
    cooldown_minutes: int
    last_triggered_at: Optional[datetime]
    trigger_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    rule_id: Optional[UUID]
    run_id: Optional[UUID]
    event_type: WebhookEventType
    severity: AlertSeverity
    title: str
    message: str
    data_json: dict
    webhook_deliveries: list
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    webhook_id: UUID
    alert_event_id: Optional[UUID]
    url: str
    status: WebhookStatus
    response_status: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    attempt: int
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]

    class Config:
        from_attributes = True


class TriggerTestRequest(BaseModel):
    event_type: WebhookEventType
    severity: AlertSeverity = AlertSeverity.INFO
    title: str
    message: str
    data: dict = Field(default_factory=dict)


# ── Webhook Endpoints ────────────────────────────────────────────────────────


@router.post("/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    project_id: UUID,
    webhook: WebhookCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new webhook for a project."""
    project = await check_project_access(str(project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.WEBHOOK_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions for webhooks")

    new_webhook = Webhook(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        name=webhook.name,
        url=str(webhook.url),
        secret=webhook.secret,
        events=[e.value for e in webhook.events],
        headers=webhook.headers,
        retry_count=webhook.retry_count,
        timeout_seconds=webhook.timeout_seconds,
    )
    session.add(new_webhook)
    await session.commit()
    await session.refresh(new_webhook)
    return new_webhook


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    project_id: UUID,
    is_active: Optional[bool] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List all webhooks for a project."""
    await check_project_access(str(project_id), current_user, session, Permission.PROJECT_READ)

    query = select(Webhook).filter(
        Webhook.tenant_id == current_user.tenant_id,
        Webhook.project_id == project_id
    )
    if is_active is not None:
        query = query.filter(Webhook.is_active == is_active)
    query = query.order_by(Webhook.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific webhook."""
    result = await session.execute(
        select(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant_id == current_user.tenant_id
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await check_project_access(str(webhook.project_id), current_user, session, Permission.PROJECT_READ)
    return webhook


@router.patch("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    webhook_update: WebhookUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update a webhook."""
    result = await session.execute(
        select(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant_id == current_user.tenant_id
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await check_project_access(str(webhook.project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.WEBHOOK_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    update_data = webhook_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "url" and value:
            value = str(value)
        if key == "events" and value:
            value = [e.value for e in value]
        setattr(webhook, key, value)

    await session.commit()
    await session.refresh(webhook)
    return webhook


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Delete a webhook."""
    result = await session.execute(
        select(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant_id == current_user.tenant_id
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await check_project_access(str(webhook.project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.WEBHOOK_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    await session.delete(webhook)
    await session.commit()


@router.post("/webhooks/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: UUID,
    test_request: TriggerTestRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Send a test payload to a webhook."""
    result = await session.execute(
        select(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant_id == current_user.tenant_id
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await check_project_access(str(webhook.project_id), current_user, session, Permission.PROJECT_READ)

    from sigmaflow.alerts.service import WebhookDispatcher
    dispatcher = WebhookDispatcher(session)

    payload = {
        "event_type": test_request.event_type.value,
        "severity": test_request.severity.value,
        "title": test_request.title,
        "message": test_request.message,
        "project_id": str(webhook.project_id),
        "tenant_id": str(current_user.tenant_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": test_request.data,
        "test": True,
    }

    delivery = await dispatcher.deliver(webhook, payload)
    return {
        "success": delivery.status == WebhookStatus.DELIVERED,
        "delivery_id": str(delivery.id),
        "status": delivery.status.value,
        "response_status": delivery.response_status,
        "error": delivery.error_message,
    }


# ── Alert Rule Endpoints ─────────────────────────────────────────────────────


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    project_id: UUID,
    rule: AlertRuleCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new alert rule."""
    project = await check_project_access(str(project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.ALERT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions for alert rules")

    # Verify webhooks exist and belong to tenant
    if rule.webhook_ids:
        result = await session.execute(
            select(Webhook).filter(
                Webhook.id.in_(rule.webhook_ids),
                Webhook.tenant_id == current_user.tenant_id
            )
        )
        found = result.scalars().all()
        if len(found) != len(rule.webhook_ids):
            raise HTTPException(status_code=400, detail="One or more webhooks not found")

    new_rule = AlertRule(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        name=rule.name,
        description=rule.description,
        event_type=rule.event_type,
        condition_json=rule.condition_json,
        severity=rule.severity,
        webhook_ids=[str(wid) for wid in rule.webhook_ids],
        cooldown_minutes=rule.cooldown_minutes,
    )
    session.add(new_rule)
    await session.commit()
    await session.refresh(new_rule)
    return new_rule


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    project_id: UUID,
    is_active: Optional[bool] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List all alert rules for a project."""
    await check_project_access(str(project_id), current_user, session, Permission.PROJECT_READ)

    query = select(AlertRule).filter(
        AlertRule.tenant_id == current_user.tenant_id,
        AlertRule.project_id == project_id
    )
    if is_active is not None:
        query = query.filter(AlertRule.is_active == is_active)
    query = query.order_by(AlertRule.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific alert rule."""
    result = await session.execute(
        select(AlertRule).filter(
            AlertRule.id == rule_id,
            AlertRule.tenant_id == current_user.tenant_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await check_project_access(str(rule.project_id), current_user, session, Permission.PROJECT_READ)
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: UUID,
    rule_update: AlertRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update an alert rule."""
    result = await session.execute(
        select(AlertRule).filter(
            AlertRule.id == rule_id,
            AlertRule.tenant_id == current_user.tenant_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await check_project_access(str(rule.project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.ALERT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    update_data = rule_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "webhook_ids" and value is not None:
            # Verify webhooks exist
            result = await session.execute(
                select(Webhook).filter(
                    Webhook.id.in_(value),
                    Webhook.tenant_id == current_user.tenant_id
                )
            )
            found = result.scalars().all()
            if len(found) != len(value):
                raise HTTPException(status_code=400, detail="One or more webhooks not found")
            value = [str(wid) for wid in value]
        setattr(rule, key, value)

    await session.commit()
    await session.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Delete an alert rule."""
    result = await session.execute(
        select(AlertRule).filter(
            AlertRule.id == rule_id,
            AlertRule.tenant_id == current_user.tenant_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await check_project_access(str(rule.project_id), current_user, session, Permission.PROJECT_WRITE)
    if not has_permission(current_user.role, Permission.ALERT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    await session.delete(rule)
    await session.commit()


# ── Alert Event Endpoints ────────────────────────────────────────────────────


@router.get("/events", response_model=list[AlertEventResponse])
async def list_alert_events(
    project_id: UUID,
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List alert events for a project."""
    await check_project_access(str(project_id), current_user, session, Permission.PROJECT_READ)

    query = select(AlertEvent).filter(
        AlertEvent.tenant_id == current_user.tenant_id,
        AlertEvent.project_id == project_id
    )
    if severity:
        query = query.filter(AlertEvent.severity == severity)
    if acknowledged is not None:
        query = query.filter(AlertEvent.acknowledged == acknowledged)
    query = query.order_by(AlertEvent.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/events/{event_id}", response_model=AlertEventResponse)
async def get_alert_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific alert event."""
    result = await session.execute(
        select(AlertEvent).filter(
            AlertEvent.id == event_id,
            AlertEvent.tenant_id == current_user.tenant_id
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Alert event not found")

    await check_project_access(str(event.project_id), current_user, session, Permission.PROJECT_READ)
    return event


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_alert_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Acknowledge an alert event."""
    result = await session.execute(
        select(AlertEvent).filter(
            AlertEvent.id == event_id,
            AlertEvent.tenant_id == current_user.tenant_id
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Alert event not found")

    await check_project_access(str(event.project_id), current_user, session, Permission.PROJECT_READ)

    event.acknowledged = True
    event.acknowledged_by_id = current_user.id
    event.acknowledged_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(event)
    return event


@router.get("/events/{event_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def get_alert_deliveries(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get webhook delivery history for an alert event."""
    result = await session.execute(
        select(AlertEvent).filter(
            AlertEvent.id == event_id,
            AlertEvent.tenant_id == current_user.tenant_id
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Alert event not found")

    await check_project_access(str(event.project_id), current_user, session, Permission.PROJECT_READ)

    result = await session.execute(
        select(WebhookDelivery)
        .filter(
            WebhookDelivery.tenant_id == current_user.tenant_id,
            WebhookDelivery.alert_event_id == event_id
        )
        .order_by(WebhookDelivery.started_at.desc())
    )
    return result.scalars().all()


# ── Webhook Delivery History ─────────────────────────────────────────────────


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    webhook_id: UUID,
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get delivery history for a webhook."""
    result = await session.execute(
        select(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant_id == current_user.tenant_id
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await check_project_access(str(webhook.project_id), current_user, session, Permission.PROJECT_READ)

    result = await session.execute(
        select(WebhookDelivery)
        .filter(
            WebhookDelivery.tenant_id == current_user.tenant_id,
            WebhookDelivery.webhook_id == webhook_id
        )
        .order_by(WebhookDelivery.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ── Event Types Reference ────────────────────────────────────────────────────


@router.get("/event-types", response_model=list[dict])
async def list_event_types():
    """List all available webhook event types with descriptions."""
    return [
        {"value": e.value, "description": _get_event_description(e)}
        for e in WebhookEventType
    ]


def _get_event_description(event: WebhookEventType) -> str:
    descriptions = {
        WebhookEventType.SPC_OUT_OF_CONTROL: "Process goes out of statistical control (Western Electric rules)",
        WebhookEventType.SPC_RULE_VIOLATION: "Specific SPC rule violation detected",
        WebhookEventType.SPC_TREND_DETECTED: "Trend pattern detected in control chart",
        WebhookEventType.SPC_SHIFT_DETECTED: "Mean shift detected in control chart",
        WebhookEventType.CAPABILITY_BELOW_THRESHOLD: "Process capability (Cpk) falls below threshold",
        WebhookEventType.CAPABILITY_DPMO_EXCEEDED: "DPMO exceeds configured threshold",
        WebhookEventType.RUN_STARTED: "DMAIC pipeline run started",
        WebhookEventType.RUN_COMPLETED: "DMAIC pipeline run completed successfully",
        WebhookEventType.RUN_FAILED: "DMAIC pipeline run failed",
        WebhookEventType.INSIGHT_CRITICAL: "Critical severity insight generated",
        WebhookEventType.INSIGHT_WARNING: "Warning severity insight generated",
        WebhookEventType.ACTION_DUE_SOON: "Action item due within 24 hours",
        WebhookEventType.ACTION_OVERDUE: "Action item past due date",
        WebhookEventType.ACTION_COMPLETED: "Action item marked as completed",
        WebhookEventType.CUSTOM: "Custom event type",
    }
    return descriptions.get(event, "No description available")
