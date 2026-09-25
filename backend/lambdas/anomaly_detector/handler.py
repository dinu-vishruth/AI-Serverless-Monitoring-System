"""
Anomaly Detector Lambda Handler.
Triggered asynchronously by DynamoDB Streams, SQS, or EventBridge to evaluate new monitoring records.
"""

import json
from backend.ml.predict import predict_anomaly
from backend.ml.risk_analyzer import calculate_risk, compute_historical_metrics
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    """
    Evaluates batches of monitoring records for statistical or Isolation Forest anomalies.
    Can handle SQS, DynamoDB Streams, or direct invocation events.
    """
    logger.info("Anomaly detector Lambda invoked", extra={"records_count": len(event.get("Records", []))})
    
    mon_repo = MonitoringRepository()
    service_repo = ServiceRepository()
    processed_count = 0
    anomalies_detected = 0

    try:
        # If triggered by DynamoDB Stream or SQS
        records = event.get("Records", [])
        if not records and "service_id" in event:
            # Direct invocation format
            records = [{"body": json.dumps(event)}]

        for item in records:
            try:
                if "dynamodb" in item:
                    from boto3.dynamodb.types import TypeDeserializer
                    deserializer = TypeDeserializer()
                    record = {k: deserializer.deserialize(v) for k, v in item["dynamodb"].get("NewImage", {}).items()}
                elif "body" in item:
                    record = json.loads(item["body"])
                else:
                    record = item

                service_id = record.get("service_id")
                if not service_id:
                    continue

                service = service_repo.get_service(service_id)
                if not service:
                    continue

                historical = mon_repo.get_historical_records(service_id, hours=24)
                prediction = predict_anomaly(
                    service_id=service_id,
                    record=record,
                    historical_records=historical[-20:],
                )

                if prediction.get("anomaly"):
                    anomalies_detected += 1
                    logger.warning(
                        f"Anomaly detected for service {service_id}",
                        extra={
                            "service_id": service_id,
                            "anomaly_score": prediction.get("anomaly_score"),
                            "details": prediction.get("details"),
                        }
                    )

                processed_count += 1
            except Exception as item_err:
                logger.error(f"Error processing record: {item_err}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "processed": processed_count,
                "anomalies_detected": anomalies_detected,
            }),
        }
    except Exception as e:
        logger.error(f"Anomaly detector Lambda failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
