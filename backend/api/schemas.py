"""
Pydantic schemas for API request and response validation.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Service Schemas ---

class ServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    url: str = Field(..., description="Target endpoint URL (HTTP/HTTPS)")
    http_method: str = Field(default="GET", description="HTTP method: GET, POST, HEAD")
    expected_status_code: int = Field(default=200, ge=100, le=599)
    check_interval: int = Field(default=60, ge=10, le=3600, description="Check interval in seconds")
    timeout: int = Field(default=10, ge=1, le=60, description="Request timeout in seconds")
    response_time_threshold: float = Field(default=2000.0, gt=0, description="Alert threshold (ms)")
    error_threshold: float = Field(default=0.05, ge=0.0, le=1.0, description="Error rate threshold (0-1)")
    is_active: bool = Field(default=True)
    tags: List[str] = Field(default_factory=list)


class ServiceUpdate(BaseModel):
    service_name: Optional[str] = None
    url: Optional[str] = None
    http_method: Optional[str] = None
    expected_status_code: Optional[int] = None
    check_interval: Optional[int] = None
    timeout: Optional[int] = None
    response_time_threshold: Optional[float] = None
    error_threshold: Optional[float] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None


class ServiceResponse(BaseModel):
    service_id: str
    service_name: str
    url: str
    http_method: str
    expected_status_code: int
    check_interval: int
    timeout: int
    response_time_threshold: float
    error_threshold: float
    is_active: bool
    tags: List[str]
    created_at: str
    updated_at: str
    last_check_status: Optional[str] = None
    last_response_time: Optional[float] = None
    current_health_score: Optional[float] = None


# --- Monitoring Schemas ---

class MonitoringRecordResponse(BaseModel):
    service_id: str
    service_name: Optional[str] = ""
    timestamp: str
    response_time: float
    status_code: int
    availability: int
    error: int
    error_rate: float
    timeout: int
    request_success: int
    anomaly: Optional[bool] = False
    anomaly_score: Optional[float] = 0.0
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "LOW"


class TimeSeriesQuery(BaseModel):
    service_id: str
    hours: int = Field(default=24, ge=1, le=168)
    limit: int = Field(default=500, ge=1, le=2000)


# --- Incident Schemas ---

class IncidentUpdate(BaseModel):
    status: Optional[str] = Field(None, description="OPEN, INVESTIGATING, RESOLVED, CLOSED")
    resolution_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class IncidentResponse(BaseModel):
    incident_id: str
    service_id: str
    service_name: Optional[str] = ""
    severity: str
    status: str
    trigger_reason: str
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    anomaly_score: Optional[float] = 0.0
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "MEDIUM"
    metrics_snapshot: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    resolution_notes: Optional[str] = None


# --- AI & Assistant Schemas ---

class AIChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question about system health or incidents")
    service_id: Optional[str] = None
    incident_id: Optional[str] = None


class AIChatResponse(BaseModel):
    query: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    confidence: str = "HIGH"
    provider: str


class TriggerAnalysisRequest(BaseModel):
    incident_id: str
    force_refresh: bool = False


# --- Dashboard Overview Schemas ---

class SystemOverviewResponse(BaseModel):
    total_services: int
    healthy_services: int
    degraded_services: int
    down_services: int
    active_incidents: int
    average_response_time_ms: float
    overall_availability_percentage: float
    system_health_score: float
    last_updated: str
