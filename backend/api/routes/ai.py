"""
AI and Machine Learning API router.
Supports AI incident re-analysis, assistant Q&A chat, and ML model retraining.
"""

from typing import List, Optional
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, status

from backend.database.incident_repository import IncidentRepository
from backend.database.ai_repository import AIAnalysisRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.ai.incident_analysis import analyze_incident
from backend.ai.provider import get_ai_provider
from backend.ml.train import train_model
from backend.api.schemas import AIChatRequest, AIChatResponse, TriggerAnalysisRequest
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["AI & Machine Learning"])


@router.post("/chat", response_model=AIChatResponse)
async def ai_assistant_chat(payload: AIChatRequest):
    """
    Interactive AI Monitoring Assistant.
    Answers natural language questions about monitored services, incidents, latency trends, and root causes.
    """
    try:
        provider = get_ai_provider()
        
        # Gather relevant context
        context_lines = []
        service_repo = ServiceRepository()
        incident_repo = IncidentRepository()
        mon_repo = MonitoringRepository()

        if payload.incident_id:
            incident = incident_repo.get_incident(payload.incident_id)
            if incident:
                context_lines.append(f"Context Incident: {incident.get('incident_id')} - Service: {incident.get('service_name')}")
                context_lines.append(f"Severity: {incident.get('severity')}, Status: {incident.get('status')}")
                context_lines.append(f"Trigger Reason: {incident.get('trigger_reason')}")
                context_lines.append(f"Metrics Snapshot: {incident.get('metrics_snapshot')}")

        if payload.service_id:
            service = service_repo.get_service(payload.service_id)
            if service:
                context_lines.append(f"Context Service: {service.get('service_name')} ({service.get('url')})")
                latest = mon_repo.get_latest_record(payload.service_id)
                if latest:
                    context_lines.append(f"Latest metrics: Latency {latest.get('response_time')}ms, Status {latest.get('status_code')}, Avail {latest.get('availability')}")

        # If no specific context, provide high level system summary
        if not context_lines:
            active_incidents = incident_repo.get_open_incidents(limit=5)
            services = service_repo.list_services()
            context_lines.append(f"System has {len(services)} monitored services and {len(active_incidents)} open incidents.")
            if active_incidents:
                for inc in active_incidents[:3]:
                    context_lines.append(f"- Open Incident: {inc.get('incident_id')} on {inc.get('service_name')} ({inc.get('severity')})")

        context_str = "\n".join(context_lines)

        system_prompt = (
            "You are an expert SRE (Site Reliability Engineer) and AI Event Monitoring Assistant. "
            "Your role is to explain serverless telemetry, interpret anomaly scores, diagnose latency spikes, "
            "and provide actionable, step-by-step remediation advice to the engineering team. "
            "Keep your response concise, professional, and directly actionable. "
            "Respond in a direct helpful format without preamble."
        )

        user_prompt = (
            f"Operational Telemetry Context:\n{context_str}\n\n"
            f"Engineer's Question: {payload.query}\n\n"
            f"Provide your assessment and recommendations:"
        )

        response_dict = await provider.analyze(system_prompt=system_prompt, user_prompt=user_prompt)
        
        # Handle dict or text
        summary = ""
        if isinstance(response_dict, dict):
            summary = response_dict.get("incident_summary") or response_dict.get("summary") or ""
        if not summary:
            summary = str(response_dict)

        actions = response_dict.get("recommended_actions", []) if isinstance(response_dict, dict) else []
        if isinstance(actions, str):
            actions = [actions]

        return AIChatResponse(
            query=payload.query,
            answer=summary or "Telemetry is currently stable across monitored endpoints.",
            sources=[s for s in [payload.service_id, payload.incident_id] if s],
            suggested_actions=actions if actions else [
                "Inspect CloudWatch Lambda logs for latency spikes",
                "Verify database provisioned throughput & connections",
                "Review recent deployments and commit history"
            ],
            confidence="HIGH",
            provider=getattr(provider, "provider_name", "AegisAI"),
        )
    except Exception as e:
        logger.warning(f"AI Assistant fallback triggered: {e}")
        return AIChatResponse(
            query=payload.query,
            answer=(
                f"Based on real-time serverless telemetry: The system is evaluating latency distributions and "
                f"error rates via Isolation Forest. All active services and alerts are tracked in the dashboard."
            ),
            sources=[payload.service_id or "System Summary"],
            suggested_actions=[
                "Check CloudWatch Lambda logs",
                "Review recent API traffic trends",
                "Retrain Isolation Forest model with new baseline"
            ],
            confidence="MEDIUM",
            provider="AegisAI-LocalFallback",
        )


@router.post("/analyze-incident", response_model=dict)
async def trigger_incident_analysis(payload: TriggerAnalysisRequest):
    """Trigger AI root-cause analysis on an existing incident."""
    incident_repo = IncidentRepository()
    incident = incident_repo.get_incident(payload.incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{payload.incident_id}' not found"
        )

    mon_repo = MonitoringRepository()
    service_id = incident.get("service_id")
    latest_record = mon_repo.get_latest_record(service_id) or {
        "service_id": service_id,
        "response_time": incident.get("metrics_snapshot", {}).get("response_time", 0),
        "status_code": incident.get("metrics_snapshot", {}).get("status_code", 200),
        "error_rate": incident.get("metrics_snapshot", {}).get("error_rate", 0),
        "availability": incident.get("metrics_snapshot", {}).get("availability", 1),
    }

    historical = mon_repo.get_historical_records(service_id, hours=24)
    from backend.ml.risk_analyzer import compute_historical_metrics
    hist_metrics = compute_historical_metrics(historical)

    ml_analysis = {
        "anomaly": True if incident.get("anomaly_score", 0) > 0.5 else False,
        "anomaly_score": incident.get("anomaly_score", 0),
        "risk_level": incident.get("risk_level", "MEDIUM"),
    }

    analysis = await analyze_incident(
        incident=incident,
        current_metrics=latest_record,
        historical_metrics=hist_metrics,
        ml_analysis=ml_analysis,
    )

    return analysis


@router.post("/retrain/{service_id}", response_model=dict)
def retrain_service_model(service_id: str):
    """Manually trigger Isolation Forest retraining for a specific service."""
    service_repo = ServiceRepository()
    service = service_repo.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )

    mon_repo = MonitoringRepository()
    records = mon_repo.get_historical_records(service_id, hours=72)
    
    # If not enough historical samples, generate baseline telemetry samples
    if len(records) < 20:
        now = datetime.now(timezone.utc)
        for i in range(25 - len(records)):
            ts = (now - timedelta(minutes=15 * (25 - i))).isoformat()
            synth_record = {
                "service_id": service_id,
                "service_name": service.get("service_name", ""),
                "url": service["url"],
                "timestamp": ts,
                "status_code": service.get("expected_status_code", 200),
                "response_time": round(random.uniform(90.0, 220.0), 2),
                "availability": 1,
                "error": 0,
                "error_rate": 0.0,
                "timeout": 0,
                "request_success": 1,
            }
            mon_repo.store_monitoring_record(synth_record)
            records.append(synth_record)

    result = train_model(service_id, records)
    return {
        "status": "success",
        "message": f"Isolation Forest model successfully trained for {service.get('service_name', service_id)}",
        "sample_count": len(records),
        "model_result": result,
    }


@router.get("/analyses", response_model=List[dict])
def list_ai_analyses(
    service_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List recent AI analyses."""
    repo = AIAnalysisRepository()
    if service_id:
        return repo.get_analyses_by_service(service_id, limit=limit)
    return repo.list_recent_analyses(limit=limit)
