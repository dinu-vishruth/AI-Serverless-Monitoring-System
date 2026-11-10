"""Deterministic incident lifecycle. ML is evidence, never a prerequisite."""
from datetime import datetime, timezone
from hashlib import sha256
from backend.database.service_repository import ServiceRepository
from backend.database.incident_repository import IncidentRepository
from backend.database.concurrency import mutate
from backend.utils.config import get_settings

ACTIVE = {"CONFIRMED_INCIDENT", "ACKNOWLEDGED", "INVESTIGATING", "MITIGATING", "RECOVERED", "OPEN"}
TRANSITIONS = {
    "OPEN": {"ACKNOWLEDGED", "INVESTIGATING", "MITIGATING"},
    "CONFIRMED_INCIDENT": {"ACKNOWLEDGED", "INVESTIGATING", "MITIGATING"},
    "ACKNOWLEDGED": {"INVESTIGATING", "MITIGATING"},
    "INVESTIGATING": {"MITIGATING"},
    "MITIGATING": {"INVESTIGATING"},
    "RECOVERED": set(),
    "RESOLVED": {"CLOSED"},
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def elapsed(start, end):
    return max(0, (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds())


def event(action, timestamp, actor="monitor", comments=""):
    return dict(action=action, timestamp=timestamp, actor=actor, comments=comments)


def classify(service, record, failures, anomaly):
    if not record.get("request_success"):
        if failures >= int(service.get("failure_threshold", get_settings().failure_threshold)):
            return "CRITICAL" if service.get("criticality", "standard") == "critical" or failures >= 5 else "HIGH"
        return "MEDIUM"
    ratio = float(record["response_time"]) / float(service.get("response_time_threshold", 2000))
    if ratio >= 2: return "HIGH"
    if ratio > 1 or anomaly.get("anomaly"): return "MEDIUM"
    return "LOW"


def process_observation(service, record, anomaly, risk):
    """Called under the per-service lease. Monotonic timestamps reject replay."""
    services, incidents = ServiceRepository(), IncidentRepository()
    state = services.get_service(service["service_id"])
    if state.get("last_processed_at", "") >= record["timestamp"]:
        return {"duplicate": True}
    now = record["timestamp"]
    failed = not bool(record.get("request_success"))
    degraded = not failed and (float(record["response_time"]) > float(service.get("response_time_threshold", 2000)) or anomaly.get("anomaly", False))
    failures = int(state.get("consecutive_failures", 0)) + 1 if failed else 0
    successes = int(state.get("consecutive_successes", 0)) + 1 if not failed and not degraded else 0
    deviations = int(state.get("consecutive_degradations", 0)) + 1 if degraded else 0
    from backend.database.monitoring_repository import MonitoringRepository
    recent = MonitoringRepository().get_records(service["service_id"], limit=20)
    rolling_error = sum(not r.get("request_success") for r in recent) / len(recent) if recent else 0
    recent_clean = len(recent) >= 3 and all(r.get("request_success") for r in recent[:3])
    high_error = len(recent) >= 10 and rolling_error > max(.2, float(service.get("error_threshold", .05))) and not recent_clean
    error_windows = int(state.get("high_error_windows", 0)) + 1 if high_error else 0
    severity = classify(service, record, failures, anomaly)
    first_failure = state.get("failure_started_at") or now
    health = "SUSPECTED_FAILURE" if failed else "DEGRADED" if degraded else "HEALTHY"
    incident = incidents.get_incident(state["active_incident_id"]) if state.get("active_incident_id") else incidents.get_open_incident_for_service(service["service_id"])
    if incident and incident["status"] not in ACTIVE:
        incident = None
    confirmed = failures >= int(service.get("failure_threshold", get_settings().failure_threshold)) or deviations >= 3 or (error_windows >= 3 and (failed or degraded))
    if error_windows >= 3:
        severity = "HIGH"
    if confirmed and not incident:
        incident_id = "INC-" + sha256(f'{service["service_id"]}:{first_failure}'.encode()).hexdigest()[:20]
        incident = incidents.get_incident(incident_id)
        if not incident:
            incident = incidents.create_incident(dict(
                incident_id=incident_id, service_id=service["service_id"], service_name=service.get("service_name", ""),
                created_at=now, started_at=first_failure, status="CONFIRMED_INCIDENT", severity=severity,
                trigger_reason="Sustained measured probe error rate" if error_windows >= 3 else "Repeated health-check failure" if failed else "Sustained latency/ML deviation",
                detection_source="rule" if failed or error_windows >= 3 else "ml" if anomaly.get("anomaly") else "latency_rule",
                anomaly_score=anomaly.get("anomaly_score"), model_version=anomaly.get("model_version"),
                risk_score=risk.get("risk_score", 0), risk_level=severity, metrics_snapshot=dict(record),
                timeline=[event("CONFIRMED_INCIDENT", now)], notifications=[], ai_status="pending", failure_count=max(0, failures-1),
            ))
    if incident:
        def update(item):
            if item.get("last_observed_at", "") >= now:
                return "HEALTHY" if item["status"] == "RESOLVED" else "RECOVERED" if item["status"] == "RECOVERED" else "CONFIRMED_INCIDENT"
            item.update(updated_at=now, last_observed_at=now, failure_count=int(item.get("failure_count", 0)) + int(failed))
            if failed or degraded:
                if item["status"] == "RECOVERED":
                    item["status"] = "CONFIRMED_INCIDENT"
                    item["timeline"] = item.get("timeline", []) + [event("RECOVERY_FAILED", now)]
                item["severity"] = severity if severity in {"HIGH", "CRITICAL"} else item["severity"]
                item["metrics_snapshot"] = dict(record)
                health_state = "CONFIRMED_INCIDENT"
            else:
                health_state = "RECOVERED"
                if successes >= int(service.get("recovery_threshold", get_settings().recovery_threshold)):
                    item.update(status="RESOLVED", resolved_at=now, downtime_seconds=elapsed(item.get("started_at", item["created_at"]), now))
                    item["timeline"] = item.get("timeline", []) + [event("RECOVERED", now), event("RESOLVED", now)]
                    health_state = "HEALTHY"
                elif item["status"] != "RECOVERED":
                    item["status"] = "RECOVERED"
                    item["timeline"] = item.get("timeline", []) + [event("RECOVERY_PENDING", now)]
            item["timeline"] = item.get("timeline", [])[-200:]
            return health_state
        incident, health = mutate(incidents.table, {"incident_id": incident["incident_id"]}, update)
    updates = dict(
        health_state=health, consecutive_failures=failures, consecutive_successes=successes,
        consecutive_degradations=deviations, last_processed_at=now,
        high_error_windows=error_windows, rolling_error_rate=rolling_error,
        active_incident_id=incident["incident_id"] if incident and incident["status"] != "RESOLVED" else None,
        failure_started_at=first_failure if failed or degraded else None,
    )
    updates["last_failed_check" if failed else "last_successful_check"] = now
    mutate(services.table, {"service_id": service["service_id"]}, lambda item: item.update(updates))
    return dict(health_state=health, severity=severity, incident_id=incident["incident_id"] if incident else None)


def operator_transition(incident_id, status, actor, comments=""):
    repo = IncidentRepository()
    def change(item):
        if status not in TRANSITIONS.get(item["status"], set()):
            raise ValueError(f'Cannot transition {item["status"]} to {status}; recovery requires verified checks')
        now = utcnow()
        item.update(status=status, updated_at=now)
        if status == "ACKNOWLEDGED": item.update(acknowledged_by=actor, acknowledged_at=now)
        item["timeline"] = (item.get("timeline", []) + [event(status, now, actor, comments)])[-200:]
        if comments: item["resolution_notes"] = comments
    return mutate(repo.table, {"incident_id": incident_id}, change)[0]
