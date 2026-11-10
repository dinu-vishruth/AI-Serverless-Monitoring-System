"""Operational reliability, dependencies, alert status and approved runbooks."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.database.concurrency import mutate
from backend.operations import reliability, dependency_map, correlation
from backend.lifecycle import event, utcnow
from backend.utils.config import get_settings

router = APIRouter(tags=["Operations"])


@router.get("/monitoring/{service_id}/reliability")
def service_reliability(service_id: str, hours: int = Query(24, ge=1, le=168)):
    service = ServiceRepository().get_service(service_id)
    if not service: raise HTTPException(404, "Service not found")
    records = MonitoringRepository().get_historical_records(service_id, hours=hours, limit=3000)
    return reliability(service, records, IncidentRepository().get_service_incidents(service_id, limit=200))


@router.get("/dependencies")
def dependencies():
    return dependency_map()


@router.get("/incidents/{incident_id}/correlation")
def incident_correlation(incident_id: str):
    incident = IncidentRepository().get_incident(incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    return correlation(incident)


@router.get("/notifications/status")
def notification_status():
    import boto3
    settings = get_settings()
    if not settings.sns_topic_arn:
        return dict(configured=False, confirmed_email_subscriptions=0, email_delivery_verified=False)
    subscriptions = []
    client = boto3.client("sns", region_name=settings.aws_region)
    for page in client.get_paginator("list_subscriptions_by_topic").paginate(TopicArn=settings.sns_topic_arn):
        subscriptions.extend(page["Subscriptions"])
    return dict(configured=True, enabled=settings.sns_alert_enabled,
        confirmed_email_subscriptions=sum(s["Protocol"] == "email" and s["SubscriptionArn"] != "PendingConfirmation" for s in subscriptions),
        pending_subscriptions=sum(s["SubscriptionArn"] == "PendingConfirmation" for s in subscriptions), email_delivery_verified=False)


class RunbookRequest(BaseModel):
    action: Literal["retry_health_check", "mute_alerts", "unmute_alerts"]
    authorized: Literal[True]
    comments: str = Field(default="", max_length=1000)


@router.post("/incidents/{incident_id}/remediate")
def remediate(incident_id: str, payload: RunbookRequest, request: Request):
    repo = IncidentRepository()
    incident = repo.get_incident(incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    started = event("REMEDIATION_STARTED", utcnow(), request.state.actor, payload.comments)
    started["runbook"] = payload.action
    mutate(repo.table, {"incident_id": incident_id}, lambda i: i.update(timeline=(i.get("timeline", []) + [started])[-200:]))
    result = {"status": "failed"}
    try:
        if payload.action == "retry_health_check":
            from backend.lambdas.health_checker.handler import check_service
            result = check_service(ServiceRepository().get_service(incident["service_id"]))
        else:
            mutate(repo.table, {"incident_id": incident_id}, lambda i: i.update(alerts_muted_until=__import__("time").time() + 3600 if payload.action == "mute_alerts" else 0))
            result = {"status": "completed", "recovery_verified": False}
        return result
    finally:
        finished = event("REMEDIATION_RESULT", utcnow(), request.state.actor)
        finished.update(runbook=payload.action, result={k: result.get(k) for k in ("status", "request_success", "health_state", "recovery_verified")})
        mutate(repo.table, {"incident_id": incident_id}, lambda i: i.update(timeline=(i.get("timeline", []) + [finished])[-200:]))


class DemoMode(BaseModel):
    mode: Literal["ONLINE", "HTTP_500", "HTTP_503", "TIMEOUT", "SLOW_RESPONSE", "RECOVERY"]


@router.put("/demo/mode")
def set_demo_mode(payload: DemoMode, request: Request):
    if not get_settings().demo_enabled: raise HTTPException(404, "Demo disabled")
    ServiceRepository().table.put_item(Item={"service_id": "__demo_control__", "item_kind": "control", "is_active": False, "mode": payload.mode, "actor": request.state.actor, "updated_at": utcnow()})
    return {"mode": payload.mode}
