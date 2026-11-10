"""Bounded read-only application tools used before operational LLM answers."""
from datetime import datetime, timezone, timedelta
import math
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.operations import reliability, dependency_map


def get_service_status(service_id):
    service = ServiceRepository().get_service(service_id)
    return dict(service=service, latest=MonitoringRepository().get_latest_record(service_id))


def get_recent_metrics(service_id, hours=24):
    return MonitoringRepository().get_historical_records(service_id, hours=hours, limit=3000)


def get_incident(incident_id):
    return IncidentRepository().get_incident(incident_id)


def get_incident_history(service_id):
    return IncidentRepository().get_service_incidents(service_id, limit=200)


def get_anomalies(records):
    return [r for r in records if r.get("anomaly")]


def get_recent_failures(records):
    return [r for r in records if not r.get("request_success")]


get_service_dependencies = dependency_map


def operational_context(services, query):
    now = datetime.now(timezone.utc)
    hours = 168 if any(word in query.lower() for word in ("week", "7 days")) else 24
    cutoff = now - timedelta(hours=hours)
    label = f"last {hours} hours"
    if "today" in query.lower():
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "today in UTC"
    elif "this week" in query.lower():
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        label = "this calendar week in UTC"
    hours = max(1, math.ceil((now - cutoff).total_seconds() / 3600))
    result = []
    for service in services[:25]:
        sid = service["service_id"]
        records = [r for r in get_recent_metrics(sid, hours) if datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) >= cutoff]
        incidents = get_incident_history(sid)
        recent = [i for i in incidents if datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")) >= cutoff]
        def compact(items, count):
            return [{k:r.get(k) for k in ("timestamp", "status_code", "response_time", "request_success", "failure_type", "anomaly", "anomaly_score", "ml_status")} for r in items[:count]]
        result.append(dict(service_id=sid, service_name=service.get("service_name"),
            reliability=reliability(service, records, recent), incident_count=len(recent),
            incident_count_is_lower_bound=len(incidents) >= 200,
            recent_incidents=[{k:i.get(k) for k in ("incident_id", "created_at", "status", "severity")} for i in recent[:10]],
            recent_metrics=compact(records, 5), failures=compact(get_recent_failures(records), 3), anomalies=compact(get_anomalies(records), 3)))
    global_incidents = IncidentRepository().get_incidents(limit=10000)
    in_window = [i for i in global_incidents if datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")) >= cutoff]
    return dict(as_of=datetime.now(timezone.utc).isoformat(), requested_window_hours=hours, services=result,
        window_label=label, window_start=cutoff.isoformat(),
        global_incident_count=len(in_window), global_incident_count_is_lower_bound=len(global_incidents) >= 10000,
        recent_global_incident_ids=[i["incident_id"] for i in in_window[:20]],
        services_truncated=len(services) > 25, dependencies=get_service_dependencies(),
        tools_used=["get_recent_metrics", "get_incident_history", "get_recent_failures", "get_anomalies", "get_service_dependencies"],
        limitations="Counts are within retrieved windows and caps; never infer customer traffic from probes; unknown data stays unknown")
