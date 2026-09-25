"""
Service repository — CRUD operations for monitored service configurations.

DynamoDB Table: Services
  Partition Key: service_id (S)
"""

from typing import Optional, List
from datetime import datetime, timezone
from backend.database.dynamodb import get_table, Key, Attr
from backend.utils.config import get_settings
from backend.utils.logger import get_logger
from backend.utils.validators import generate_service_id

logger = get_logger(__name__)


class ServiceRepository:
    """Manages monitored service configurations in DynamoDB."""

    def __init__(self):
        settings = get_settings()
        self.table = get_table(settings.services_table)

    def create_service(self, service: dict) -> dict:
        """Creates a new monitored service configuration."""
        now = datetime.now(timezone.utc).isoformat()
        service_id = service.get("service_id") or generate_service_id(service.get("service_name", "svc"))
        item = {
            "service_id": service_id,
            "service_name": service.get("service_name", ""),
            "url": service["url"],
            "http_method": service.get("http_method", "GET"),
            "expected_status_code": int(service.get("expected_status_code", 200)),
            "check_interval": int(service.get("check_interval", 60)),
            "response_time_threshold": float(service.get("response_time_threshold", 2000.0)),
            "error_threshold": float(service.get("error_threshold", 0.05)),
            "timeout": int(service.get("timeout", 10)),
            "is_active": service.get("is_active", True),
            "tags": service.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }
        self.table.put_item(Item=item)
        logger.info(
            f"Created service: {item['service_id']}",
            extra={"service_id": item["service_id"], "action": "create_service"},
        )
        return item

    def get_service(self, service_id: str) -> Optional[dict]:
        """Retrieves a service by ID."""
        response = self.table.get_item(Key={"service_id": service_id})
        return response.get("Item")

    def get_all_services(self) -> List[dict]:
        """Returns all monitored services."""
        response = self.table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    def list_services(self) -> List[dict]:
        """Alias for get_all_services."""
        return self.get_all_services()

    def get_active_services(self) -> List[dict]:
        """Returns only active services."""
        if Attr is not None:
            try:
                response = self.table.scan(FilterExpression=Attr("is_active").eq(True))
                items = response.get("Items", [])
                while "LastEvaluatedKey" in response:
                    response = self.table.scan(
                        FilterExpression=Attr("is_active").eq(True),
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                    )
                    items.extend(response.get("Items", []))
                return items
            except Exception:
                pass
        
        # Fallback in-memory filter
        all_services = self.get_all_services()
        return [s for s in all_services if s.get("is_active", True)]

    def update_service(self, service_id: str, updates: dict) -> Optional[dict]:
        """Updates a service configuration."""
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}

        for key, value in updates.items():
            safe_key = f"#k_{key}"
            val_key = f":v_{key}"
            update_expr_parts.append(f"{safe_key} = {val_key}")
            expr_attr_values[val_key] = value
            expr_attr_names[safe_key] = key

        update_expression = "SET " + ", ".join(update_expr_parts)

        response = self.table.update_item(
            Key={"service_id": service_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expr_attr_values,
            ExpressionAttributeNames=expr_attr_names,
            ReturnValues="ALL_NEW",
        )
        logger.info(
            f"Updated service: {service_id}",
            extra={"service_id": service_id, "action": "update_service"},
        )
        return response.get("Attributes") or self.get_service(service_id)

    def delete_service(self, service_id: str) -> bool:
        """Deletes a service configuration."""
        self.table.delete_item(Key={"service_id": service_id})
        logger.info(
            f"Deleted service: {service_id}",
            extra={"service_id": service_id, "action": "delete_service"},
        )
        return True
