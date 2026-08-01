"""
SigmaFlow Alert Service & Webhook Dispatcher
=============================================
Handles alert evaluation, webhook delivery with retries, and HMAC signing.
Multi-tenant support added.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigmaflow.core.database import get_sync_session
from sigmaflow.core.models import Project, Run, Tenant
from sigmaflow.alerts.models import (
    Webhook,
    WebhookEventType,
    WebhookStatus,
    AlertRule,
    AlertSeverity,
    AlertEvent,
    WebhookDelivery,
)

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """Dispatches webhook payloads with retries, HMAC signing, and delivery tracking."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def deliver(
        self,
        webhook: Webhook,
        payload: dict[str, Any],
        alert_event_id: Optional[uuid.UUID] = None,
    ) -> WebhookDelivery:
        """Deliver a webhook payload with retries."""
        delivery = WebhookDelivery(
            tenant_id=webhook.tenant_id,
            webhook_id=webhook.id,
            alert_event_id=alert_event_id,
            url=webhook.url,
            payload_json=payload,
            status=WebhookStatus.PENDING,
            attempt=1,
        )

        if self.session:
            self.session.add(delivery)
            await self.session.flush()

        last_error = None
        for attempt in range(1, webhook.retry_count + 1):
            delivery.attempt = attempt
            delivery.started_at = datetime.now(timezone.utc)
            start_time = time.perf_counter()

            try:
                success = await self._send_webhook(webhook, payload, delivery)
                if success:
                    delivery.status = WebhookStatus.DELIVERED
                    delivery.completed_at = datetime.now(timezone.utc)
                    delivery.duration_ms = int((time.perf_counter() - start_time) * 1000)

                    if self.session:
                        await self.session.flush()

                    # Update webhook last status
                    webhook.last_status = WebhookStatus.DELIVERED
                    webhook.last_triggered_at = datetime.now(timezone.utc)
                    webhook.failure_count = 0

                    logger.info(f"Webhook {webhook.id} delivered successfully on attempt {attempt}")
                    return delivery

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Webhook {webhook.id} attempt {attempt} failed: {e}")

            delivery.status = WebhookStatus.RETRYING
            if self.session:
                await self.session.flush()

            # Exponential backoff: 1s, 2s, 4s, 8s...
            if attempt < webhook.retry_count:
                await self._sleep(2 ** (attempt - 1))

        # All retries failed
        delivery.status = WebhookStatus.FAILED
        delivery.completed_at = datetime.now(timezone.utc)
        delivery.duration_ms = int((time.perf_counter() - start_time) * 1000)
        delivery.error_message = last_error

        if self.session:
            await self.session.flush()

        webhook.last_status = WebhookStatus.FAILED
        webhook.failure_count += 1

        logger.error(f"Webhook {webhook.id} failed after {webhook.retry_count} attempts: {last_error}")
        return delivery

    async def _send_webhook(
        self,
        webhook: Webhook,
        payload: dict[str, Any],
        delivery: WebhookDelivery,
    ) -> bool:
        """Send a single webhook request."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SigmaFlow-Webhooks/1.0",
            **webhook.headers,
        }

        # Add HMAC signature if secret configured
        body = json.dumps(payload, separators=(",", ":"), default=str)
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-SigmaFlow-Signature"] = f"sha256={signature}"

        async with httpx.AsyncClient(timeout=webhook.timeout_seconds) as client:
            response = await client.post(
                webhook.url,
                content=body,
                headers=headers,
            )

        delivery.response_status = response.status_code
        delivery.response_body = response.text[:1000] if response.text else None

        if 200 <= response.status_code < 300:
            return True

        raise httpx.HTTPStatusError(
            f"Webhook returned {response.status_code}",
            request=response.request,
            response=response,
        )

    async def _sleep(self, seconds: float):
        """Async sleep - can be mocked in tests."""
        import asyncio
        await asyncio.sleep(seconds)


class AlertService:
    """Evaluates alert rules and triggers webhooks."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.dispatcher = WebhookDispatcher(session)

    async def evaluate_run_completion(self, run: Run) -> list[AlertEvent]:
        """Evaluate all alert rules for a completed run."""
        alerts_created = []

        # Get active alert rules for this project in the same tenant
        result = await self.session.execute(
            select(AlertRule).filter(
                AlertRule.tenant_id == run.tenant_id,
                AlertRule.project_id == run.project_id,
                AlertRule.is_active == True,
            )
        )
        rules = result.scalars().all()

        for rule in rules:
            # Check cooldown
            if rule.last_triggered_at:
                cooldown_end = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
                if datetime.now(timezone.utc) < cooldown_end:
                    continue

            # Evaluate condition based on event type
            triggered = await self._evaluate_rule(rule, run)
            if triggered:
                alert = await self._create_alert_event(rule, run, triggered)
                alerts_created.append(alert)

                # Dispatch to webhooks
                await self._dispatch_alert(alert, rule.webhook_ids)

                # Update rule trigger time
                rule.last_triggered_at = datetime.now(timezone.utc)
                rule.trigger_count += 1

        if alerts_created:
            await self.session.commit()

        return alerts_created

    async def _evaluate_rule(self, rule: AlertRule, run: Run) -> Optional[dict]:
        """Evaluate if an alert rule condition is met."""
        condition = rule.condition_json or {}

        if rule.event_type == WebhookEventType.RUN_COMPLETED:
            # Always trigger on run completion if no specific condition
            return {"triggered": True, "reason": "Run completed"}

        elif rule.event_type == WebhookEventType.RUN_FAILED:
            if run.status.value == "failed":
                return {"triggered": True, "reason": "Run failed", "error": run.error_message}

        elif rule.event_type == WebhookEventType.INSIGHT_CRITICAL:
            if run.critical_insights_count > 0:
                threshold = condition.get("threshold", 1)
                if run.critical_insights_count >= threshold:
                    return {
                        "triggered": True,
                        "reason": f"{run.critical_insights_count} critical insights",
                        "count": run.critical_insights_count,
                    }

        elif rule.event_type == WebhookEventType.INSIGHT_WARNING:
            if run.warning_insights_count > 0:
                threshold = condition.get("threshold", 1)
                if run.warning_insights_count >= threshold:
                    return {
                        "triggered": True,
                        "reason": f"{run.warning_insights_count} warning insights",
                        "count": run.warning_insights_count,
                    }

        elif rule.event_type == WebhookEventType.SPC_OUT_OF_CONTROL:
            # Check for SPC out-of-control insights in this run
            from sigmaflow.core.models import Insight
            result = await self.session.execute(
                select(Insight).filter(
                    Insight.tenant_id == run.tenant_id,
                    Insight.run_id == run.id,
                    Insight.rule_id.ilike("%spc%"),
                    Insight.severity.in_([AlertSeverity.WARNING, AlertSeverity.CRITICAL]),
                )
            )
            spc_insights = result.scalars().all()
            if spc_insights:
                return {
                    "triggered": True,
                    "reason": f"{len(spc_insights)} SPC violations detected",
                    "insights": [i.description for i in spc_insights],
                }

        elif rule.event_type == WebhookEventType.CAPABILITY_BELOW_THRESHOLD:
            # Check capability insights
            min_cpk = condition.get("min_cpk", 1.33)
            summary = run.summary_json or {}
            capability = summary.get("capability", {})
            cpk = capability.get("Cpk")
            if cpk is not None and cpk < min_cpk:
                return {
                    "triggered": True,
                    "reason": f"Cpk ({cpk:.2f}) below threshold ({min_cpk})",
                    "cpk": cpk,
                    "threshold": min_cpk,
                }

        elif rule.event_type == WebhookEventType.CAPABILITY_DPMO_EXCEEDED:
            max_dpmo = condition.get("max_dpmo", 3400)
            summary = run.summary_json or {}
            capability = summary.get("capability", {})
            dpmo = capability.get("DPMO") or capability.get("dpmo")
            if dpmo is not None and dpmo > max_dpmo:
                return {
                    "triggered": True,
                    "reason": f"DPMO ({dpmo:.0f}) exceeds threshold ({max_dpmo})",
                    "dpmo": dpmo,
                    "threshold": max_dpmo,
                }

        return None

    async def _create_alert_event(
        self,
        rule: AlertRule,
        run: Run,
        evaluation_result: dict,
    ) -> AlertEvent:
        """Create an alert event record."""
        alert = AlertEvent(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            rule_id=rule.id,
            run_id=run.id,
            event_type=rule.event_type,
            severity=rule.severity,
            title=f"Alert: {rule.name}",
            message=evaluation_result.get("reason", "Alert triggered"),
            data_json={
                "run_id": str(run.id),
                "run_number": run.run_number,
                "project_code": run.project.code,
                "evaluation": evaluation_result,
            },
            webhook_deliveries=[],
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def _dispatch_alert(self, alert: AlertEvent, webhook_ids: list) -> None:
        """Dispatch alert to configured webhooks."""
        if not webhook_ids:
            return

        # Get webhooks in the same tenant
        result = await self.session.execute(
            select(Webhook).filter(
                Webhook.tenant_id == alert.tenant_id,
                Webhook.id.in_([uuid.UUID(wid) for wid in webhook_ids]),
                Webhook.is_active == True,
            )
        )
        webhooks = result.scalars().all()

        payload = {
            "event_type": alert.event_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "project_id": str(alert.project_id),
            "tenant_id": str(alert.tenant_id),
            "run_id": str(alert.run_id) if alert.run_id else None,
            "timestamp": alert.created_at.isoformat(),
            "data": alert.data_json,
        }

        deliveries = []
        for webhook in webhooks:
            # Check if webhook subscribes to this event type
            if webhook.events and alert.event_type.value not in webhook.events:
                continue

            delivery = await self.dispatcher.deliver(webhook, payload, alert.id)
            deliveries.append({
                "webhook_id": str(webhook.id),
                "webhook_name": webhook.name,
                "delivery_id": str(delivery.id),
                "status": delivery.status.value,
                "attempt": delivery.attempt,
            })

        # Update alert with delivery results
        alert.webhook_deliveries = deliveries
        await self.session.flush()

    # ── Manual Alert Creation ────────────────────────────────────────────────

    async def create_manual_alert(
        self,
        project_id: uuid.UUID,
        event_type: WebhookEventType,
        severity: AlertSeverity,
        title: str,
        message: str,
        data: Optional[dict] = None,
        run_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> AlertEvent:
        """Create an alert event manually (e.g., from worker tasks)."""
        alert = AlertEvent(
            tenant_id=tenant_id,
            project_id=project_id,
            run_id=run_id,
            event_type=event_type,
            severity=severity,
            title=title,
            message=message,
            data_json=data or {},
            webhook_deliveries=[],
        )
        self.session.add(alert)
        await self.session.flush()

        # Find matching alert rules to get webhooks (in same tenant)
        result = await self.session.execute(
            select(AlertRule).filter(
                AlertRule.tenant_id == tenant_id if tenant_id else True,
                AlertRule.project_id == project_id,
                AlertRule.event_type == event_type,
                AlertRule.is_active == True,
            )
        )
        rules = result.scalars().all()

        # Collect unique webhook IDs
        webhook_ids = []
        for rule in rules:
            webhook_ids.extend(rule.webhook_ids)

        if webhook_ids:
            await self._dispatch_alert(alert, webhook_ids)

        await self.session.commit()
        return alert

    # ── Webhook Management ──────────────────────────────────────────────────

    async def create_webhook(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        url: str,
        events: list[str],
        secret: Optional[str] = None,
        headers: Optional[dict] = None,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> Webhook:
        """Create a new webhook."""
        webhook = Webhook(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            url=url,
            events=events,
            secret=secret,
            headers=headers or {},
            created_by_id=created_by_id,
        )
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def test_webhook(self, webhook_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
        """Send a test payload to a webhook."""
        result = await self.session.execute(
            select(Webhook).filter(
                Webhook.id == webhook_id,
                Webhook.tenant_id == tenant_id
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            return {"success": False, "error": "Webhook not found"}

        test_payload = {
            "event_type": "test",
            "severity": "info",
            "title": "Test Webhook from SigmaFlow",
            "message": "This is a test delivery to verify webhook configuration.",
            "tenant_id": str(tenant_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"test": True},
        }

        delivery = await self.dispatcher.deliver(webhook, test_payload)
        await self.session.commit()

        return {
            "success": delivery.status == WebhookStatus.DELIVERED,
            "delivery_id": str(delivery.id),
            "status": delivery.status.value,
            "response_status": delivery.response_status,
            "error": delivery.error_message,
        }
