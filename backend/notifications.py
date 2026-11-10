"""SNS incident lifecycle publishing with persisted delivery attempts.

SNS Standard is at-least-once. A crash after publish but before persistence can
duplicate delivery; we never claim exactly-once email delivery.
"""
import json
import time
import boto3
from botocore.config import Config
from backend.database.incident_repository import IncidentRepository
from backend.database.concurrency import mutate
from backend.lifecycle import utcnow, elapsed, event
from backend.utils.config import get_settings
from backend.utils.logger import get_logger
logger = get_logger(__name__)


def publish_pending(incident_id):
    settings = get_settings()
    repo = IncidentRepository()
    incident = repo.get_incident(incident_id)
    history = incident.get("notifications", [])
    if float(incident.get("alerts_muted_until", 0)) > time.time() and incident["status"] not in {"RESOLVED", "CLOSED"}:
        return {"status": "muted"}
    sent = {n["kind"] for n in history if n["status"] == "sent"}
    kinds = []
    if "created" not in sent: kinds.append("created")
    if incident["severity"] == "CRITICAL" and "critical" not in sent and "created" in sent: kinds.append("critical")
    if incident["status"] in {"RESOLVED", "CLOSED"}:
        if "recovery" not in sent: kinds.append("recovery")
    elif elapsed(incident["created_at"], utcnow()) >= settings.escalation_seconds and "escalation" not in sent:
        kinds.append("escalation")
    # Failed delivery retries have a one-minute cooldown during local polling.
    for kind in kinds:
        attempts = [n for n in history if n["kind"] == kind]
        if settings.environment.lower() != "production" and attempts and attempts[-1]["status"] == "failed" and elapsed(attempts[-1]["timestamp"], utcnow()) < 60:
            continue
        if not settings.sns_alert_enabled or not settings.sns_topic_arn:
            return {"status": "not_configured", "email_delivery_verified": False}
        entry = dict(kind=kind, timestamp=utcnow(), status="failed")
        error = None
        try:
            sns = boto3.client("sns", region_name=settings.aws_region, config=Config(connect_timeout=2, read_timeout=4, retries={"mode": "standard", "max_attempts": 3}))
            response = sns.publish(TopicArn=settings.sns_topic_arn,
                Subject=f'ISMS {kind.upper()}: {incident["severity"]} {incident.get("service_name", "")}'[:100],
                Message=json.dumps({"event": kind, "incident_id": incident_id, "service": incident.get("service_name"), "severity": incident["severity"], "status": incident["status"], "evidence": incident.get("metrics_snapshot"), "downtime_seconds": incident.get("downtime_seconds"), "cause": "Unconfirmed; inspect incident evidence"}, default=str))
            entry.update(status="sent", message_id=response["MessageId"])
        except Exception as exc:
            entry["error_type"] = type(exc).__name__
            error = exc
            logger.exception("SNS publish failed", extra={"action": "sns_failure", "incident_id": incident_id})
        def record(item):
            item["notifications"] = (item.get("notifications", []) + [entry])[-100:]
            item["timeline"] = (item.get("timeline", []) + [event(f'NOTIFICATION_{kind.upper()}_{entry["status"].upper()}', entry["timestamp"])])[-200:]
        mutate(repo.table, {"incident_id": incident_id}, record)
        if error: raise error
    return {"status": "processed", "email_delivery_verified": False}
