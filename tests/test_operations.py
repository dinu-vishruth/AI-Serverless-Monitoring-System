from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.operations import reliability
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.ml.train import train_model
from backend.ml.model_manager import ModelManager


def test_insufficient_data_is_unknown():
    metrics = reliability({}, [], [])
    assert metrics["availability_percentage"] is None
    assert metrics["mttr_seconds"] is None
    assert metrics["mtbf_seconds"] is None
    assert metrics["p95_ms"] is None
    assert metrics["slo_compliant"] is None


def test_percentiles_and_probe_budget():
    records = [dict(timestamp=f'{i:03}', response_time=i, request_success=1) for i in range(100)]
    metrics = reliability({}, records, [])
    assert metrics["p95_ms"] == pytest.approx(94.05)
    assert metrics["p99_ms"] == pytest.approx(98.01)
    assert metrics["error_budget_remaining_percentage"] == 100
    assert metrics["slo_compliant"] is True


def test_retrain_does_not_insert_fake_samples():
    s = ServiceRepository().create_service(dict(service_name="Empty", url="https://example.com"))
    response = TestClient(app).post(f'/api/v1/ai/retrain/{s["service_id"]}')
    assert response.status_code == 409
    assert MonitoringRepository().get_records(s["service_id"]) == []
    assert not ModelManager().model_exists(s["service_id"])


def test_auth_and_safe_runbooks(isolated_runtime):
    isolated_runtime.admin_token = "test-administrator-token"
    client = TestClient(app)
    assert client.get('/api/v1/services').status_code == 401
    headers = {"Authorization":"Bearer test-administrator-token"}
    assert client.get('/api/v1/services', headers=headers).status_code == 200
    assert client.post('/api/v1/incidents/missing/remediate', headers=headers, json={"action":"rm -rf /", "authorized":True}).status_code == 422
    assert client.post('/api/v1/incidents/missing/remediate', headers=headers, json={"action":"retry_health_check", "authorized":False}).status_code == 422


def test_unauthorized_response_has_exact_cors_headers(isolated_runtime):
    isolated_runtime.admin_token = "test-token"
    client = TestClient(app)
    response = client.get('/api/v1/services', headers={"Origin":"http://localhost:3000"})
    assert response.status_code == 401
    assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'
    response = client.get('/api/v1/services', headers={"Origin":"https://untrusted.example"})
    assert 'access-control-allow-origin' not in response.headers


def test_dependency_cycle_rejected_and_blast_radius():
    from backend.operations import dependency_map
    client = TestClient(app)
    root = client.post('/api/v1/services', json={"service_name":"Database health", "url":"https://example.com"}).json()
    child = client.post('/api/v1/services', json={"service_name":"Orders", "url":"https://example.com", "dependencies":[root['service_id']]}).json()
    assert client.put(f'/api/v1/services/{root["service_id"]}', json={"dependencies":[child['service_id']]}).status_code == 422
    ServiceRepository().update_service(root['service_id'], {"health_state":"CONFIRMED_INCIDENT"})
    graph = dependency_map()
    assert child['service_id'] in graph['unhealthy_dependencies'][0]['affected_services']


def test_updates_validate_bounds_and_private_targets(isolated_runtime):
    isolated_runtime.allow_private_targets = False
    client = TestClient(app)
    assert client.post('/api/v1/services', json={"service_name":"Bad", "url":"http://169.254.169.254/latest/meta-data"}).status_code == 422
    svc = client.post('/api/v1/services', json={"service_name":"Public", "url":"https://example.com"}).json()
    assert client.put(f'/api/v1/services/{svc["service_id"]}', json={"timeout":0}).status_code == 422


def test_demo_changes_actual_response(isolated_runtime):
    from backend.demo import handler
    isolated_runtime.demo_enabled = True
    client = TestClient(app)
    assert client.put('/api/v1/demo/mode', json={"mode":"HTTP_503"}).status_code == 200
    assert handler({}, None)["statusCode"] == 503
    assert client.put('/api/v1/demo/mode', json={"mode":"RECOVERY"}).status_code == 200
    assert handler({}, None)["statusCode"] == 200
