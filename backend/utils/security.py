"""Administrator authentication and cached Secrets Manager retrieval."""
import hmac
import json
from functools import lru_cache
import boto3
from backend.utils.config import get_settings


@lru_cache(maxsize=8)
def read_secret(arn):
    response = boto3.client("secretsmanager", region_name=get_settings().aws_region).get_secret_value(SecretId=arn)
    value = response["SecretString"]
    try:
        parsed = json.loads(value)
        return parsed.get("token") or parsed.get("api_key")
    except json.JSONDecodeError:
        return value


def authenticate(authorization):
    settings = get_settings()
    token = read_secret(settings.admin_secret_arn) if settings.admin_secret_arn else settings.admin_token
    if not token:
        if settings.environment.lower() in {"dev", "development", "local", "test"}:
            return "local-operator"
        return None
    supplied = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    return "administrator" if supplied and hmac.compare_digest(supplied, token) else None
