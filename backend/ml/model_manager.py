"""
ML model manager — handles model persistence (save/load).

Models are stored as joblib files in the configured ML_MODEL_PATH directory.
Each service gets its own model file: {service_id}_isolation_forest.joblib
"""

import os
import json
import joblib
from datetime import datetime, timezone
from typing import Optional, Any
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ModelManager:
    """Manages ML model lifecycle — save, load, and metadata tracking."""

    def __init__(self):
        settings = get_settings()
        self.model_dir = settings.ml_model_path
        os.makedirs(self.model_dir, exist_ok=True)

    def _model_path(self, service_id: str) -> str:
        """Returns the file path for a service's model."""
        safe_id = service_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.model_dir, f"{safe_id}_isolation_forest.joblib")

    def _metadata_path(self, service_id: str) -> str:
        """Returns the file path for a model's metadata."""
        safe_id = service_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.model_dir, f"{safe_id}_metadata.json")

    def save_model(self, service_id: str, model: Any, training_samples: int) -> str:
        """
        Saves a trained model and its metadata.

        Returns:
            The file path where the model was saved.
        """
        path = self._model_path(service_id)
        joblib.dump(model, path)

        metadata = {
            "service_id": service_id,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_samples": training_samples,
            "model_type": "IsolationForest",
            "model_path": path,
        }
        with open(self._metadata_path(service_id), "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(
            f"Saved model for {service_id} ({training_samples} samples)",
            extra={"service_id": service_id, "action": "save_model"},
        )
        return path

    def load_model(self, service_id: str) -> Optional[Any]:
        """Loads a previously trained model. Returns None if no model exists."""
        path = self._model_path(service_id)
        if not os.path.exists(path):
            logger.info(
                f"No model found for {service_id}",
                extra={"service_id": service_id, "action": "load_model"},
            )
            return None

        model = joblib.load(path)
        logger.info(
            f"Loaded model for {service_id}",
            extra={"service_id": service_id, "action": "load_model"},
        )
        return model

    def get_metadata(self, service_id: str) -> Optional[dict]:
        """Returns model metadata (training date, sample count, etc.)."""
        meta_path = self._metadata_path(service_id)
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r") as f:
            return json.load(f)

    def model_exists(self, service_id: str) -> bool:
        """Checks whether a trained model exists for the service."""
        return os.path.exists(self._model_path(service_id))

    def should_retrain(self, service_id: str, current_record_count: int) -> bool:
        """
        Determines whether the model should be retrained.
        Retrains if no model exists or if significantly more data is available.
        """
        metadata = self.get_metadata(service_id)
        if metadata is None:
            return current_record_count >= 20  # Need minimum data to train

        settings = get_settings()
        trained_samples = metadata.get("training_samples", 0)
        new_samples = current_record_count - trained_samples

        return new_samples >= settings.ml_retrain_threshold

    def delete_model(self, service_id: str) -> bool:
        """Deletes a model and its metadata."""
        model_path = self._model_path(service_id)
        meta_path = self._metadata_path(service_id)

        deleted = False
        for path in (model_path, meta_path):
            if os.path.exists(path):
                os.remove(path)
                deleted = True

        return deleted
