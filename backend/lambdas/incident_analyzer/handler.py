"""DynamoDB incident stream worker. Propagates failures for AWS retry/DLQ."""
import asyncio
import time
import uuid
from boto3.dynamodb.types import TypeDeserializer
from backend.database.incident_repository import IncidentRepository
from backend.database.concurrency import mutate, Conflict
from backend.ai.incident_analysis import analyze_incident
from backend.database.monitoring_repository import MonitoringRepository
from backend.ml.risk_analyzer import compute_historical_metrics
from backend.notifications import publish_pending
from backend.lifecycle import event as timeline_event, utcnow
from backend.utils.logger import get_logger
logger = get_logger(__name__)

def process_incident(incident_id):
    repo = IncidentRepository()
    token = uuid.uuid4().hex
    def acquire(item):
        if float(item.get('worker_lease_until', 0)) > time.time():
            raise Conflict('Incident worker busy')
        item.update(worker_lease_owner=token, worker_lease_until=time.time() + 90)
    incident, _ = mutate(repo.table, {'incident_id': incident_id}, acquire)
    try:
        publish_pending(incident_id)
        if incident.get('ai_status') == 'pending':
            mutate(repo.table, {'incident_id': incident_id}, lambda i: i.update(timeline=(i.get('timeline', []) + [timeline_event('AI_INVESTIGATION_STARTED', utcnow())])[-200:]))
            metrics = incident.get('metrics_snapshot', {})
            history = MonitoringRepository().get_historical_records(incident['service_id'])
            analysis = asyncio.run(analyze_incident(incident, metrics, compute_historical_metrics(history),
                {'anomaly_score': incident.get('anomaly_score'), 'model_version': incident.get('model_version'), 'anomaly': incident.get('detection_source') == 'ml'}))
            def finish(item):
                item['ai_status'] = analysis.get('analysis_status', 'unavailable')
                item['ai_confidence'] = analysis.get('confidence', 'low')
                item['likely_cause'] = analysis.get('possible_causes', [])
                item['timeline'] = (item.get('timeline', []) + [timeline_event('AI_INVESTIGATION_' + item['ai_status'].upper(), utcnow())])[-200:]
            mutate(repo.table, {'incident_id': incident_id}, finish)
    finally:
        def release(item):
            if item.get('worker_lease_owner') == token:
                item.update(worker_lease_until=0, worker_lease_owner=None)
        mutate(repo.table, {'incident_id': incident_id}, release)

def handler(event, context):
    deserializer = TypeDeserializer()
    ids = [event['incident_id']] if event.get('incident_id') else []
    for record in event.get('Records', []):
        if record.get('eventName') == 'REMOVE': continue
        image = record.get('dynamodb', {}).get('NewImage', {})
        item = {k: deserializer.deserialize(v) for k, v in image.items()}
        # Lease/timeline/AI-only modifications do not invoke another pipeline.
        old = {k: deserializer.deserialize(v) for k, v in record.get('dynamodb', {}).get('OldImage', {}).items()}
        if record.get('eventName') == 'INSERT' or any(item.get(k) != old.get(k) for k in ('status', 'severity', 'last_observed_at')):
            ids.append(item['incident_id'])
    for incident_id in set(ids):
        process_incident(incident_id)
    return {'processed': len(set(ids))}
