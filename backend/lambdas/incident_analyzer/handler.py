"""
Incident Analyzer Lambda Handler.
Asynchronously processes newly created incidents with LLM explanation and root-cause analysis.
"""

import json
import asyncio
from backend.ai.incident_analysis import analyze_incident
from backend.database.incident_repository import IncidentRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.ml.risk_analyzer import compute_historical_metrics
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    """
    Handles async incident analysis.
    Triggered by EventBridge or SNS when an incident severity is HIGH or CRITICAL.
    """
    logger.info("Incident analyzer Lambda invoked")

    try:
        records = event.get("Records", [])
        if not records and "incident_id" in event:
            records = [{"body": json.dumps(event)}]

        incident_repo = IncidentRepository()
        mon_repo = MonitoringRepository()
        analyzed_count = 0

        for item in records:
            body = json.loads(item.get("body", "{}")) if "body" in item else item
            incident_id = body.get("incident_id")
            if not incident_id:
                continue

            incident = incident_repo.get_incident(incident_id)
            if not incident:
                logger.warning(f"Incident {incident_id} not found")
                continue

            service_id = incident.get("service_id")
            latest_record = mon_repo.get_latest_record(service_id) or {
                "service_id": service_id,
                "response_time": incident.get("metrics_snapshot", {}).get("response_time", 0),
                "status_code": incident.get("metrics_snapshot", {}).get("status_code", 200),
                "error_rate": incident.get("metrics_snapshot", {}).get("error_rate", 0),
                "availability": incident.get("metrics_snapshot", {}).get("availability", 1),
            }

            historical = mon_repo.get_historical_records(service_id, hours=24)
            hist_metrics = compute_historical_metrics(historical)

            ml_analysis = {
                "anomaly": True if incident.get("anomaly_score", 0) > 0.5 else False,
                "anomaly_score": incident.get("anomaly_score", 0),
                "risk_level": incident.get("risk_level", "HIGH"),
            }

            loop = asyncio.new_event_loop()
            analysis = loop.run_until_complete(
                analyze_incident(
                    incident=incident,
                    current_metrics=latest_record,
                    historical_metrics=hist_metrics,
                    ml_analysis=ml_analysis,
                )
            )
            loop.close()

            analyzed_count += 1
            logger.info(f"Completed AI analysis for incident {incident_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"analyzed_incidents": analyzed_count}),
        }
    except Exception as e:
        logger.error(f"Incident analyzer Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
