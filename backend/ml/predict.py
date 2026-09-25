"""
ML prediction module — uses a trained Isolation Forest to detect anomalies.

Anomaly Score Mapping:
  The Isolation Forest's `decision_function` returns raw scores where:
    - Negative values → more anomalous
    - Positive values → more normal

  We remap to a 0–1 scale using:
    anomaly_score = max(0, min(1, 0.5 - raw_score))

  Interpretation:
    0.0 – 0.3  → Likely normal
    0.3 – 0.5  → Borderline / uncertain
    0.5 – 0.7  → Likely anomalous
    0.7 – 1.0  → Highly anomalous

  IMPORTANT: This is a relative anomaly measure, NOT a calibrated probability.
"""

import numpy as np
from typing import Optional

from backend.ml.preprocessing import prepare_single_record
from backend.ml.model_manager import ModelManager
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Default threshold for classifying a record as anomalous
ANOMALY_THRESHOLD = 0.5


def predict_anomaly(
    service_id: str,
    record: dict,
    historical_records: Optional[list[dict]] = None,
    threshold: float = ANOMALY_THRESHOLD,
) -> dict:
    """
    Predicts whether a monitoring record is anomalous.

    Args:
        service_id: The service being checked.
        record: Current monitoring record.
        historical_records: Recent records for computing derived features.
        threshold: Anomaly score threshold (default 0.5).

    Returns:
        Dict with anomaly flag, score, and interpretation.
    """
    manager = ModelManager()
    model = manager.load_model(service_id)

    if model is None:
        logger.info(
            f"No trained model for {service_id}, skipping anomaly detection",
            extra={"service_id": service_id, "action": "predict_anomaly"},
        )
        return {
            "service_id": service_id,
            "timestamp": record.get("timestamp", ""),
            "anomaly": False,
            "anomaly_score": 0.0,
            "status": "no_model",
            "interpretation": "No trained model available. Anomaly detection skipped.",
        }

    # Prepare features
    features = prepare_single_record(record, historical_records)

    # Get raw prediction and decision function score
    prediction = model.predict(features)[0]       # 1 = normal, -1 = anomaly
    raw_score = model.decision_function(features)[0]

    # Remap to 0–1 scale (higher = more anomalous)
    anomaly_score = float(max(0.0, min(1.0, 0.5 - raw_score)))
    is_anomaly = anomaly_score >= threshold

    # Interpretation
    if anomaly_score >= 0.7:
        interpretation = "Highly anomalous — significant deviation from learned normal behavior."
    elif anomaly_score >= 0.5:
        interpretation = "Likely anomalous — notable deviation from normal patterns."
    elif anomaly_score >= 0.3:
        interpretation = "Borderline — some deviation detected, may warrant attention."
    else:
        interpretation = "Normal — within expected behavioral patterns."

    result = {
        "service_id": service_id,
        "timestamp": record.get("timestamp", ""),
        "anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 4),
        "raw_score": round(float(raw_score), 4),
        "threshold": threshold,
        "interpretation": interpretation,
        "status": "predicted",
    }

    logger.info(
        f"Anomaly prediction for {service_id}: "
        f"score={anomaly_score:.4f}, anomaly={is_anomaly}",
        extra={"service_id": service_id, "action": "predict_anomaly"},
    )

    return result
