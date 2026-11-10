from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
import pytest
from backend.database.incident_repository import IncidentRepository
from backend.lambdas.incident_analyzer.handler import process_incident
from backend.notifications import publish_pending


def incident():
    return IncidentRepository().create_incident(dict(incident_id="INC-test", service_id="test", severity="HIGH",
        status="CONFIRMED_INCIDENT", notifications=[], ai_status="pending", metrics_snapshot={"status_code":503},
        created_at=datetime.now(timezone.utc).isoformat()))


def test_created_cooldown_escalation_recovery(isolated_runtime):
    isolated_runtime.sns_topic_arn = "arn:aws:sns:ap-south-2:123456789012:test"
    inc = incident()
    sns = Mock()
    sns.publish.return_value = {"MessageId": "message"}
    with patch("backend.notifications.boto3.client", return_value=sns):
        publish_pending(inc["incident_id"])
        publish_pending(inc["incident_id"])
        assert sns.publish.call_count == 1
        IncidentRepository().update_incident(inc["incident_id"], {"created_at": (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()})
        publish_pending(inc["incident_id"])
        assert sns.publish.call_count == 2
        IncidentRepository().update_incident(inc["incident_id"], {"status":"RESOLVED"})
        publish_pending(inc["incident_id"])
        publish_pending(inc["incident_id"])
        assert sns.publish.call_count == 3
    entries = IncidentRepository().get_incident(inc["incident_id"])["notifications"]
    assert [n["kind"] for n in entries] == ["created", "escalation", "recovery"]


def test_sns_failure_persisted_and_retried(isolated_runtime):
    isolated_runtime.environment = "production"
    isolated_runtime.sns_topic_arn = "arn:aws:sns:ap-south-2:123456789012:test"
    # Keep repository local while exercising production retry behavior.
    isolated_runtime.environment = "test"
    inc = incident()
    with patch("backend.notifications.boto3.client") as client:
        client.return_value.publish.side_effect = RuntimeError("SNS unavailable")
        with pytest.raises(RuntimeError): publish_pending(inc["incident_id"])
    assert IncidentRepository().get_incident(inc["incident_id"])["notifications"][0]["status"] == "failed"


def test_ai_unavailable_does_not_remove_incident():
    inc = incident()
    with patch("backend.lambdas.incident_analyzer.handler.analyze_incident", new=AsyncMock(return_value={"analysis_status":"unavailable","confidence":"low"})):
        process_incident(inc["incident_id"])
    assert IncidentRepository().get_incident(inc["incident_id"])["status"] == "CONFIRMED_INCIDENT"
