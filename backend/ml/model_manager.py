"""Immutable versioned ML bundles with atomic active metadata publication."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
import boto3
import joblib
import sklearn
from backend.utils.config import get_settings

class ModelManager:
    def __init__(self):
        self.settings = get_settings()
        self.model_dir = self.settings.ml_model_path
        Path(self.model_dir).mkdir(parents=True, exist_ok=True)
    def safe_id(self, sid):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', sid): raise ValueError('Invalid service ID')
        return sid
    def _metadata_path(self, sid): return str(Path(self.model_dir) / f'{self.safe_id(sid)}_metadata.json')
    def _model_path(self, sid):
        metadata = self.get_metadata(sid)
        return str(Path(self.model_dir) / (metadata['artifact'] if metadata else f'{self.safe_id(sid)}_missing.joblib'))
    def get_metadata(self, sid):
        self.safe_id(sid)
        if self.settings.model_bucket:
            try:
                obj = boto3.client('s3', region_name=self.settings.aws_region).get_object(Bucket=self.settings.model_bucket, Key=f'{sid}/active.json')
                return json.loads(obj['Body'].read())
            except Exception as exc:
                if getattr(exc, 'response', {}).get('Error', {}).get('Code') in {'NoSuchKey', '404'}: return None
                raise
        path = Path(self._metadata_path(sid))
        return json.loads(path.read_text()) if path.exists() else None
    def save_model(self, sid, model, training_samples, evaluation=None):
        from backend.ml.preprocessing import ALL_FEATURES
        self.safe_id(sid)
        version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:12]
        artifact = f'{sid}_{version}.joblib'
        path = Path(self.model_dir) / artifact
        joblib.dump(model, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # Reload and exercise serialization before promoting the artifact.
        candidate = joblib.load(path)
        if not hasattr(candidate, 'decision_function'): raise ValueError('Invalid model artifact')
        metadata = dict(service_id=sid, version=version, trained_at=datetime.now(timezone.utc).isoformat(),
            training_samples=training_samples, model_type='IsolationForest', artifact=artifact, sha256=digest,
            features=ALL_FEATURES, feature_schema_version=2, sklearn_version=sklearn.__version__,
            threshold=self.settings.ml_anomaly_threshold, evaluation=evaluation or {}, status='active')
        if self.settings.model_bucket:
            s3 = boto3.client('s3', region_name=self.settings.aws_region)
            key = f'{sid}/{artifact}'
            s3.upload_file(str(path), self.settings.model_bucket, key)
            metadata['artifact_key'] = key
            s3.put_object(Bucket=self.settings.model_bucket, Key=f'{sid}/versions/{version}.json', Body=json.dumps(metadata).encode(), ContentType='application/json')
            # Publishing the pointer is the final step; failed training keeps previous model.
            s3.put_object(Bucket=self.settings.model_bucket, Key=f'{sid}/active.json', Body=json.dumps(metadata).encode(), ContentType='application/json')
        temp = Path(self._metadata_path(sid) + '.' + uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(metadata), encoding='utf-8')
        os.replace(temp, self._metadata_path(sid))
        return str(path)
    def load_model(self, sid):
        metadata = self.get_metadata(sid)
        if not metadata: return None
        if metadata.get('feature_schema_version') != 2: return None
        if metadata.get('sklearn_version') != sklearn.__version__: return None
        path = Path(self.model_dir) / metadata['artifact']
        if not path.exists() and self.settings.model_bucket:
            temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            boto3.client('s3', region_name=self.settings.aws_region).download_file(self.settings.model_bucket, metadata['artifact_key'], str(temp))
            os.replace(temp, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']: raise ValueError('Model checksum mismatch')
        return joblib.load(path)
    def model_exists(self, sid): return self.get_metadata(sid) is not None
    def should_retrain(self, sid, count):
        metadata = self.get_metadata(sid)
        if not metadata: return count >= 20
        trained_at = datetime.fromisoformat(metadata['trained_at'].replace('Z', '+00:00'))
        stale = (datetime.now(timezone.utc) - trained_at).total_seconds() >= 86400
        return count >= 20 and (stale or count - metadata['training_samples'] >= self.settings.ml_retrain_threshold)
    def delete_model(self, sid):
        # Remove only the active pointer; retain immutable versions for audit/rollback.
        if self.settings.model_bucket:
            boto3.client('s3', region_name=self.settings.aws_region).delete_object(Bucket=self.settings.model_bucket, Key=f'{self.safe_id(sid)}/active.json')
        path = Path(self._metadata_path(sid))
        if path.exists(): path.unlink(); return True
        return False
