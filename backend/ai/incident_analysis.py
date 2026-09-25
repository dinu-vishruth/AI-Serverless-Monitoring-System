"""
AI incident analysis pipeline — orchestrates LLM-based incident explanation.

This module:
1. Gathers structured evidence from monitoring data, ML analysis, and CloudWatch.
2. Sends the evidence to the configured LLM provider.
3. Parses and stores the AI analysis result.
4. Provides graceful fallback if the AI service is unavailable.
"""

import json
from typing import Optional
from datetime import datetime, timezone

from backend.ai.provider import get_ai_provider, AIProviderError
from backend.ai.prompts import (
    INCIDENT_ANALYSIS_SYSTEM_PROMPT,
    build_incident_analysis_prompt,
)
from backend.database.ai_repository import AIAnalysisRepository
from backend.utils.logger import get_logger
from backend.utils.validators import sanitize_log_content

logger = get_logger(__name__)


async def analyze_incident(
    incident: dict,
    current_metrics: dict,
    historical_metrics: Optional[dict] = None,
    ml_analysis: Optional[dict] = None,
    cloudwatch_evidence: Optional[list[str]] = None,
) -> dict:
    """
    Performs AI-powered incident analysis.

    Args:
        incident: The incident record.
        current_metrics: Current monitoring metrics.
        historical_metrics: Historical baseline metrics.
        ml_analysis: ML anomaly detection / risk results.
        cloudwatch_evidence: Sanitized CloudWatch log snippets.

    Returns:
        AI analysis result dict. If AI is unavailable, returns a
        fallback result so monitoring continues.
    """
    service_name = current_metrics.get(
        "service_name", incident.get("service_name", "Unknown Service")
    )
    service_id = incident.get("service_id", "")
    incident_id = incident.get("incident_id", "")

    # Build evidence payload
    evidence = {
        "service": service_name,
        "current_metrics": {
            "response_time": current_metrics.get("response_time"),
            "status_code": current_metrics.get("status_code"),
            "error_rate": current_metrics.get("error_rate"),
            "availability": current_metrics.get("availability"),
        },
        "trigger_reason": incident.get("trigger_reason", ""),
    }

    if historical_metrics:
        evidence["historical_baseline"] = {
            "average_response_time": historical_metrics.get("avg_response_time"),
            "average_error_rate": historical_metrics.get("avg_error_rate"),
        }

    if ml_analysis:
        evidence["ml_analysis"] = {
            "anomaly": ml_analysis.get("anomaly", False),
            "anomaly_score": ml_analysis.get("anomaly_score", 0),
            "risk_level": ml_analysis.get("risk_level", "UNKNOWN"),
        }

    if cloudwatch_evidence:
        # Sanitize before sending to external AI
        evidence["cloudwatch_evidence"] = [
            sanitize_log_content(log, max_length=500) for log in cloudwatch_evidence[:5]
        ]

    # Build prompt
    user_prompt = build_incident_analysis_prompt(evidence)

    # Call AI provider
    try:
        provider = get_ai_provider()
        ai_response = await provider.analyze(
            system_prompt=INCIDENT_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Validate response structure
        analysis_result = _validate_ai_response(ai_response)

    except AIProviderError as e:
        logger.warning(
            f"AI provider unavailable for incident {incident_id}: {e}",
            extra={"incident_id": incident_id, "action": "ai_analysis_fallback"},
        )
        analysis_result = _fallback_analysis(incident, current_metrics, ml_analysis)

    except Exception as e:
        logger.error(
            f"Unexpected error during AI analysis: {e}",
            extra={"incident_id": incident_id, "action": "ai_analysis_error"},
        )
        analysis_result = _fallback_analysis(incident, current_metrics, ml_analysis)

    # Enrich with metadata
    analysis_result["incident_id"] = incident_id
    analysis_result["service_id"] = service_id
    analysis_result["timestamp"] = datetime.now(timezone.utc).isoformat()
    analysis_result["anomaly"] = ml_analysis.get("anomaly", False) if ml_analysis else False
    analysis_result["anomaly_score"] = ml_analysis.get("anomaly_score", 0) if ml_analysis else 0
    analysis_result["risk_score"] = incident.get("risk_score", 0)
    analysis_result["risk_level"] = incident.get("risk_level", "UNKNOWN")

    # Store in DynamoDB
    try:
        repo = AIAnalysisRepository()
        stored = repo.store_analysis(analysis_result)
        analysis_result["analysis_id"] = stored.get("analysis_id")
    except Exception as e:
        logger.error(f"Failed to store AI analysis: {e}")

    return analysis_result


def _validate_ai_response(response: dict) -> dict:
    """Validates and normalizes the AI response structure."""
    required_fields = [
        "incident_summary",
        "observed_facts",
        "possible_causes",
        "impact",
        "recommended_actions",
        "confidence",
    ]

    result = {}
    for field in required_fields:
        value = response.get(field)
        if field == "confidence":
            result[field] = value if value in ("low", "medium", "high") else "low"
        elif isinstance(value, list):
            result[field] = [str(v) for v in value]
        elif isinstance(value, str):
            result[field] = value if field == "incident_summary" else [value]
        else:
            result[field] = [] if field != "incident_summary" else "Analysis completed."

    return result


def _fallback_analysis(
    incident: dict,
    current_metrics: dict,
    ml_analysis: Optional[dict] = None,
) -> dict:
    """
    Generates a rule-based fallback analysis when AI is unavailable.
    This ensures monitoring continues even if the LLM service fails.
    """
    facts = []
    causes = []
    impact = []
    actions = []

    rt = current_metrics.get("response_time", 0)
    status = current_metrics.get("status_code", 200)
    error_rate = current_metrics.get("error_rate", 0)
    availability = current_metrics.get("availability", 1.0)

    if rt > 3000:
        facts.append(f"Response time is elevated at {rt}ms.")
        causes.append("Possible backend processing bottleneck or resource contention.")
        actions.append("Review recent Lambda execution logs for slow operations.")

    if status >= 500:
        facts.append(f"HTTP {status} server errors detected.")
        causes.append("Application error or upstream dependency failure.")
        actions.append("Check application logs for unhandled exceptions.")

    if error_rate > 0.1:
        facts.append(f"Error rate is {error_rate:.1%}.")
        impact.append("Users may experience failed requests.")
        actions.append("Investigate recent code deployments or configuration changes.")

    if availability < 0.95:
        facts.append(f"Availability decreased to {availability:.1%}.")
        impact.append("Service reliability is below acceptable levels.")
        actions.append("Check infrastructure health and scaling configuration.")

    if not facts:
        facts.append("Monitoring threshold crossed.")

    if not actions:
        actions.append("Review service logs and recent changes.")

    return {
        "incident_summary": (
            f"AI analysis temporarily unavailable. "
            f"Rule-based assessment: {incident.get('trigger_reason', 'Monitoring alert triggered')}."
        ),
        "observed_facts": facts,
        "possible_causes": causes if causes else ["Further investigation required."],
        "impact": impact if impact else ["Potential user impact — severity depends on duration."],
        "recommended_actions": actions,
        "confidence": "low",
    }
