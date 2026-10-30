"""Periodic service checks for local development."""

import asyncio
import time

from backend.database.service_repository import ServiceRepository
from backend.lambdas.health_checker.handler import check_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def run_local_monitoring(poll_interval: float = 5.0) -> None:
    """Check active services locally using each service's configured interval."""
    last_checked = {}
    service_repo = ServiceRepository()

    while True:
        try:
            services = await asyncio.to_thread(service_repo.get_active_services)
            now = time.monotonic()
            due_services = []

            for service in services:
                service_id = service.get("service_id")
                if not service_id:
                    continue
                interval = max(1, int(service.get("check_interval", 60)))
                if now - last_checked.get(service_id, float("-inf")) >= interval:
                    last_checked[service_id] = now
                    due_services.append(service)

            if due_services:
                await asyncio.gather(
                    *(_check_service(service) for service in due_services)
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Local monitoring cycle failed.",
                extra={"action": "local_monitoring_error"},
            )

        await asyncio.sleep(poll_interval)


async def _check_service(service: dict) -> None:
    try:
        await asyncio.to_thread(check_service, service)
    except Exception:
        logger.exception(
            "Local health check failed.",
            extra={
                "service_id": service.get("service_id"),
                "action": "local_health_check_error",
            },
        )
