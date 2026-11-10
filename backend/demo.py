"""Dedicated deterministic failure-simulation service; never fabricated telemetry."""
import json
import time
from backend.database.service_repository import ServiceRepository


def handler(event, context):
    state = ServiceRepository().get_service("__demo_control__") or {}
    mode = state.get("mode", "ONLINE")
    if mode == "TIMEOUT": time.sleep(15)
    if mode == "SLOW_RESPONSE": time.sleep(2)
    status = 500 if mode == "HTTP_500" else 503 if mode == "HTTP_503" else 200
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"}, "body": json.dumps({"mode": mode, "status": "healthy" if status == 200 else "unavailable"})}
