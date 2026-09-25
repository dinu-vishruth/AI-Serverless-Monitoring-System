"""
Incident repository — manages incident lifecycle in DynamoDB.

DynamoDB Table: Incidents
  Partition Key: incident_id (S)
  GSI: ServiceIndex — service_id (S) + created_at (S)
"""

from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
from backend.database.dynamodb import get_table, Key, Attr
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
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


class IncidentRepository:
    """Manages incident records in DynamoDB."""

    def __init__(self):
        settings = get_settings()
        self.table = get_table(settings.incident_table)

    def create_incident(self, incident: dict) -> dict:
        """Creates a new incident."""
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "incident_id": incident["incident_id"],
            "service_id": incident["service_id"],
            "service_name": incident.get("service_name", ""),
            "created_at": now,
            "updated_at": now,
            "severity": incident.get("severity", "MEDIUM"),
            "status": incident.get("status", "OPEN"),
            "trigger_reason": incident.get("trigger_reason", ""),
            "anomaly_score": _to_decimal(incident.get("anomaly_score", 0)),
            "risk_score": _to_decimal(incident.get("risk_score", 0)),
            "risk_level": incident.get("risk_level", "MEDIUM"),
            "metrics_snapshot": incident.get("metrics_snapshot", {}),
            "resolved_at": None,
        }
        self.table.put_item(Item=item)
        logger.info(
            f"Created incident: {item['incident_id']}",
            extra={"incident_id": item["incident_id"], "action": "create_incident"},
        )
        return _from_decimal(item)

    def get_incident(self, incident_id: str) -> Optional[dict]:
        """Retrieves an incident by ID."""
        response = self.table.get_item(Key={"incident_id": incident_id})
        item = response.get("Item")
        return _from_decimal(item) if item else None

    def get_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieves incidents with optional filters."""
        filter_parts = []
        expr_values = {}
        expr_names = {}

        if status:
            filter_parts.append("#status_key = :status_val")
            expr_values[":status_val"] = status
            expr_names["#status_key"] = "status"

        if severity:
            filter_parts.append("#severity_key = :severity_val")
            expr_values[":severity_val"] = severity
            expr_names["#severity_key"] = "severity"

        scan_kwargs = {"Limit": limit}
        if filter_parts:
            scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
            scan_kwargs["ExpressionAttributeValues"] = expr_values
            scan_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.table.scan(**scan_kwargs)
        items = response.get("Items", [])

        # Sort by created_at descending
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [_from_decimal(item) for item in items]

    def get_service_incidents(self, service_id: str, limit: int = 20) -> list[dict]:
        """Gets incidents for a specific service using GSI."""
        try:
            response = self.table.query(
                IndexName="ServiceIndex",
                KeyConditionExpression=Key("service_id").eq(service_id),
                ScanIndexForward=False,
                Limit=limit,
            )
            return [_from_decimal(item) for item in response.get("Items", [])]
        except Exception:
            # Fallback to scan if GSI doesn't exist
            response = self.table.scan(
                FilterExpression=Attr("service_id").eq(service_id)
            )
            items = response.get("Items", [])
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return [_from_decimal(item) for item in items[:limit]]

    def update_incident_status(
        self, incident_id: str, status: str, resolved_at: Optional[str] = None
    ) -> Optional[dict]:
        """Updates incident status (e.g., OPEN → RESOLVED)."""
        now = datetime.now(timezone.utc).isoformat()
        update_expr = "SET #s = :status, updated_at = :updated"
        expr_values = {":status": status, ":updated": now}
        expr_names = {"#s": "status"}

        if resolved_at or status == "RESOLVED":
            update_expr += ", resolved_at = :resolved"
            expr_values[":resolved"] = resolved_at or now

        response = self.table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
            ReturnValues="ALL_NEW",
        )
        logger.info(
            f"Updated incident {incident_id} to {status}",
            extra={"incident_id": incident_id, "action": "update_incident"},
        )
        return _from_decimal(response.get("Attributes", {}))

    def list_incidents(self, limit: int = 50, status_filter: Optional[str] = None) -> list[dict]:
        """Alias for get_incidents."""
        return self.get_incidents(status=status_filter, limit=limit)

    def get_open_incidents(self, limit: int = 50) -> list[dict]:
        """Returns all open incidents."""
        return self.get_incidents(status="OPEN", limit=limit)

    def get_incidents_by_service(self, service_id: str, limit: int = 20) -> list[dict]:
        """Alias for get_service_incidents."""
        return self.get_service_incidents(service_id=service_id, limit=limit)

    def update_incident(self, incident_id: str, updates: dict) -> Optional[dict]:
        """Generic incident update."""
        existing = self.get_incident(incident_id)
        if not existing:
            return None
        existing.update(updates)
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.table.put_item(Item={k: _to_decimal(v) for k, v in existing.items()})
        return existing

    def get_open_incident_for_service(self, service_id: str) -> Optional[dict]:
        """Checks if there's already an open incident for a service."""
        incidents = self.get_service_incidents(service_id, limit=5)
        for inc in incidents:
            if inc.get("status") == "OPEN":
                return inc
        return None
