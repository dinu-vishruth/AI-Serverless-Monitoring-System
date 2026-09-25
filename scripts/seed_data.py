"""
Seed Data Generator.
Populates DynamoDB tables (or local in-memory/fallback) with realistic services,
historical monitoring metrics, ML anomalies, incidents, and AI analyses.
"""

import sys
import os
import random
from datetime import datetime, timedelta, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.incident_repository import IncidentRepository
from backend.database.ai_repository import AIAnalysisRepository
from backend.ml.train import train_model

SAMPLE_SERVICES = [
    {
        "service_name": "Auth & SSO Service",
        "url": "https://auth.internal.example.com/health",
        "http_method": "GET",
        "expected_status_code": 200,
        "check_interval": 30,
        "timeout": 5,
        "response_time_threshold": 1200.0,
        "error_threshold": 0.02,
        "is_active": True,
        "tags": ["core", "security", "production"],
    },
    {
        "service_name": "Payment Gateway API",
        "url": "https://payment.internal.example.com/v1/health",
        "http_method": "GET",
        "expected_status_code": 200,
        "check_interval": 60,
        "timeout": 10,
        "response_time_threshold": 2500.0,
        "error_threshold": 0.05,
        "is_active": True,
        "tags": ["finance", "critical", "production"],
    },
    {
        "service_name": "Product Catalog API",
        "url": "https://catalog.internal.example.com/api/products",
        "http_method": "GET",
        "expected_status_code": 200,
        "check_interval": 60,
        "timeout": 8,
        "response_time_threshold": 1500.0,
        "error_threshold": 0.05,
        "is_active": True,
        "tags": ["ecommerce", "public"],
    },
    {
        "service_name": "Notification Dispatcher",
        "url": "https://notifications.internal.example.com/status",
        "http_method": "GET",
        "expected_status_code": 200,
        "check_interval": 120,
        "timeout": 5,
        "response_time_threshold": 800.0,
        "error_threshold": 0.01,
        "is_active": True,
        "tags": ["async", "messaging"],
    },
]


def seed_database():
    print("[+] Starting Seed Process...")
    service_repo = ServiceRepository()
    mon_repo = MonitoringRepository()
    incident_repo = IncidentRepository()
    ai_repo = AIAnalysisRepository()

    created_services = []
    for s_def in SAMPLE_SERVICES:
        service = service_repo.create_service(s_def)
        created_services.append(service)
        print(f"  [+] Created Service: {service['service_name']} ({service['service_id']})")

    # Generate historical monitoring data for each service over last 24 hours
    now = datetime.now(timezone.utc)
    for service in created_services:
        sid = service["service_id"]
        sname = service["service_name"]
        records = []

        print(f"  Generating 24h telemetry for {sname}...")
        for i in range(48):  # Every 30 mins for 24h
            ts = (now - timedelta(minutes=30 * (48 - i))).isoformat()
            
            # Base normal telemetry
            base_rt = 120.0 + random.uniform(10, 80)
            status_code = 200
            error = 0
            avail = 1
            error_rate = 0.0

            # Inject simulated anomaly for Payment Gateway near the end
            if "Payment" in sname and i >= 42:
                base_rt = 3400.0 + random.uniform(200, 1100)
                if i >= 45:
                    status_code = 504
                    error = 1
                    avail = 0
                    error_rate = 0.4

            record = {
                "service_id": sid,
                "service_name": sname,
                "url": service["url"],
                "timestamp": ts,
                "status_code": status_code,
                "response_time": round(base_rt, 2),
                "availability": avail,
                "error": error,
                "error_rate": error_rate,
                "timeout": 1 if status_code == 504 else 0,
                "request_success": 1 if status_code == 200 else 0,
            }
            mon_repo.store_monitoring_record(record)
            records.append(record)

        # Train ML Isolation Forest model
        try:
            train_model(sid, records)
            print(f"  [+] Trained Isolation Forest model for {sname}")
        except Exception as e:
            print(f"  [!] Model training notice for {sname}: {e}")

    # Seed simulated active incident for Payment Gateway
    payment_service = [s for s in created_services if "Payment" in s["service_name"]][0]
    incident_id = f"inc-{int(now.timestamp())}-sim"
    incident_data = {
        "incident_id": incident_id,
        "service_id": payment_service["service_id"],
        "service_name": payment_service["service_name"],
        "severity": "CRITICAL",
        "status": "OPEN",
        "trigger_reason": "Response time above threshold (4210ms) | HTTP 504 Gateway Timeout | Isolation Forest Anomaly Score 0.88",
        "created_at": (now - timedelta(minutes=12)).isoformat(),
        "updated_at": now.isoformat(),
        "anomaly_score": 0.88,
        "risk_score": 92.5,
        "risk_level": "CRITICAL",
        "metrics_snapshot": {
            "response_time": 4210.0,
            "status_code": 504,
            "error_rate": 0.4,
            "availability": 0,
        },
    }
    incident_repo.create_incident(incident_data)
    print(f"  [+] Created Demonstration Incident: {incident_id}")

    # Seed AI Analysis for this incident
    ai_analysis_data = {
        "analysis_id": f"ai-{int(now.timestamp())}-sim",
        "incident_id": incident_id,
        "service_id": payment_service["service_id"],
        "timestamp": now.isoformat(),
        "incident_summary": "Payment Gateway API experienced severe degradation resulting in HTTP 504 Gateway Timeouts. Latency increased by 1,850% over baseline (avg 180ms vs current 4,210ms) with an Isolation Forest anomaly score of 0.88.",
        "observed_facts": [
            "Response time spiked to 4,210ms (threshold: 2,500ms)",
            "Downstream upstream connections timing out after 10,000ms",
            "Error rate rose to 40% with multiple 504 Gateway Timeout responses",
            "Isolation Forest flagged multi-dimensional outlier with 0.88 confidence"
        ],
        "possible_causes": [
            "Upstream bank payment provider API rate limiting or experiencing degraded gateway latency",
            "Database connection pool exhaustion in serverless Lambda concurrency burst",
            "Deadlock in transactional ledger verification table"
        ],
        "impact": [
            "Checkout workflows are failing for ~40% of active users",
            "Potential transaction replay and duplicate charge attempts"
        ],
        "recommended_actions": [
            "Verify third-party payment clearinghouse status page & circuit breaker",
            "Increase Lambda reserved concurrency and check DynamoDB provisioned/on-demand read throttle events",
            "Engage on-call payment infrastructure engineering team"
        ],
        "confidence": "high",
        "risk_level": "CRITICAL",
        "risk_score": 92.5,
    }
    ai_repo.store_analysis(ai_analysis_data)
    print(f"  [+] Created AI Telemetry Analysis")

    print("\n[SUCCESS] Database successfully seeded with demo telemetry and AI insights!")


if __name__ == "__main__":
    seed_database()
