"""Optimistic writes shared by local SQLite and DynamoDB."""
from backend.database.service_repository import _to_dynamodb, _from_dynamodb
from botocore.exceptions import ClientError


class Conflict(Exception):
    pass


def save_versioned(table, item, expected=None):
    updated = dict(item, version=(expected or 0) + 1)
    kwargs = dict(Item=_to_dynamodb(updated), ExpressionAttributeNames={"#v": "version"})
    if expected is None:
        kwargs["ConditionExpression"] = "attribute_not_exists(#v)"
    else:
        kwargs.update(ConditionExpression="#v = :expected", ExpressionAttributeValues={":expected": _to_dynamodb(expected)})
    try:
        table.put_item(**kwargs)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Conflict("Concurrent update; retry") from exc
        raise
    return updated


def mutate(table, key, change, attempts=5):
    for _ in range(attempts):
        item = _from_dynamodb(table.get_item(Key=key, ConsistentRead=True).get("Item", {}))
        if not item:
            raise KeyError("Record not found")
        expected = item.get("version")
        result = change(item)
        try:
            saved = save_versioned(table, item, expected)
            return saved, result
        except Conflict:
            continue
    raise Conflict("Concurrent update; retry")
