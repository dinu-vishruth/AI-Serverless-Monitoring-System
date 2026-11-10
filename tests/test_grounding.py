import pytest
from backend.ai.grounding import render_answer


def test_assistant_rejects_invented_facts():
    with pytest.raises(ValueError):
        render_answer({"fact_ids":["invented"]}, {"fact-1":"Observed four failures"})


def test_assistant_cannot_add_invented_measurements():
    answer = render_answer({"fact_ids":["fact-1"], "possible_causes":["Five failures prove database overload", "Upstream dependency may be unavailable"], "recommended_actions":["Inspect application logs"]}, {"fact-1":"Observed four failures"})
    assert "Five" not in answer
    assert "four failures" in answer
    assert "Upstream dependency" in answer


def test_today_query_excludes_yesterdays_failures():
    from datetime import datetime, timezone, timedelta
    from backend.ai.tools import operational_context
    from backend.database.service_repository import ServiceRepository
    from backend.database.monitoring_repository import MonitoringRepository
    service = ServiceRepository().create_service({"service_name":"Calendar test", "url":"https://example.com"})
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for timestamp, success in ((midnight-timedelta(seconds=1),0),(datetime.now(timezone.utc),1)):
        MonitoringRepository().store_monitoring_record(dict(service_id=service['service_id'], timestamp=timestamp.isoformat(), response_time=100, status_code=200 if success else 503, request_success=success, availability=success, error=1-success, error_rate=1-success, timeout=0))
    context = operational_context([service], "Which service had the most failures today?")
    assert context['window_label'] == 'today in UTC'
    assert context['services'][0]['reliability']['failure_count'] == 0
