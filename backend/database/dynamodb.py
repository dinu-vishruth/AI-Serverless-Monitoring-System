"""
DynamoDB client factory — provides a shared boto3 DynamoDB resource
with an in-memory & file-backed fallback for offline/local/test execution.
"""

import json
import os
from typing import Optional, Dict, Any, List
from backend.utils.config import get_settings


class MockCondition:
    """Mock DynamoDB Condition for local testing."""
    def __init__(self, name: str, op: str = "noop", val: Any = None, val2: Any = None):
        self.name = name
        self.op = op
        self.val = val
        self.val2 = val2
        self.children: List['MockCondition'] = []
        self.logical_op = "AND"

    def eq(self, val):
        return MockCondition(self.name, "eq", val)

    def gte(self, val):
        return MockCondition(self.name, "gte", val)

    def lte(self, val):
        return MockCondition(self.name, "lte", val)

    def between(self, val1, val2):
        return MockCondition(self.name, "between", val1, val2)

    def begins_with(self, val):
        return MockCondition(self.name, "begins_with", val)

    def __and__(self, other):
        combined = MockCondition(self.name, "combined")
        combined.logical_op = "AND"
        combined.children = [self, other]
        return combined

    def __or__(self, other):
        combined = MockCondition(self.name, "combined")
        combined.logical_op = "OR"
        combined.children = [self, other]
        return combined

    def evaluate(self, item: dict) -> bool:
        if self.op == "combined":
            if self.logical_op == "AND":
                return all(c.evaluate(item) for c in self.children)
            else:
                return any(c.evaluate(item) for c in self.children)

        val = item.get(self.name)
        if self.op == "eq":
            return str(val) == str(self.val) or val == self.val
        elif self.op == "gte":
            return val is not None and str(val) >= str(self.val)
        elif self.op == "lte":
            return val is not None and str(val) <= str(self.val)
        elif self.op == "between":
            return val is not None and str(self.val) <= str(val) <= str(self.val2)
        elif self.op == "begins_with":
            return val is not None and str(val).startswith(str(self.val))
        return True


try:
    import boto3
    from boto3.dynamodb.conditions import Key as BotoKey, Attr as BotoAttr
    Key = BotoKey
    Attr = BotoAttr
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    Key = MockCondition
    Attr = MockCondition

_dynamodb_resource = None
LOCAL_DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".local_db.json"))


class InMemoryTable:
    """Lightweight persistent file-backed DynamoDB Table for local testing without AWS/boto3."""
    _storage: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def _load_storage(cls):
        if os.path.exists(LOCAL_DB_FILE):
            try:
                with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                    cls._storage = json.load(f)
            except Exception:
                pass

    @classmethod
    def _save_storage(cls):
        try:
            with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._storage, f, indent=2, default=str)
        except Exception:
            pass

    def __init__(self, name: str):
        self.name = name
        InMemoryTable._load_storage()
        if name not in InMemoryTable._storage:
            InMemoryTable._storage[name] = []

    def put_item(self, Item: Dict[str, Any]):
        InMemoryTable._load_storage()
        items = InMemoryTable._storage.setdefault(self.name, [])
        key_name = None
        for k in ["service_id", "incident_id", "analysis_id"]:
            if k in Item:
                key_name = k
                break

        if key_name:
            if "timestamp" in Item:
                InMemoryTable._storage[self.name] = [
                    i for i in items if not (str(i.get(key_name)) == str(Item[key_name]) and str(i.get("timestamp")) == str(Item["timestamp"]))
                ]
            else:
                InMemoryTable._storage[self.name] = [i for i in items if str(i.get(key_name)) != str(Item[key_name])]

        InMemoryTable._storage[self.name].append(dict(Item))
        InMemoryTable._save_storage()
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, Key: Dict[str, Any]):
        InMemoryTable._load_storage()
        items = InMemoryTable._storage.get(self.name, [])
        for i in items:
            if all(str(i.get(k)) == str(v) for k, v in Key.items()):
                return {"Item": dict(i)}
        return {}

    def delete_item(self, Key: Dict[str, Any]):
        InMemoryTable._load_storage()
        items = InMemoryTable._storage.get(self.name, [])
        InMemoryTable._storage[self.name] = [
            i for i in items if not all(str(i.get(k)) == str(v) for k, v in Key.items())
        ]
        InMemoryTable._save_storage()
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def scan(self, **kwargs):
        InMemoryTable._load_storage()
        items = list(InMemoryTable._storage.get(self.name, []))
        filter_expr = kwargs.get("FilterExpression")
        if filter_expr and hasattr(filter_expr, "evaluate"):
            items = [i for i in items if filter_expr.evaluate(i)]

        limit = kwargs.get("Limit")
        if limit:
            items = items[:limit]
        return {"Items": items, "Count": len(items)}

    def query(self, **kwargs):
        InMemoryTable._load_storage()
        items = list(InMemoryTable._storage.get(self.name, []))
        key_cond = kwargs.get("KeyConditionExpression")
        if key_cond and hasattr(key_cond, "evaluate"):
            items = [i for i in items if key_cond.evaluate(i)]

        scan_forward = kwargs.get("ScanIndexForward", True)
        if any("timestamp" in i for i in items):
            items.sort(key=lambda x: str(x.get("timestamp", "")), reverse=not scan_forward)
        elif any("created_at" in i for i in items):
            items.sort(key=lambda x: str(x.get("created_at", "")), reverse=not scan_forward)

        limit = kwargs.get("Limit")
        if limit:
            items = items[:limit]

        select = kwargs.get("Select")
        if select == "COUNT":
            return {"Count": len(items), "Items": []}

        return {"Items": items, "Count": len(items)}

    def update_item(self, Key: Dict[str, Any], **kwargs):
        res = self.get_item(Key)
        item = res.get("Item", dict(Key))
        vals = kwargs.get("ExpressionAttributeValues", {})
        for k, v in vals.items():
            clean_k = k.lstrip(":")
            item[clean_k] = v
        self.put_item(item)
        return {"Attributes": item}


def get_dynamodb_resource():
    """Returns a cached DynamoDB resource or None if using in-memory mock."""
    global _dynamodb_resource
    if not HAS_BOTO3:
        return None

    settings = get_settings()
    if settings.environment.lower() in {"development", "dev", "local", "test"}:
        return None

    if _dynamodb_resource is None:
        try:
            _dynamodb_resource = boto3.resource("dynamodb", region_name=settings.aws_region)
        except Exception:
            _dynamodb_resource = None
    return _dynamodb_resource


def get_table(table_name: str):
    """Returns a DynamoDB Table object or InMemoryTable fallback."""
    resource = get_dynamodb_resource()
    if resource is not None:
        try:
            return resource.Table(table_name)
        except Exception:
            pass
    return InMemoryTable(table_name)
