"""
Metrics & Dashboard Aggregation API router.
Provides high-level health scores, SLA compliance, and system-wide telemetry summaries.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.api.schemas import SystemOverviewResponse

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/overview", response_model=SystemOverviewResponse)
def get_system_overview():
    """Returns top-level executive metrics for the dashboard header."""
    service_repo = ServiceRepository()
    mon_repo = MonitoringRepository()
    incident_repo = IncidentRepository()

    services = service_repo.list_services()
    open_incidents = incident_repo.get_open_incidents()

    total = len(services)
    healthy = 0
    degraded = 0
    down = 0
    total_rt = 0.0
    rt_count = 0
    total_avail = 0.0

    for s in services:
        sid = s.get("service_id")
        latest = mon_repo.get_latest_record(sid)
        if latest:
            rt = float(latest.get("response_time", 0))
            avail = float(latest.get("availability", 1))
            err = float(latest.get("error", 0))
            
            total_rt += rt
            rt_count += 1
            total_avail += avail

            if avail == 0:
                down += 1
            elif err > 0 or rt > float(s.get("response_time_threshold", 2000)):
                degraded += 1
            else:
                healthy += 1
        else:
            healthy += 1

    avg_rt = round(total_rt / rt_count, 2) if rt_count > 0 else 0.0
    overall_avail = round((total_avail / total) * 100, 2) if total > 0 else 100.0

    # Calculate overall health score (0-100)
    # Deduct points for open incidents and degraded services
    health_score = 100.0
    if total > 0:
        health_score -= (down / total) * 50.0
        health_score -= (degraded / total) * 20.0
    health_score -= min(30.0, len(open_incidents) * 10.0)
    health_score = max(0.0, min(100.0, round(health_score, 1)))

    return SystemOverviewResponse(
        total_services=total,
        healthy_services=healthy,
        degraded_services=degraded,
        down_services=down,
        active_incidents=len(open_incidents),
        average_response_time_ms=avg_rt,
        overall_availability_percentage=overall_avail,
        system_health_score=health_score,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
