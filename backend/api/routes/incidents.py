"""
Incidents API router — Incident triage, detail views, and resolution.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.database.incident_repository import IncidentRepository
from backend.database.ai_repository import AIAnalysisRepository
from backend.api.schemas import IncidentUpdate, IncidentResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=List[dict])
def list_incidents(
    status_filter: Optional[str] = Query(default=None, description="Filter by status: OPEN, INVESTIGATING, RESOLVED, CLOSED"),
    severity: Optional[str] = Query(default=None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    service_id: Optional[str] = Query(default=None, description="Filter by specific service ID"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List incidents with optional filters."""
    repo = IncidentRepository()
    if service_id:
        incidents = repo.get_incidents_by_service(service_id, limit=limit)
    elif status_filter == "OPEN":
        incidents = repo.get_open_incidents(limit=limit)
    else:
        incidents = repo.list_incidents(limit=limit, status_filter=status_filter)

    if severity:
        incidents = [i for i in incidents if i.get("severity") == severity]

    return incidents


@router.get("/{incident_id}", response_model=dict)
def get_incident(incident_id: str):
    """Get complete incident details including AI analysis."""
    repo = IncidentRepository()
    incident = repo.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found"
        )

    # Attach any persisted AI analysis
    ai_repo = AIAnalysisRepository()
    ai_analysis = ai_repo.get_analysis_by_incident(incident_id)
    incident_copy = dict(incident)
    if ai_analysis:
        incident_copy["ai_analysis"] = ai_analysis

    return incident_copy


@router.patch("/{incident_id}", response_model=dict)
def update_incident(incident_id: str, payload: IncidentUpdate):
    """Update incident status (e.g. acknowledge or resolve)."""
    repo = IncidentRepository()
    incident = repo.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found"
        )

    update_fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    
    if "status" in update_fields:
        updated = repo.update_incident_status(
            incident_id=incident_id,
            status=update_fields["status"],
            resolution_notes=update_fields.get("resolution_notes"),
        )
    else:
        updated = repo.update_incident(incident_id, update_fields)

    return updated
