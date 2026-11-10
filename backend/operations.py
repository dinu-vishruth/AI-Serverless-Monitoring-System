"""Reliability statistics and dependency correlation from measured samples."""
from datetime import datetime, timezone
import numpy as np
from backend.lifecycle import elapsed
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository


def service_health(service, record):
    if not record: return "UNKNOWN"
    timestamp = record.get("timestamp")
    if timestamp and service.get("is_active", True):
        checked = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - checked).total_seconds() > max(180, 3 * int(service.get("check_interval", 60))):
            return "UNKNOWN"
    if not float(record.get("availability", 0)): return "DOWN"
    if float(record.get("error", 0)) or float(record.get("response_time", 0)) > float(service.get("response_time_threshold", 2000)) or record.get("anomaly") or service.get("health_state") == "RECOVERED": return "DEGRADED"
    return "HEALTHY"


def reliability(service, records, incidents):
    records = sorted(records, key=lambda r: r["timestamp"])
    count = len(records)
    success = [r for r in records if r.get("request_success")]
    latencies = [float(r["response_time"]) for r in success]
    failures = count - len(success)
    availability = len(success) / count * 100 if count else None
    error_rate = failures / count if count else None
    target = float(service.get("availability_target", 99.9))
    allowed = count * (1 - target / 100)
    budget = max(0, (allowed - failures) / allowed * 100) if allowed else None
    completed = [i for i in incidents if i.get("resolved_at") and i.get("started_at")]
    durations = [elapsed(i["started_at"], i["resolved_at"]) for i in completed]
    # MTBF measures fully observed intervals between recovery and the next incident.
    ordered = sorted(incidents, key=lambda i: i["created_at"])
    intervals = [elapsed(a["resolved_at"], b.get("started_at", b["created_at"])) for a, b in zip(ordered, ordered[1:]) if a.get("resolved_at") and a["resolved_at"] <= b.get("started_at", b["created_at"])]
    p95 = float(np.percentile(latencies, 95)) if len(latencies) >= 20 else None
    latency_target = float(service.get("latency_target_ms", 500))
    compliance = None if availability is None or p95 is None else availability >= target and p95 < latency_target and error_rate <= float(service.get("error_rate_target", .01))
    trend = None
    if len(latencies) >= 10:
        half = len(latencies) // 2
        trend = float(np.mean(latencies[half:]) - np.mean(latencies[:half]))
    return dict(sample_count=count, failure_count=failures, availability_percentage=availability,
        error_rate=error_rate, average_latency_ms=float(np.mean(latencies)) if latencies else None,
        p50_ms=float(np.percentile(latencies, 50)) if len(latencies) >= 2 else None,
        p95_ms=p95, p99_ms=float(np.percentile(latencies, 99)) if len(latencies) >= 100 else None,
        mttr_seconds=float(np.mean(durations)) if durations else None,
        mtbf_seconds=float(np.mean(intervals)) if intervals else None,
        latency_trend_ms=trend, error_budget_remaining_percentage=budget, slo_compliant=compliance,
        latency_compliance_percentage=sum(v < latency_target for v in latencies) / len(latencies) * 100 if latencies else None,
        measurement_basis="Probe samples; latency excludes failed requests; MTTR uses completed incidents; missing coverage is unknown",
        window_start=records[0]["timestamp"] if count else None, window_end=records[-1]["timestamp"] if count else None,
        truncated=count >= 3000)


def dependency_map():
    services = ServiceRepository().get_all_services()
    nodes = {s["service_id"]: dict(service_id=s["service_id"], name=s.get("service_name"), state=s.get("health_state", "UNKNOWN")) for s in services}
    edges = [dict(source=s["service_id"], dependency=d) for s in services for d in s.get("dependencies", [])]
    def affected(root):
        result, pending = set(), [root]
        while pending:
            current = pending.pop()
            for edge in edges:
                if edge["dependency"] == current and edge["source"] not in result and edge["source"] != root:
                    result.add(edge["source"])
                    pending.append(edge["source"])
        return sorted(result)
    unhealthy = [dict(**n, affected_services=affected(sid)) for sid, n in nodes.items() if n["state"] not in {"HEALTHY", "UNKNOWN"}]
    return dict(nodes=list(nodes.values()), edges=edges, unhealthy_dependencies=unhealthy,
        interpretation="Dependencies are administrator-declared; correlated failures are hypotheses, not proven causation")


def correlation(incident):
    history = MonitoringRepository().get_records(incident["service_id"], limit=60, end_time=incident["created_at"])
    timeline = []
    for r in sorted(history, key=lambda r: r["timestamp"]):
        timeline.append(dict(timestamp=r["timestamp"], action="HEALTH_CHECK", status_code=r.get("status_code"), latency_ms=r.get("response_time"), failure_type=r.get("failure_type"), anomaly=r.get("anomaly"), model_version=r.get("model_version")))
    return dict(timeline=timeline, lifecycle=incident.get("timeline", []), dependencies=dependency_map(),
        related_incidents=[{k:i.get(k) for k in ("incident_id", "service_id", "severity", "status", "created_at")} for i in IncidentRepository().get_incidents(limit=200) if abs(elapsed(min(i["created_at"], incident["created_at"]), max(i["created_at"], incident["created_at"]))) <= 300][:20],
        unavailable_evidence=["Application logs", "Deployment events", "Database telemetry"], causal_conclusion="Unconfirmed")
