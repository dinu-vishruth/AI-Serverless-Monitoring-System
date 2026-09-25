"""
Monitoring API router — health check data query and manual trigger.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.lambdas.health_checker.handler import check_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/{service_id}/records", response_model=List[dict])
def get_service_records(
    service_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    hours: Optional[int] = Query(default=None, ge=1, le=168),
):
    """Retrieve historical monitoring metrics for a specific service."""
    repo = MonitoringRepository()
    if hours:
        records = repo.get_historical_records(service_id, hours=hours, limit=limit)
    else:
        records = repo.get_recent_records(service_id, limit=limit)
    return records


@router.get("/{service_id}/latest", response_model=dict)
def get_latest_record(service_id: str):
    """Get the latest monitoring check record for a service."""
    repo = MonitoringRepository()
    record = repo.get_latest_record(service_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monitoring records found for service '{service_id}'"
        )
    return record


@router.post("/{service_id}/check-now", response_model=dict)
def trigger_immediate_check(service_id: str):
    """Trigger an immediate health check and AI analysis for a service."""
    service_repo = ServiceRepository()
    service = service_repo.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )

    try:
        result = check_service(service)
        return {
            "message": "Health check executed successfully",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Manual check failed for {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check execution failed: {str(e)}"
        )


@router.get("/summary/all", response_model=List[dict])
def get_all_services_latest_summary():
    """Get the latest metrics summary across all services."""
    service_repo = ServiceRepository()
    mon_repo = MonitoringRepository()
    services = service_repo.list_services()

    summaries = []
    for s in services:
        sid = s.get("service_id")
        latest = mon_repo.get_latest_record(sid)
        summaries.append({
            "service_id": sid,
            "service_name": s.get("service_name"),
            "url": s.get("url"),
            "is_active": s.get("is_active", True),
            "latest_record": latest,
        })

    return summaries
