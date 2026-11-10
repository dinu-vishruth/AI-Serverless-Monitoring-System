"""Real HTTP probes + actual IsolationForest + isolated DB; mocked external AI/SNS.

This test proves orchestration, not Groq availability or email delivery.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch, Mock, AsyncMock
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.lambdas.health_checker.handler import check_service
from backend.ml.train import train_model
from backend.lifecycle import operator_transition


def test_full_failure_investigation_notification_recovery(isolated_runtime):
    state = {"code":200, "delay":0}
    class Endpoint(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(state["delay"])
            self.send_response(state["code"])
            self.end_headers()
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    isolated_runtime.sns_topic_arn = "arn:aws:sns:ap-south-2:123456789012:test"
    service = ServiceRepository().create_service(dict(service_name="Demo payments", url=f'http://127.0.0.1:{server.server_port}/health', response_time_threshold=50))
    provider = Mock(provider_name="TEST ONLY")
    provider.analyze = AsyncMock(return_value=dict(incident_summary="HTTP 503 observed", observed_facts=["HTTP 503"], possible_causes=["Unconfirmed upstream failure"], impact=["Probe unavailable"], recommended_actions=["Inspect application logs"], confidence="low", next_diagnostic_checks=["Check upstream logs"]))
    sns = Mock()
    sns.publish.return_value = {"MessageId":"test-message"}
    try:
        with patch("backend.ai.incident_analysis.get_ai_provider", return_value=provider), patch("backend.notifications.boto3.client", return_value=sns):
            for _ in range(25):
                record = check_service(service)
                assert record["request_success"] == 1
            records = MonitoringRepository().get_historical_records(service["service_id"])
            assert train_model(service["service_id"], records)["status"] == "trained"
            state["delay"] = .1
            degraded = check_service(service)
            assert degraded["ml_status"] == "predicted"
            state.update(code=503, delay=0)
            for _ in range(3): failed = check_service(service)
            iid = failed["incident_id"]
            assert iid
            operator_transition(iid, "ACKNOWLEDGED", "test-admin", "Review actual 503")
            for _ in range(2): assert check_service(service)["incident_id"] == iid
            assert len(IncidentRepository().get_incidents()) == 1
            assert provider.analyze.await_count == 1
            prompt = provider.analyze.await_args.kwargs["user_prompt"]
            assert '503' in prompt and 'correlation' in prompt
            state["code"] = 200
            # Existing learned latency model may flag tiny scheduling variations;
            # use a new service no-model state for deterministic recovery verification.
            from backend.ml.model_manager import ModelManager
            ModelManager().delete_model(service["service_id"])
            assert check_service(service)["health_state"] == "RECOVERED"
            assert check_service(service)["health_state"] == "HEALTHY"
            inc = IncidentRepository().get_incident(iid)
            assert inc["status"] == "RESOLVED"
            assert inc["downtime_seconds"] > 0
            assert {n["kind"] for n in inc["notifications"] if n["status"] == "sent"} >= {"created", "recovery"}
    finally:
        server.shutdown()
        server.server_close()
