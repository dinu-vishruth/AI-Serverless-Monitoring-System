"""Scheduled training from actual historical telemetry; no synthetic samples."""
from backend.database.service_repository import ServiceRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.ml.train import retrain_service
from backend.ml.model_manager import ModelManager

def handler(event, context):
    results = []
    for service in ServiceRepository().get_active_services():
        sid = service['service_id']
        records = MonitoringRepository().get_historical_records(sid, hours=72, limit=3000)
        if ModelManager().should_retrain(sid, len(records)):
            results.append(retrain_service(sid, records))
    return {'results': results}
