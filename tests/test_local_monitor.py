import asyncio
import unittest
from unittest.mock import Mock, patch

from backend.utils.local_monitor import run_local_monitoring


class TestLocalMonitoring(unittest.IsolatedAsyncioTestCase):
    async def test_checks_active_services_immediately_and_respects_interval(self):
        service_repo = Mock()
        service_repo.get_active_services.return_value = [
            {"service_id": "svc-fast", "check_interval": 1},
            {"service_id": "svc-slow", "check_interval": 60},
        ]
        sleep_calls = 0

        async def run_in_thread(function, *args):
            return function(*args)

        async def stop_after_second_cycle(_interval):
            nonlocal sleep_calls
            sleep_calls += 1
            if sleep_calls == 2:
                raise asyncio.CancelledError

        with patch(
            "backend.utils.local_monitor.ServiceRepository",
            return_value=service_repo,
        ), patch(
            "backend.utils.local_monitor.check_service"
        ) as check_service, patch(
            "backend.utils.local_monitor.asyncio.to_thread",
            side_effect=run_in_thread,
        ), patch(
            "backend.utils.local_monitor.asyncio.sleep",
            side_effect=stop_after_second_cycle,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_local_monitoring(poll_interval=0.01)

        self.assertEqual(check_service.call_count, 2)
        self.assertEqual(
            {call.args[0]["service_id"] for call in check_service.call_args_list},
            {"svc-fast", "svc-slow"},
        )
        self.assertEqual(service_repo.get_active_services.call_count, 2)
