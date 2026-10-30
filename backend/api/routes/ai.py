"""
AI and Machine Learning API router.
Supports AI incident re-analysis, assistant Q&A chat, and ML model retraining.
"""

from typing import List, Optional
import json
import random
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, status

from backend.database.incident_repository import IncidentRepository
from backend.database.ai_repository import AIAnalysisRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.ai.incident_analysis import analyze_incident
from backend.ai.provider import AIProviderError, get_ai_provider
from backend.ai.prompts import MONITORING_ASSISTANT_SYSTEM_PROMPT
from backend.ml.train import train_model
from backend.api.schemas import AIChatRequest, AIChatResponse, TriggerAnalysisRequest
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["AI & Machine Learning"])

_MONITORING_QUESTION_TERMS = re.compile(
    r"\b(?:services?|incidents?|monitor(?:ing)?|telemetry|response[\s-]+time|"
    r"latency|error[\s-]+rate|availability|anomal(?:y|ies)|isolation[\s-]+forest|"
    r"risk(?:[\s-]+score)?|thresholds?|health(?:y)?|degraded|outages?|status[\s-]+codes?|"
    r"metrics?|dashboard|alerts?|serverless|endpoints?|system[\s-]+health|overall[\s-]+health)\b",
    re.IGNORECASE,
)
_CONTEXTUAL_REFERENCES = re.compile(
    r"\b(?:this|that|these|those)\s+(?:service|incident|metric|data|chart|alert)s?\b",
    re.IGNORECASE,
)
_OUT_OF_SCOPE_ANSWER = (
    "I can only answer questions grounded in this application's monitored "
    "services, telemetry, anomalies, and incidents. Ask about one of those "
    "topics or select a service or incident for context."
)


def _build_chat_context(payload):
    service_repo = ServiceRepository()
    incident_repo = IncidentRepository()
    mon_repo = MonitoringRepository()

    selected_service = None
    selected_incident = None
    if payload.service_id:
        selected_service = service_repo.get_service(payload.service_id)
        if not selected_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{payload.service_id}' was not found.",
            )

    if payload.incident_id:
        selected_incident = incident_repo.get_incident(payload.incident_id)
        if not selected_incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{payload.incident_id}' was not found.",
            )
        if (
            selected_service
            and selected_incident.get("service_id") != selected_service.get("service_id")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected service and incident do not match.",
            )

    if selected_service:
        services = [selected_service]
        incidents = (
            [selected_incident]
            if selected_incident
            else incident_repo.get_service_incidents(payload.service_id, limit=10)
        )
    elif selected_incident:
        service = service_repo.get_service(selected_incident.get("service_id", ""))
        services = [service] if service else []
        incidents = [selected_incident]
    else:
        services = service_repo.list_services()
        incidents = incident_repo.get_incidents(limit=20)

    service_context = []
    for service in services[:25]:
        latest = mon_repo.get_latest_record(service.get("service_id", ""))
        latest_context = None
        if latest:
            latest_context = {
                key: latest[key]
                for key in (
                    "timestamp",
                    "response_time",
                    "status_code",
                    "availability",
                    "error",
                    "error_rate",
                    "anomaly",
                    "anomaly_score",
                    "risk_score",
                    "risk_level",
                )
                if key in latest
            }
        service_context.append({
            "service_id": service.get("service_id"),
            "service_name": service.get("service_name"),
            "is_active": service.get("is_active"),
            "response_time_threshold": service.get("response_time_threshold"),
            "error_threshold": service.get("error_threshold"),
            "tags": service.get("tags", []),
            "latest_telemetry": latest_context,
        })

    incident_context = [
        {
            key: incident[key]
            for key in (
                "incident_id",
                "service_id",
                "service_name",
                "severity",
                "status",
                "trigger_reason",
                "created_at",
                "updated_at",
                "anomaly_score",
                "risk_score",
                "risk_level",
                "metrics_snapshot",
                "resolution_notes",
            )
            if key in incident
        }
        for incident in incidents[:20]
    ]

    context = {
        "application_scope": [
            "This application monitors registered services and stores service health telemetry.",
            "Telemetry can include response time, HTTP status, availability, error rate, and anomaly/risk scores.",
            (
                "Isolation Forest features are response time, error rate, availability, normalized HTTP status, "
                "timeout, request success, rolling response-time/error-rate averages, and their change ratios."
            ),
            (
                "Anomaly scores are clamped to 0-1 using 0.5 minus the model decision score; scores at or above "
                "0.5 are flagged. This is a relative anomaly measure, not a probability."
            ),
            (
                "Risk scores combine response time (25%), response-time trend (15%), error rate (20%), "
                "error-rate trend (10%), availability (15%), timeouts (10%), and recent anomaly count (5%). "
                "Risk levels are LOW (up to 25), MEDIUM (above 25 up to 50), HIGH (above 50 up to 75), "
                "and CRITICAL (above 75); "
                "the score is a heuristic, not a calibrated probability."
            ),
            "The application tracks incidents and uses these models to detect anomalies and prioritize operational risk.",
        ],
        "service_count": len(services),
        "services": service_context,
        "incidents": incident_context,
        "data_limitations": (
            "Only the services and incidents listed here, and their latest telemetry, "
            "are available for this answer. Missing values were not supplied."
        ),
    }
    source_ids = list(dict.fromkeys(
        [service["service_id"] for service in service_context if service.get("service_id")]
        + [incident["incident_id"] for incident in incident_context if incident.get("incident_id")]
    ))
    return context, source_ids


def _is_monitoring_question(query, context, has_selected_context):
    if _MONITORING_QUESTION_TERMS.search(query) or _CONTEXTUAL_REFERENCES.search(query):
        return True

    query_lower = query.casefold()
    known_names = [
        str(value).casefold()
        for service in context["services"]
        for value in (service.get("service_id"), service.get("service_name"))
        if value
    ]
    known_names.extend(
        str(incident["incident_id"]).casefold()
        for incident in context["incidents"]
        if incident.get("incident_id")
    )
    if any(name in query_lower for name in known_names):
        return True

    if has_selected_context:
        return bool(re.search(r"\b(?:this|that|it|they|them)\b", query, re.IGNORECASE))

    return False


@router.post("/chat", response_model=AIChatResponse)
async def ai_assistant_chat(payload: AIChatRequest):
    """
    Interactive AI Monitoring Assistant.
    Answers natural language questions about monitored services, incidents, latency trends, and root causes.
    """
    context, source_ids = _build_chat_context(payload)
    if not _is_monitoring_question(
        payload.query,
        context,
        has_selected_context=bool(payload.service_id or payload.incident_id),
    ):
        return AIChatResponse(
            query=payload.query,
            answer=_OUT_OF_SCOPE_ANSWER,
            suggested_actions=[],
            confidence="HIGH",
            provider="Context filter",
        )

    try:
        provider = get_ai_provider()
        answer = await provider.chat([
            {"role": "system", "content": MONITORING_ASSISTANT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {payload.query}\n\n"
                    "Authoritative application context (JSON):\n"
                    f"{json.dumps(context, ensure_ascii=True, default=str)}"
                ),
            },
        ])
    except AIProviderError as exc:
        logger.warning(
            "AI chat provider request failed.",
            extra={"provider": exc.provider, "recoverable": exc.recoverable},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not answer or not answer.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The configured AI provider returned an empty answer.",
        )

    return AIChatResponse(
        query=payload.query,
        answer=answer.strip(),
        sources=source_ids,
        suggested_actions=[],
        confidence="MEDIUM",
        provider=provider.provider_name,
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
