"""Explicit environment-selected storage. Production never falls back locally."""
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.config import Config
from backend.utils.config import get_settings
from backend.database.local import LocalTable
HAS_BOTO3 = True
_dynamodb_resource = None
InMemoryTable = LocalTable

def get_dynamodb_resource():
    global _dynamodb_resource
    settings = get_settings()
    if settings.environment.lower() in {'development', 'dev', 'local', 'test'}:
        return None
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource('dynamodb', region_name=settings.aws_region,
            config=Config(connect_timeout=2, read_timeout=4, retries={'mode': 'standard', 'max_attempts': 3}))
    return _dynamodb_resource

def get_table(table_name):
    resource = get_dynamodb_resource()
    return resource.Table(table_name) if resource is not None else LocalTable(table_name)
