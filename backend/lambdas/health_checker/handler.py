"""HTTP probes, per-service concurrency lease and canonical monitoring pipeline."""
import asyncio
import json
import socket
import ssl
import time
import uuid
import urllib.request
import urllib.error
import http.client
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.service_repository import ServiceRepository
from backend.database.concurrency import mutate, Conflict
from backend.ml.predict import predict_anomaly
from backend.ml.risk_analyzer import calculate_risk, compute_historical_metrics
from backend.lifecycle import process_observation
from backend.utils.config import get_settings
from backend.utils.logger import get_logger
logger = get_logger(__name__)

def handler(event, context):
    services = ServiceRepository().get_active_services()
    now = time.time()
    due = [s for s in services if not s.get('last_processed_at') or now - datetime.fromisoformat(s['last_processed_at']).timestamp() >= int(s.get('check_interval', 60))]
    def execute(service):
        if context is not None and context.get_remaining_time_in_millis() < (int(service.get('timeout', 10)) + 5) * 1000:
            raise TimeoutError('Insufficient Lambda budget; next schedule will retry unchecked services')
        return check_service(service)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(execute, due))
    return {'statusCode': 200, 'body': json.dumps({'checked': len(results)}, default=str)}

def check_service(service):
    repo = ServiceRepository()
    sid = service['service_id']
    token = uuid.uuid4().hex
    def acquire(item):
        if float(item.get('lease_until', 0)) > time.time():
            raise Conflict('Check already running')
        item.update(lease_owner=token, lease_until=time.time() + 120)
    try:
        mutate(repo.table, {'service_id': sid}, acquire)
    except Conflict:
        return {'service_id': sid, 'status': 'check_in_progress'}
    try:
        result = perform_http_check(service['url'], service.get('http_method', 'GET'), int(service.get('expected_status_code', 200)), int(service.get('timeout', 10)))
        record = dict(result, service_id=sid, service_name=service.get('service_name', ''), timestamp=datetime.now(timezone.utc).isoformat())
        monitoring = MonitoringRepository()
        ai = run_ai_pipeline(service, record, monitoring)
        record.update({k: v for k, v in ai.items() if k not in {'incident_id'}})
        monitoring.store_monitoring_record(record)
        state = process_observation(service, record, ai, ai)
        record.update(state)
        # Cloud execution uses the incident stream. Local execution uses the same worker.
        if state.get('incident_id') and get_settings().environment.lower() in {'local', 'development', 'dev', 'test'}:
            from backend.lambdas.incident_analyzer.handler import process_incident
            try:
                process_incident(state['incident_id'])
            except Exception:
                logger.exception('Local incident processing failed', extra={'action': 'platform_failure', 'incident_id': state['incident_id']})
        return record
    except Exception:
        logger.exception('Monitoring pipeline failed', extra={'action': 'platform_failure', 'service_id': sid})
        raise
    finally:
        def release(item):
            if item.get('lease_owner') == token:
                item.update(lease_until=0, lease_owner=None)
        mutate(repo.table, {'service_id': sid}, release)

def perform_http_check(url, method='GET', expected_status=200, timeout=10):
    from backend.utils.targets import probe_address
    start = time.monotonic()
    result = dict(status_code=0, response_time=0, availability=0, error=1, error_rate=1.0, timeout=0, request_success=0, failure_type=None)
    try:
        address = probe_address(url)
        request = urllib.request.Request(url, method=method.upper(), headers={'User-Agent': 'ISMS/2.0'})
        # Redirects are deliberately not followed: each registered target is checked directly.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl): return None
        def connection_factory(cls, host, **kwargs):
            connection = cls(host, **kwargs)
            connection._create_connection = lambda pair, timeout, source_address=None: socket.create_connection((address, pair[1]), timeout, source_address)
            return connection
        class PinnedHTTP(urllib.request.HTTPHandler):
            def http_open(self, req):
                return self.do_open(lambda host, **kwargs: connection_factory(http.client.HTTPConnection, host, **kwargs), req)
        class PinnedHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req):
                return self.do_open(lambda host, **kwargs: connection_factory(http.client.HTTPSConnection, host, context=ssl.create_default_context(), **kwargs), req)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect, PinnedHTTP, PinnedHTTPS)
        with opener.open(request, timeout=timeout) as response:
            result['status_code'] = response.status
    except urllib.error.HTTPError as exc:
        result['status_code'] = exc.code
        exc.close()
    except (TimeoutError, socket.timeout):
        result.update(timeout=1, failure_type='timeout')
    except urllib.error.URLError as exc:
        reason = exc.reason
        failure = 'tls' if isinstance(reason, ssl.SSLError) else 'dns' if isinstance(reason, socket.gaierror) else 'timeout' if isinstance(reason, TimeoutError) else 'connection'
        result.update(failure_type=failure, timeout=int(failure == 'timeout'))
    except ssl.SSLError:
        result['failure_type'] = 'tls'
    except socket.gaierror:
        result['failure_type'] = 'dns'
    except (OSError, ValueError):
        result['failure_type'] = 'connection'
    success = result['status_code'] == expected_status
    result.update(response_time=round((time.monotonic() - start) * 1000, 2), request_success=int(success), availability=int(success), error=int(not success), error_rate=float(not success))
    if not success and result['failure_type'] is None: result['failure_type'] = 'http_status'
    return result

def run_ai_pipeline(service, record, monitoring_repo):
    history = monitoring_repo.get_historical_records(service['service_id'], hours=24)
    history = sorted([r for r in history if r['timestamp'] < record['timestamp']], key=lambda r: r['timestamp'])
    result = dict(anomaly=False, anomaly_score=None, ml_status='no_model')
    try:
        prediction = predict_anomaly(service['service_id'], record, history[-20:])
        result.update(anomaly=prediction['anomaly'], anomaly_score=prediction['anomaly_score'], ml_status=prediction['status'], model_version=prediction.get('model_version'))
    except Exception:
        result['ml_status'] = 'inference_failed'
        logger.exception('ML inference failed; deterministic monitoring continues', extra={'action': 'ml_failure'})
    result.update(calculate_risk(record, compute_historical_metrics(history), service))
    return result
