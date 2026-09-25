"""
Monitoring repository — stores and retrieves health-check monitoring data.

DynamoDB Table: MonitoringData
  Partition Key: service_id (S)
  Sort Key: timestamp (S)
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from backend.database.dynamodb import get_table, Key, Attr
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _to_decimal(value) -> Decimal:
    """Converts a float to Decimal for DynamoDB compatibility."""
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _from_decimal(item: dict) -> dict:
    """Converts Decimal values back to float for JSON serialization."""
    result = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, dict):
            result[key] = _from_decimal(value)
        elif isinstance(value, list):
            result[key] = [
                _from_decimal(v) if isinstance(v, dict) else float(v) if isinstance(v, Decimal) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


class MonitoringRepository:
    """Manages monitoring data in DynamoDB."""

    def __init__(self):
        settings = get_settings()
        self.table = get_table(settings.monitoring_table)

    def store_monitoring_record(self, record: dict) -> dict:
        """Stores a single health-check result."""
        item = {
            "service_id": record["service_id"],
            "timestamp": record["timestamp"],
            "service_name": record.get("service_name", ""),
            "url": record.get("url", ""),
            "status_code": int(record.get("status_code", 0)),
            "response_time": _to_decimal(record.get("response_time", 0)),
            "availability": _to_decimal(record.get("availability", 0)),
            "error": int(record.get("error", 0)),
            "error_rate": _to_decimal(record.get("error_rate", 0.0)),
            "timeout": int(record.get("timeout", 0)),
            "request_success": int(record.get("request_success", 0)),
        }
        self.table.put_item(Item=item)
        logger.info(
            f"Stored monitoring record for {item['service_id']}",
            extra={"service_id": item["service_id"], "action": "store_monitoring"},
        )
        return _from_decimal(item)

    def get_latest_record(self, service_id: str) -> Optional[dict]:
        """Gets the most recent monitoring record for a service."""
        response = self.table.query(
            KeyConditionExpression=Key("service_id").eq(service_id),
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return _from_decimal(items[0]) if items else None

    def get_records(
        self,
        service_id: str,
        limit: int = 100,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict]:
        """Retrieves monitoring records for a service within a time range."""
        key_condition = Key("service_id").eq(service_id)

        if start_time and end_time:
            key_condition = key_condition & Key("timestamp").between(start_time, end_time)
        elif start_time:
            key_condition = key_condition & Key("timestamp").gte(start_time)
        elif end_time:
            key_condition = key_condition & Key("timestamp").lte(end_time)

        response = self.table.query(
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,
            Limit=limit,
        )
        return [_from_decimal(item) for item in response.get("Items", [])]

    def get_historical_records(
        self, service_id: str, hours: int = 24, limit: int = 500
    ) -> list[dict]:
        """Retrieves records from the last N hours for ML training/prediction."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        return self.get_records(
            service_id=service_id,
            limit=limit,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

    def get_all_recent_records(self, hours: int = 1) -> list[dict]:
        """Scans for all recent records across all services. Use sparingly."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        response = self.table.scan(
            FilterExpression=Attr("timestamp").gte(cutoff)
        )
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.table.scan(
                FilterExpression=Attr("timestamp").gte(cutoff),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return [_from_decimal(item) for item in items]

    def get_record_count(self, service_id: str) -> int:
        """Returns the total record count for a service (for ML training decisions)."""
        response = self.table.query(
            KeyConditionExpression=Key("service_id").eq(service_id),
            Select="COUNT",
        )
        return response.get("Count", 0)
