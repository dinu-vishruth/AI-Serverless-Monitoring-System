"""
AI analysis repository — stores and retrieves AI/ML analysis results.

DynamoDB Table: AIAnalysis
  Partition Key: analysis_id (S)
  GSI: IncidentIndex — incident_id (S) + timestamp (S)
  GSI: ServiceIndex  — service_id (S) + timestamp (S)
"""

from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from backend.database.dynamodb import get_table, Key, Attr
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_decimal(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_to_decimal(nested_value) for nested_value in value]
    return value


def _from_decimal(item: dict) -> dict:
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


class AIAnalysisRepository:
    """Manages AI analysis results in DynamoDB."""

    def __init__(self):
        settings = get_settings()
        self.table = get_table(settings.ai_analysis_table)

    def store_analysis(self, analysis: dict) -> dict:
        """Stores an AI analysis result."""
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "analysis_id": analysis.get("analysis_id", f"AI-{uuid.uuid4().hex[:8].upper()}"),
            "incident_id": analysis.get("incident_id", ""),
            "service_id": analysis["service_id"],
            "timestamp": analysis.get("timestamp", now),
            "anomaly": analysis.get("anomaly", False),
            "anomaly_score": _to_decimal(analysis.get("anomaly_score", 0)),
            "risk_score": _to_decimal(analysis.get("risk_score", 0)),
            "risk_level": analysis.get("risk_level", "LOW"),
            "incident_summary": analysis.get("incident_summary", ""),
            "observed_facts": analysis.get("observed_facts", []),
            "possible_causes": analysis.get("possible_causes", []),
            "impact": analysis.get("impact", []),
            "recommended_actions": analysis.get("recommended_actions", []),
            "confidence": analysis.get("confidence", "low"),
        }
        self.table.put_item(Item=_to_decimal(item))
        logger.info(
            f"Stored AI analysis: {item['analysis_id']}",
            extra={"service_id": item["service_id"], "action": "store_analysis"},
        )
        return _from_decimal(item)

    def get_analysis(self, analysis_id: str) -> Optional[dict]:
        """Retrieves an analysis by ID."""
        response = self.table.get_item(Key={"analysis_id": analysis_id})
        item = response.get("Item")
        return _from_decimal(item) if item else None

    def get_analysis_by_incident(self, incident_id: str) -> Optional[dict]:
        """Retrieves the AI analysis for a specific incident."""
        try:
            response = self.table.query(
                IndexName="IncidentIndex",
                KeyConditionExpression=Key("incident_id").eq(incident_id),
                ScanIndexForward=False,
                Limit=1,
            )
            items = response.get("Items", [])
            return _from_decimal(items[0]) if items else None
        except Exception:
            # Fallback: scan for the incident_id
            from boto3.dynamodb.conditions import Attr

            response = self.table.scan(
                FilterExpression=Attr("incident_id").eq(incident_id)
            )
            items = response.get("Items", [])
            return _from_decimal(items[0]) if items else None

    def get_service_analyses(self, service_id: str, limit: int = 20) -> list[dict]:
        """Retrieves recent AI analyses for a service."""
        try:
            response = self.table.query(
                IndexName="ServiceIndex",
                KeyConditionExpression=Key("service_id").eq(service_id),
                ScanIndexForward=False,
                Limit=limit,
            )
            return [_from_decimal(item) for item in response.get("Items", [])]
        except Exception:
            from boto3.dynamodb.conditions import Attr

            response = self.table.scan(
                FilterExpression=Attr("service_id").eq(service_id)
            )
            items = response.get("Items", [])
            items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return [_from_decimal(item) for item in items[:limit]]

    def get_recent_analyses(self, limit: int = 50) -> list[dict]:
        """Retrieves the most recent analyses across all services."""
        response = self.table.scan(Limit=limit)
        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return [_from_decimal(item) for item in items]
