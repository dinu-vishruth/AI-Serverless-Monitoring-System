"""
Health Checker Lambda — checks the health of configured services.

Triggered by Amazon EventBridge on a schedule.

For each active service:
1. Sends an HTTP request to the configured URL.
2. Records response time, status code, availability.
3. Stores the result in DynamoDB (MonitoringData).
4. Triggers anomaly detection and risk analysis.
5. Creates incidents when thresholds are crossed.
6. Sends SNS alerts for critical issues.
"""

import json
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional
import urllib.request
import urllib.error
import ssl

from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.database.incident_repository import IncidentRepository
from backend.ml.predict import predict_anomaly
from backend.ml.risk_analyzer import calculate_risk, compute_historical_metrics
from backend.ml.train import train_model
from backend.ml.model_manager import ModelManager
from backend.ai.incident_analysis import analyze_incident
from backend.utils.config import get_settings
from backend.utils.logger import get_logger
from backend.utils.validators import generate_incident_id

logger = get_logger(__name__)


def handler(event, context):
    """Lambda entry point — triggered by EventBridge."""
    logger.info("Health checker invoked", extra={"action": "health_check_start"})

    try:
        service_repo = ServiceRepository()
        services = service_repo.get_active_services()

        if not services:
            logger.info("No active services to check")
            return {"statusCode": 200, "body": json.dumps({"message": "No services configured"})}

        results = []
        for service in services:
            try:
                result = check_service(service)
                results.append(result)
            except Exception as e:
                logger.error(f"Error checking service {service.get('service_id')}: {e}")
                results.append({
                    "service_id": service.get("service_id"),
                    "error": str(e),
                    "status": "check_failed",
                })

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Checked {len(results)} services",
                "results": results,
            }, default=str),
        }

    except Exception as e:
        logger.error(f"Health checker failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def check_service(service: dict) -> dict:
    """
    Performs a health check on a single service and runs the AI pipeline.
    """
    service_id = service["service_id"]
    url = service["url"]
    method = service.get("http_method", "GET")
    expected_status = int(service.get("expected_status_code", 200))
    timeout_seconds = int(service.get("timeout", 10))

    logger.info(
        f"Checking service: {service_id} ({url})",
        extra={"service_id": service_id, "action": "check_service"},
    )

    # Perform the HTTP check
    check_result = perform_http_check(url, method, expected_status, timeout_seconds)

    # Build monitoring record
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "service_id": service_id,
        "service_name": service.get("service_name", ""),
        "url": url,
        "timestamp": now,
        "status_code": check_result["status_code"],
        "response_time": check_result["response_time"],
        "availability": check_result["availability"],
        "error": check_result["error"],
        "error_rate": check_result["error_rate"],
        "timeout": check_result["timeout"],
        "request_success": check_result["request_success"],
    }

    # Store in DynamoDB
    monitoring_repo = MonitoringRepository()
    monitoring_repo.store_monitoring_record(record)

    # Run AI intelligence pipeline
    ai_result = run_ai_pipeline(service, record, monitoring_repo)
    record["ai_analysis"] = ai_result

    return record


def perform_http_check(
    url: str, method: str = "GET", expected_status: int = 200, timeout: int = 10
) -> dict:
    """
    Performs an HTTP health check and returns metrics.
    Uses urllib to avoid external dependencies in Lambda.
    """
    start_time = time.time()
    result = {
        "status_code": 0,
        "response_time": 0,
        "availability": 0,
        "error": 1,
        "error_rate": 1.0,
        "timeout": 0,
        "request_success": 0,
    }

    try:
        # Create SSL context that doesn't verify for flexibility
        ctx = ssl.create_default_context()

        request = urllib.request.Request(url, method=method.upper())
        request.add_header("User-Agent", "ServerlessMonitor/1.0")

        response = urllib.request.urlopen(request, timeout=timeout, context=ctx)
        elapsed = (time.time() - start_time) * 1000  # ms

        result["status_code"] = response.status
        result["response_time"] = round(elapsed, 2)
        result["request_success"] = 1 if response.status == expected_status else 0
        result["availability"] = 1 if response.status < 500 else 0
        result["error"] = 0 if response.status == expected_status else 1
        result["error_rate"] = 0.0 if response.status == expected_status else 1.0

    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start_time) * 1000
        result["status_code"] = e.code
        result["response_time"] = round(elapsed, 2)
        result["availability"] = 0 if e.code >= 500 else 1
        result["error"] = 1
        result["error_rate"] = 1.0

    except urllib.error.URLError as e:
        elapsed = (time.time() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        if "timed out" in str(e.reason).lower():
            result["timeout"] = 1
        result["error"] = 1
        result["error_rate"] = 1.0

    except TimeoutError:
        elapsed = (time.time() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["timeout"] = 1
        result["error"] = 1
        result["error_rate"] = 1.0

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = 1
        result["error_rate"] = 1.0
        logger.warning(f"Unexpected error checking {url}: {e}")

    return result


def run_ai_pipeline(
    service: dict, record: dict, monitoring_repo: MonitoringRepository
) -> dict:
    """
    Runs the AI intelligence pipeline:
    1. Retrieve historical data
    2. Retrain model if needed
    3. Anomaly detection
    4. Risk analysis
    5. Incident creation (if warranted)
    6. AI incident analysis (if HIGH/CRITICAL)
    """
    service_id = service["service_id"]
    ai_result = {"anomaly": False, "risk_level": "LOW"}

    try:
        # 1. Get historical data
        historical = monitoring_repo.get_historical_records(service_id, hours=24)

        # 2. Check if model needs retraining
        model_manager = ModelManager()
        record_count = len(historical)
        if model_manager.should_retrain(service_id, record_count):
            logger.info(f"Retraining model for {service_id}")
            train_result = train_model(service_id, historical)
            logger.info(f"Training result: {train_result.get('status')}")

        # 3. Anomaly detection
        anomaly_result = predict_anomaly(
            service_id=service_id,
            record=record,
            historical_records=historical[-20:],  # Recent window for derived features
        )
        ai_result.update(anomaly_result)

        # 4. Risk analysis
        hist_metrics = compute_historical_metrics(historical)
        risk_result = calculate_risk(
            current_metrics=record,
            historical_metrics=hist_metrics,
            service_config=service,
        )
        ai_result["risk_score"] = risk_result["risk_score"]
        ai_result["risk_level"] = risk_result["risk_level"]
        ai_result["risk_factors"] = risk_result["factors"]

        # 5. Check if incident should be created
        should_create, trigger_reason = _should_create_incident(
            record, anomaly_result, risk_result, service
        )

        if should_create:
            incident = _create_incident(
                service, record, anomaly_result, risk_result, trigger_reason
            )
            ai_result["incident_id"] = incident.get("incident_id")

            # 6. AI analysis for HIGH/CRITICAL incidents
            if risk_result["risk_level"] in ("HIGH", "CRITICAL"):
                try:
                    loop = asyncio.new_event_loop()
                    analysis = loop.run_until_complete(
                        analyze_incident(
                            incident=incident,
                            current_metrics=record,
                            historical_metrics=hist_metrics,
                            ml_analysis=anomaly_result,
                        )
                    )
                    loop.close()
                    ai_result["ai_analysis"] = analysis

                    # Send intelligent SNS alert
                    _send_intelligent_alert(incident, record, risk_result, analysis)
                except Exception as e:
                    logger.warning(f"AI analysis failed, sending basic alert: {e}")
                    _send_basic_alert(incident, record)
            else:
                # Send basic alert for MEDIUM incidents
                _send_basic_alert(incident, record)

        # Check for incident resolution
        elif risk_result["risk_level"] == "LOW" and not anomaly_result.get("anomaly"):
            _check_incident_resolution(service_id)

    except Exception as e:
        logger.error(
            f"AI pipeline error for {service_id}: {e}",
            extra={"service_id": service_id, "action": "ai_pipeline_error"},
        )
        # AI pipeline failure should NOT stop monitoring

    return ai_result


def _should_create_incident(
    record: dict, anomaly: dict, risk: dict, service: dict
) -> tuple[bool, str]:
    """Determines whether an incident should be created."""
    reasons = []

    # Service unavailable
    if record.get("availability", 1) == 0:
        reasons.append("Service unavailable")

    # High risk
    if risk["risk_level"] in ("HIGH", "CRITICAL"):
        reasons.append(f"Risk level: {risk['risk_level']}")

    # Significant anomaly
    if anomaly.get("anomaly") and anomaly.get("anomaly_score", 0) >= 0.6:
        reasons.append(f"Anomaly detected (score: {anomaly['anomaly_score']:.2f})")

    # Error threshold crossed
    error_threshold = float(service.get("error_threshold", 0.1))
    if float(record.get("error_rate", 0)) > error_threshold:
        reasons.append(f"Error rate above threshold ({record.get('error_rate'):.2%})")

    # Response time threshold crossed
    rt_threshold = float(service.get("response_time_threshold", 5000))
    if float(record.get("response_time", 0)) > rt_threshold:
        reasons.append(f"Response time above threshold ({record.get('response_time')}ms)")

    if not reasons:
        return False, ""

    # Check if there's already an open incident
    incident_repo = IncidentRepository()
    existing = incident_repo.get_open_incident_for_service(record["service_id"])
    if existing:
        logger.info(f"Open incident already exists: {existing['incident_id']}")
        return False, ""

    return True, " | ".join(reasons)


def _create_incident(
    service: dict, record: dict, anomaly: dict, risk: dict, trigger_reason: str
) -> dict:
    """Creates a new incident in DynamoDB."""
    incident_repo = IncidentRepository()

    # Determine severity from risk level
    severity = risk["risk_level"]
    if record.get("availability", 1) == 0:
        severity = "CRITICAL"

    incident = {
        "incident_id": generate_incident_id(),
        "service_id": service["service_id"],
        "service_name": service.get("service_name", ""),
        "severity": severity,
        "status": "OPEN",
        "trigger_reason": trigger_reason,
        "anomaly_score": anomaly.get("anomaly_score", 0),
        "risk_score": risk.get("risk_score", 0),
        "risk_level": risk.get("risk_level", "MEDIUM"),
        "metrics_snapshot": {
            "response_time": record.get("response_time"),
            "status_code": record.get("status_code"),
            "error_rate": record.get("error_rate"),
            "availability": record.get("availability"),
        },
    }

    created = incident_repo.create_incident(incident)
    logger.info(
        f"Created incident {created['incident_id']} for {service['service_id']}",
        extra={"incident_id": created["incident_id"], "action": "create_incident"},
    )
    return created


def _check_incident_resolution(service_id: str):
    """Resolves open incidents when service returns to normal."""
    incident_repo = IncidentRepository()
    open_incident = incident_repo.get_open_incident_for_service(service_id)
    if open_incident:
        incident_repo.update_incident_status(open_incident["incident_id"], "RESOLVED")
        logger.info(
            f"Resolved incident {open_incident['incident_id']}",
            extra={
                "incident_id": open_incident["incident_id"],
                "action": "resolve_incident",
            },
        )


def _send_intelligent_alert(
    incident: dict, record: dict, risk: dict, analysis: dict
):
    """Sends an enhanced SNS notification with AI insights."""
    settings = get_settings()
    if not settings.sns_topic_arn or not settings.sns_alert_enabled:
        logger.info("SNS not configured, skipping alert")
        return

    try:
        import boto3

        sns = boto3.client("sns", region_name=settings.aws_region)

        summary = analysis.get("incident_summary", "Incident detected")
        actions = analysis.get("recommended_actions", [])
        actions_text = "\n".join(f"  • {a}" for a in actions[:3]) if actions else "  • Review service logs"

        message = (
            f"🚨 {risk['risk_level']}-RISK INCIDENT DETECTED\n\n"
            f"Service: {incident.get('service_name', incident.get('service_id'))}\n"
            f"Incident: {incident['incident_id']}\n\n"
            f"━━━ Current Metrics ━━━\n"
            f"Response Time: {record.get('response_time', 'N/A')}ms\n"
            f"Error Rate: {float(record.get('error_rate', 0)):.1%}\n"
            f"Availability: {float(record.get('availability', 0)):.1%}\n"
            f"Status Code: {record.get('status_code', 'N/A')}\n\n"
            f"━━━ AI Risk Analysis ━━━\n"
            f"Risk Score: {risk.get('risk_score', 'N/A')}/100\n"
            f"Risk Level: {risk['risk_level']}\n\n"
            f"━━━ AI Summary ━━━\n"
            f"{summary}\n\n"
            f"━━━ Recommended Investigation ━━━\n"
            f"{actions_text}\n\n"
            f"Confidence: {analysis.get('confidence', 'N/A')}\n"
            f"Time: {incident.get('created_at', 'N/A')}"
        )

        sns.publish(
            TopicArn=settings.sns_topic_arn,
            Subject=f"[{risk['risk_level']}] {incident.get('service_name', 'Service')} - {incident['incident_id']}",
            Message=message,
        )
        logger.info(f"Sent intelligent SNS alert for {incident['incident_id']}")

    except Exception as e:
        logger.error(f"Failed to send SNS alert: {e}")


def _send_basic_alert(incident: dict, record: dict):
    """Sends a basic SNS notification (fallback when AI is unavailable)."""
    settings = get_settings()
    if not settings.sns_topic_arn or not settings.sns_alert_enabled:
        return

    try:
        import boto3

        sns = boto3.client("sns", region_name=settings.aws_region)

        message = (
            f"⚠️ INCIDENT DETECTED\n\n"
            f"Service: {incident.get('service_name', incident.get('service_id'))}\n"
            f"Incident: {incident['incident_id']}\n"
            f"Severity: {incident.get('severity', 'UNKNOWN')}\n"
            f"Reason: {incident.get('trigger_reason', 'N/A')}\n\n"
            f"Response Time: {record.get('response_time', 'N/A')}ms\n"
            f"Status Code: {record.get('status_code', 'N/A')}\n"
            f"Error Rate: {float(record.get('error_rate', 0)):.1%}\n"
        )

        sns.publish(
            TopicArn=settings.sns_topic_arn,
            Subject=f"[{incident.get('severity', 'ALERT')}] {incident.get('service_name', 'Service')} Alert",
            Message=message,
        )

    except Exception as e:
        logger.error(f"Failed to send basic SNS alert: {e}")
