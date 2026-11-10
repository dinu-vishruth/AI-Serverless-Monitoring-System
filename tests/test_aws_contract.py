"""DynamoDB/S3/SNS contracts using moto, distinct from live cloud tests."""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import boto3
import pytest
from moto import mock_aws
from backend.database.service_repository import ServiceRepository
from backend.database.incident_repository import IncidentRepository
from backend.database.monitoring_repository import MonitoringRepository
from backend.database.concurrency import mutate, save_versioned, Conflict
from backend.lifecycle import process_observation
from backend.ml.train import train_model
from backend.ml.predict import predict_anomaly
from backend.ml.model_manager import ModelManager
from backend.notifications import publish_pending


@pytest.fixture
def aws_tables(isolated_runtime):
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="ap-south-2")
        for name, partition, sort in [("Services","service_id",None),("MonitoringData","service_id","timestamp"),("Incidents","incident_id",None),("AIAnalysis","analysis_id",None)]:
            keys = [{"AttributeName":partition,"KeyType":"HASH"}]
            attrs = [{"AttributeName":partition,"AttributeType":"S"}]
            kwargs = {}
            if sort:
                keys.append({"AttributeName":sort,"KeyType":"RANGE"})
                attrs.append({"AttributeName":sort,"AttributeType":"S"})
            if name == "Incidents":
                attrs += [{"AttributeName":"service_id","AttributeType":"S"},{"AttributeName":"created_at","AttributeType":"S"}]
                kwargs["GlobalSecondaryIndexes"] = [{"IndexName":"ServiceIndex","KeySchema":[{"AttributeName":"service_id","KeyType":"HASH"},{"AttributeName":"created_at","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]
            resource.create_table(TableName=name, KeySchema=keys, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST", **kwargs)
        with patch("backend.database.dynamodb.get_dynamodb_resource", return_value=resource):
            yield resource


def test_dynamo_conditional_lifecycle_and_real_sns(aws_tables, isolated_runtime):
    svc = ServiceRepository().create_service(dict(service_name="AWS contract", url="https://example.com", failure_threshold=1))
    saved, _ = mutate(ServiceRepository().table, {"service_id":svc["service_id"]}, lambda i: i.update(test_value=1))
    with pytest.raises(Conflict): save_versioned(ServiceRepository().table, svc)
    now = datetime.now(timezone.utc).isoformat()
    record = dict(service_id=svc["service_id"], timestamp=now, response_time=10., status_code=503, request_success=0, availability=0, error_rate=1., error=1, timeout=0)
    MonitoringRepository().store_monitoring_record(record)
    result = process_observation(svc, record, {"anomaly_score":None}, {"risk_score":40.})
    iid = result["incident_id"]
    assert iid
    assert MonitoringRepository().get_latest_record(svc["service_id"])["ttl"] > 0
    assert process_observation(svc, record, {}, {}) == {"duplicate":True}
    sns = boto3.client("sns", region_name="ap-south-2")
    isolated_runtime.sns_topic_arn = sns.create_topic(Name="test-monitoring")["TopicArn"]
    publish_pending(iid)
    publish_pending(iid)
    assert len(IncidentRepository().get_incident(iid)["notifications"]) == 1


def test_s3_model_available_after_local_cache_loss(aws_tables, isolated_runtime, tmp_path):
    s3 = boto3.client("s3", region_name="ap-south-2")
    s3.create_bucket(Bucket="isms-model-test", CreateBucketConfiguration={"LocationConstraint":"ap-south-2"})
    isolated_runtime.model_bucket = "isms-model-test"
    records = [dict(service_id="model-test", timestamp=(datetime.now(timezone.utc)-timedelta(minutes=30-i)).isoformat(), response_time=100+i%7, status_code=200, error_rate=0., availability=1, timeout=0, request_success=1) for i in range(25)]
    trained = train_model("model-test", records)
    assert trained["status"] == "trained"
    metadata = ModelManager().get_metadata("model-test")
    isolated_runtime.ml_model_path = str(tmp_path / "cold-container")
    prediction = predict_anomaly("model-test", dict(records[-1], timestamp=datetime.now(timezone.utc).isoformat()), records)
    assert prediction["status"] == "predicted"
    assert prediction["model_version"] == metadata["version"]
    assert train_model("model-test", records[:2])["status"] == "insufficient_data"
    assert ModelManager().get_metadata("model-test")["version"] == metadata["version"]
