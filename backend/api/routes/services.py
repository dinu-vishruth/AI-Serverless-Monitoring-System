"""
Services API router — CRUD operations for monitored services.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.api.schemas import ServiceCreate, ServiceUpdate, ServiceResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=List[dict])
def list_services(
    active_only: bool = Query(default=False, description="Filter for active services only")
):
    """Retrieve all monitored service configurations."""
    repo = ServiceRepository()
    if active_only:
        services = repo.get_active_services()
    else:
        services = repo.list_services()

    # Enrich with latest health check summary
    mon_repo = MonitoringRepository()
    enriched = []
    for s in services:
        service_id = s.get("service_id")
        latest = mon_repo.get_latest_record(service_id)
        s_copy = dict(s)
        if latest:
            s_copy["last_check_status"] = "HEALTHY" if latest.get("availability") == 1 and latest.get("error") == 0 else "DOWN" if latest.get("availability") == 0 else "DEGRADED"
            s_copy["last_response_time"] = latest.get("response_time")
            s_copy["last_status_code"] = latest.get("status_code")
            s_copy["last_checked_at"] = latest.get("timestamp")
        else:
            s_copy["last_check_status"] = "UNKNOWN"
            s_copy["last_response_time"] = None
            s_copy["last_status_code"] = None
            s_copy["last_checked_at"] = None
        enriched.append(s_copy)

    return enriched


@router.get("/{service_id}", response_model=dict)
def get_service(service_id: str):
    """Get service details by ID."""
    repo = ServiceRepository()
    service = repo.get_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Service '{service_id}' not found")
    
    # Enrich with latest status
    mon_repo = MonitoringRepository()
    latest = mon_repo.get_latest_record(service_id)
    service_copy = dict(service)
    if latest:
        service_copy["latest_record"] = latest
    return service_copy


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate):
    """Register a new service to monitor."""
    repo = ServiceRepository()
    try:
        service_data = payload.model_dump()
        created = repo.create_service(service_data)
        logger.info(f"Service created: {created['service_id']} ({created['service_name']})")
        return created
    except Exception as e:
        logger.error(f"Failed to create service: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{service_id}", response_model=dict)
def update_service(service_id: str, payload: ServiceUpdate):
    """Update service monitoring parameters."""
    repo = ServiceRepository()
    existing = repo.get_service(service_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Service '{service_id}' not found")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        return existing

    updated = repo.update_service(service_id, update_data)
    return updated


@router.delete("/{service_id}", status_code=status.HTTP_200_OK)
def delete_service(service_id: str):
    """Delete a service from monitoring."""
    repo = ServiceRepository()
    existing = repo.get_service(service_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Service '{service_id}' not found")

    success = repo.delete_service(service_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete service")

    return {"message": f"Service '{service_id}' deleted successfully"}
