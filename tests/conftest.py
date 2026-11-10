"""All tests use isolated storage; never read developer credentials or telemetry."""
import pytest
from backend.utils import config
from backend.database import local


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    settings = config.Settings(_env_file=None, ENVIRONMENT="test", ML_MODEL_PATH=str(tmp_path / "models"),
        LOCAL_MONITORING_ENABLED=False, GROQ_API_KEY=None, GROQ_SECRET_ARN=None, ADMIN_TOKEN=None,
        ADMIN_SECRET_ARN=None, MODEL_BUCKET=None, SNS_TOPIC_ARN=None, ALLOW_PRIVATE_TARGETS=True)
    monkeypatch.setattr(config, "_settings", settings)
    monkeypatch.setattr(local, "DB_PATH", tmp_path / "test.sqlite3")
    return settings
