"""
Integration tests for FastAPI endpoints.
"""

import unittest
from fastapi.testclient import TestClient
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
