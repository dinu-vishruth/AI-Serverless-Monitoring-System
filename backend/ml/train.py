"""
ML training module — trains an Isolation Forest model on historical monitoring data.

The Isolation Forest is an unsupervised anomaly detection algorithm.
It works by randomly partitioning data — anomalies require fewer partitions
to isolate, so they receive higher anomaly scores.

No labelled data is required. The model learns "normal" behavior from
historical health-check records and flags observations that deviate
significantly from the learned distribution.

Anomaly Score Interpretation:
  - The raw Isolation Forest `decision_function` output ranges from negative
    (anomalous) to positive (normal).
  - We remap this to a 0–1 "anomaly_score" where:
      0.0 = definitely normal
      1.0 = definitely anomalous
  - A threshold of 0.5 is used by default to classify anomaly vs. normal.
  - This score is NOT a calibrated probability of failure. It is a relative
    measure of how unusual the observation is compared to training data.
"""

from sklearn.ensemble import IsolationForest
import numpy as np

from backend.ml.preprocessing import (
    records_to_dataframe,
    add_derived_features,
    extract_features,
    validate_records,
)
from backend.ml.model_manager import ModelManager
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Minimum records required for meaningful training
MIN_TRAINING_SAMPLES = 20


def train_model(
    service_id: str,
    records: list[dict],
    contamination: float | None = None,
) -> dict:
    """
    Trains an Isolation Forest model on historical monitoring records.

    Args:
        service_id: The service to train for.
        records: Historical monitoring records.
        contamination: Expected proportion of anomalies (0–0.5).
                        Defaults to the ML_CONTAMINATION config value.

    Returns:
        Training result metadata including sample count and status.
    """
    settings = get_settings()
    if contamination is None:
        contamination = settings.ml_contamination

    # Validate and clean records
    valid_records = [r for r in validate_records(records) if r["service_id"] == service_id]

    if len(valid_records) < MIN_TRAINING_SAMPLES:
        logger.warning(
            f"Insufficient training data for {service_id}: "
            f"{len(valid_records)} records (need {MIN_TRAINING_SAMPLES})",
            extra={"service_id": service_id, "action": "train_model"},
        )
        return {
            "status": "insufficient_data",
            "service_id": service_id,
            "samples": len(valid_records),
            "required": MIN_TRAINING_SAMPLES,
        }

    # Convert to feature matrix
    df = records_to_dataframe(valid_records)
    df = add_derived_features(df)
    features = extract_features(df)

    logger.info(
        f"Training Isolation Forest for {service_id} with {len(features)} samples",
        extra={"service_id": service_id, "action": "train_model"},
    )

    # Train Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    split = max(16, int(len(features) * 0.8))
    training, validation = features[:split], features[split:]
    model.fit(training)
    scores = model.decision_function(validation)
    if not len(scores) or not np.isfinite(scores).all():
        return {"status": "evaluation_failed", "service_id": service_id}
    evaluation = {
        "method": "chronological_holdout_unlabeled",
        "training_count": len(training), "validation_count": len(validation),
        "holdout_anomaly_rate": float(np.mean(scores < 0)),
        "mean_decision_score": float(np.mean(scores)),
        "limitations": "Unlabeled data; accuracy, precision and recall cannot be calculated.",
    }
    if evaluation["holdout_anomaly_rate"] >= .9:
        return {"status": "evaluation_failed", "service_id": service_id, "evaluation": evaluation}

    # Save model
    manager = ModelManager()
    model_path = manager.save_model(service_id, model, len(features), evaluation=evaluation)

    return {
        "status": "trained",
        "service_id": service_id,
        "samples": len(features),
        "model_path": model_path,
        "contamination": contamination,
        "metadata": manager.get_metadata(service_id),
    }


def retrain_service(service_id, records):
    """Record every training attempt without replacing a failed candidate."""
    from backend.database.service_repository import ServiceRepository
    from backend.database.concurrency import mutate
    from backend.lifecycle import utcnow
    result = {"status": "failed", "service_id": service_id}
    try:
        result = train_model(service_id, records)
        return result
    finally:
        attempt = {k: v for k, v in result.items() if k != "model_path"}
        attempt["attempted_at"] = utcnow()
        mutate(ServiceRepository().table, {"service_id": service_id}, lambda s: s.update(last_training_result=attempt))
