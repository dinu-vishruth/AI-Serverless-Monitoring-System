"""
Integration tests for FastAPI endpoints.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from backend.ai.provider import AIProviderError, get_ai_provider
from backend.main import app


class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")

    def test_metrics_overview_endpoint(self):
        response = self.client.get("/api/v1/metrics/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("system_health_score", data)
        self.assertIn("total_services", data)

    def test_metrics_overview_handles_numeric_string_records(self):
        with patch("backend.api.routes.metrics.ServiceRepository") as service_repo, \
             patch("backend.api.routes.metrics.MonitoringRepository") as monitoring_repo, \
             patch("backend.api.routes.metrics.IncidentRepository") as incident_repo:
            service_repo.return_value.list_services.return_value = [
                {"service_id": "svc-1", "response_time_threshold": "2000"}
            ]
            monitoring_repo.return_value.get_latest_record.return_value = {
                "response_time": "125",
                "availability": "1",
                "error": "0",
            }
            incident_repo.return_value.get_open_incidents.return_value = []

            response = self.client.get("/api/v1/metrics/overview")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["average_response_time_ms"], 125.0)
        self.assertEqual(data["overall_availability_percentage"], 100.0)
        self.assertEqual(data["healthy_services"], 1)

    def test_ai_chat_uses_llm_chat_with_current_service_context(self):
        service = {
            "service_id": "svc-1",
            "service_name": "Payments API",
            "is_active": True,
            "response_time_threshold": 2000,
            "error_threshold": 0.05,
            "tags": ["payments"],
        }
        provider = Mock()
        provider.provider_name = "OpenAI (gpt-4o-mini)"
        provider.chat = AsyncMock(return_value="Payments API is responding in 125 ms.")

        with patch("backend.api.routes.ai.ServiceRepository") as service_repo, \
             patch("backend.api.routes.ai.IncidentRepository") as incident_repo, \
             patch("backend.api.routes.ai.MonitoringRepository") as monitoring_repo, \
             patch("backend.api.routes.ai.get_ai_provider", return_value=provider):
            service_repo.return_value.get_service.return_value = service
            incident_repo.return_value.get_service_incidents.return_value = []
            monitoring_repo.return_value.get_latest_record.return_value = {
                "timestamp": "2026-10-30T10:00:00+00:00",
                "response_time": 125,
                "status_code": 200,
                "availability": 1,
                "error_rate": 0,
            }

            response = self.client.post(
                "/api/v1/ai/chat",
                json={"query": "How is Payments API responding?", "service_id": "svc-1"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Payments API is responding in 125 ms.")
        self.assertEqual(data["provider"], "OpenAI (gpt-4o-mini)")
        messages = provider.chat.await_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("125", messages[1]["content"])
        self.assertIn("Payments API", messages[1]["content"])
        self.assertIn("Isolation Forest features", messages[1]["content"])

    def test_ai_chat_refuses_unrelated_questions_without_calling_llm(self):
        with patch("backend.api.routes.ai.ServiceRepository") as service_repo, \
             patch("backend.api.routes.ai.IncidentRepository") as incident_repo, \
             patch("backend.api.routes.ai.MonitoringRepository"), \
             patch("backend.api.routes.ai.get_ai_provider") as get_provider:
            service_repo.return_value.list_services.return_value = []
            incident_repo.return_value.get_incidents.return_value = []

            response = self.client.post(
                "/api/v1/ai/chat",
                json={"query": "What is the capital of France?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("only answer questions", response.json()["answer"])
        self.assertEqual(response.json()["provider"], "Context filter")
        get_provider.assert_not_called()

    def test_ai_chat_reports_missing_real_llm_configuration(self):
        with patch("backend.api.routes.ai.ServiceRepository") as service_repo, \
             patch("backend.api.routes.ai.IncidentRepository") as incident_repo, \
             patch("backend.api.routes.ai.MonitoringRepository"), \
             patch(
                 "backend.api.routes.ai.get_ai_provider",
                 side_effect=AIProviderError(
                     "AI_API_KEY is not configured.",
                     provider="openai",
                     recoverable=False,
                 ),
             ):
            service_repo.return_value.list_services.return_value = []
            incident_repo.return_value.get_incidents.return_value = []

            response = self.client.post(
                "/api/v1/ai/chat",
                json={"query": "What is the current service health?"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("AI_API_KEY", response.json()["detail"])

    def test_openai_provider_does_not_fall_back_when_key_is_missing(self):
        with patch(
            "backend.ai.provider.get_settings",
            return_value=Mock(ai_provider="openai", ai_api_key=""),
        ):
            with self.assertRaisesRegex(AIProviderError, "AI_API_KEY is not configured"):
                get_ai_provider()

    def test_groq_provider_uses_groq_api_and_configured_model(self):
        settings = Mock(
            ai_provider="groq",
            groq_api_key="test-groq-key",
            groq_model="openai/gpt-oss-120b",
        )
        with patch("backend.ai.provider.get_settings", return_value=settings), \
             patch("backend.ai.openai_provider.get_settings", return_value=settings), \
             patch("backend.ai.openai_provider.AsyncOpenAI") as openai_client:
            provider = get_ai_provider()

        self.assertEqual(provider.provider_name, "Groq (openai/gpt-oss-120b)")
        openai_client.assert_called_once_with(
            api_key="test-groq-key",
            base_url="https://api.groq.com/openai/v1",
        )

    def test_groq_provider_requires_groq_api_key(self):
        settings = Mock(ai_provider="groq", groq_api_key="")
        with patch("backend.ai.provider.get_settings", return_value=settings):
            with self.assertRaisesRegex(AIProviderError, "GROQ_API_KEY is not configured"):
                get_ai_provider()

    def test_groq_chat_reports_authentication_failure_without_leaking_error(self):
        settings = Mock(
            ai_provider="groq",
            groq_api_key="test-groq-key",
            groq_model="openai/gpt-oss-120b",
        )
        with patch("backend.ai.provider.get_settings", return_value=settings), \
             patch("backend.ai.openai_provider.get_settings", return_value=settings), \
             patch("backend.ai.openai_provider.AsyncOpenAI"):
            provider = get_ai_provider()

        provider.client.chat.completions.create = AsyncMock(
            side_effect=type("ProviderResponseError", (Exception,), {"status_code": 401})(
                "sensitive provider response"
            )
        )

        with self.assertRaises(AIProviderError) as raised:
            import asyncio
            asyncio.run(provider.chat([{"role": "user", "content": "test"}]))

        self.assertIn("HTTP 401", str(raised.exception))
        self.assertIn("GROQ_API_KEY", str(raised.exception))
        self.assertNotIn("sensitive provider response", str(raised.exception))

    def test_services_crud(self):
        # 1. Create service
        new_svc = {
            "service_name": "Test Integration API",
            "url": "https://httpbin.org/status/200",
            "http_method": "GET",
            "expected_status_code": 200,
            "check_interval": 60,
            "timeout": 10,
            "response_time_threshold": 2000.0,
            "error_threshold": 0.05,
        }
        res_create = self.client.post("/api/v1/services", json=new_svc)
        self.assertEqual(res_create.status_code, 201)
        created_svc = res_create.json()
        service_id = created_svc["service_id"]

        # 2. Get service
        res_get = self.client.get(f"/api/v1/services/{service_id}")
        self.assertEqual(res_get.status_code, 200)

        # 3. List services
        res_list = self.client.get("/api/v1/services")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(s["service_id"] == service_id for s in res_list.json()))

        # 4. Delete service
        res_del = self.client.delete(f"/api/v1/services/{service_id}")
        self.assertEqual(res_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()
