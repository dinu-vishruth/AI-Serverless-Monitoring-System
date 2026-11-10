from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.database.concurrency import mutate, Conflict, save_versioned
from backend.lambdas.health_checker.handler import check_service
from backend.lifecycle import process_observation, operator_transition


def service(**overrides):
    return ServiceRepository().create_service(dict(service_name="Payments", url="https://example.com/health", **overrides))


def observation(s, index, success=0, latency=100):
    return dict(service_id=s["service_id"], timestamp=(datetime.now(timezone.utc) + timedelta(seconds=index)).isoformat(),
        response_time=latency, status_code=200 if success else 503, request_success=success,
        availability=success, error=1-success, error_rate=float(1-success), timeout=0)


def process(s, index, success=0, latency=100):
    record = observation(s, index, success, latency)
    MonitoringRepository().store_monitoring_record(record)
    return process_observation(s, record, {"anomaly": False, "anomaly_score": None}, {"risk_score": 45})


def test_outage_dedup_ack_recovery_and_relapse():
    s = service()
    assert process(s, 0, 1)["health_state"] == "HEALTHY"
    assert process(s, 1)["health_state"] == "SUSPECTED_FAILURE"
    assert process(s, 2)["incident_id"] is None
    incident_id = process(s, 3)["incident_id"]
    assert incident_id
    operator_transition(incident_id, "ACKNOWLEDGED", "admin", "Investigating 503")
    operator_transition(incident_id, "INVESTIGATING", "admin")
    assert process(s, 4)["incident_id"] == incident_id
    assert IncidentRepository().get_incident(incident_id)["status"] == "INVESTIGATING"
    assert process(s, 5, 1)["health_state"] == "RECOVERED"
    with pytest.raises(ValueError): operator_transition(incident_id, "RESOLVED", "admin")
    assert process(s, 6)["incident_id"] == incident_id
    assert process(s, 7, 1)["health_state"] == "RECOVERED"
    assert process(s, 8, 1)["health_state"] == "HEALTHY"
    inc = IncidentRepository().get_incident(incident_id)
    assert inc["status"] == "RESOLVED"
    assert inc["downtime_seconds"] >= 7
    assert len(IncidentRepository().get_incidents()) == 1
    assert any(e.get("actor") == "admin" for e in inc["timeline"])


def test_replay_and_invalid_manual_resolution():
    s = service(failure_threshold=1)
    record = observation(s, 0)
    result = process_observation(s, record, {}, {})
    assert process_observation(s, record, {}, {}) == {"duplicate": True}
    with pytest.raises(ValueError): operator_transition(result["incident_id"], "RESOLVED", "admin")


def test_slow_recovery_does_not_resolve():
    s = service(failure_threshold=1)
    iid = process(s, 0)["incident_id"]
    for i in range(1, 5): process(s, i, 1, latency=4000)
    assert IncidentRepository().get_incident(iid)["status"] != "RESOLVED"


def test_intermittent_failures_do_not_confirm():
    s = service()
    for i in range(10): process(s, i, i % 2)
    assert IncidentRepository().get_incidents() == []


def test_ml_failure_cannot_block_outage():
    s = service(failure_threshold=1)
    result = dict(status_code=503, response_time=15, availability=0, request_success=0, error=1, error_rate=1., timeout=0)
    with patch("backend.lambdas.health_checker.handler.perform_http_check", return_value=result), patch("backend.lambdas.health_checker.handler.predict_anomaly", side_effect=RuntimeError("bad model")):
        record = check_service(s)
    assert record["incident_id"]
    assert record["ml_status"] == "inference_failed"


def test_database_failure_propagates_without_claiming_service_failure():
    s = service()
    with patch("backend.lambdas.health_checker.handler.perform_http_check", return_value=dict(status_code=200, response_time=1, availability=1, request_success=1, error=0, error_rate=0., timeout=0)), patch.object(MonitoringRepository, "store_monitoring_record", side_effect=RuntimeError("database unavailable")):
        with pytest.raises(RuntimeError): check_service(s)
    assert not IncidentRepository().get_incidents()


def test_conditional_write_rejects_stale_version():
    s = service()
    repo = ServiceRepository()
    save_versioned(repo.table, s)
    with pytest.raises(Conflict): save_versioned(repo.table, s)


def test_two_services_do_not_overwrite_incidents():
    a, b = service(failure_threshold=1), service(failure_threshold=1)
    assert process(a, 0)["incident_id"] != process(b, 0)["incident_id"]
    assert len(IncidentRepository().get_incidents()) == 2


def test_sustained_intermittent_error_rate_creates_evidence_based_incident():
    s = service()
    for i in range(14): result = process(s, i, i % 2)
    assert result["incident_id"]
    incident = IncidentRepository().get_incident(result["incident_id"])
    assert incident["severity"] == "HIGH"
    assert incident["detection_source"] == "rule"
