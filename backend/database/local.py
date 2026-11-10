"""Explicit SQLite development storage with atomic conditional writes."""
import json
import sqlite3
from pathlib import Path
from botocore.exceptions import ClientError
DB_PATH = Path(__file__).resolve().parents[2] / '.local_db.sqlite3'

def matches(expr, item):
    if expr is None:
        return True
    data = expr.get_expression()
    values, op = data['values'], data['operator']
    if op in ('AND', 'OR'):
        result = [matches(v, item) for v in values]
        return all(result) if op == 'AND' else any(result)
    actual = item.get(values[0].name)
    expected = values[1] if len(values) > 1 else None
    if op == '=': return actual == expected
    if op == '>=': return actual is not None and actual >= expected
    if op == '<=': return actual is not None and actual <= expected
    if op == 'BETWEEN': return actual is not None and expected <= actual <= values[2]
    raise ValueError(f'Unsupported local condition {op}')

class LocalTable:
    def __init__(self, name):
        from backend.utils.config import get_settings
        s = get_settings()
        self.name = name
        self.keys = (['service_id', 'timestamp'] if name == s.monitoring_table else
            ['incident_id'] if name == s.incident_table else ['analysis_id'] if name == s.ai_analysis_table else ['service_id'])
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS items (table_name TEXT, key TEXT, value TEXT, PRIMARY KEY(table_name,key))')
    def connect(self): return sqlite3.connect(str(DB_PATH), timeout=10)
    def key(self, item): return json.dumps([str(item[k]) for k in self.keys])
    def get_item(self, Key, **kwargs):
        with self.connect() as db:
            row = db.execute('SELECT value FROM items WHERE table_name=? AND key=?', (self.name, self.key(Key))).fetchone()
        return {'Item': json.loads(row[0])} if row else {}
    def put_item(self, Item, **kwargs):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM items WHERE table_name=? AND key=?', (self.name, self.key(Item))).fetchone()
            existing = json.loads(row[0]) if row else {}
            condition = kwargs.get('ConditionExpression')
            if condition:
                values = kwargs.get('ExpressionAttributeValues', {})
                if condition == 'attribute_not_exists(#pk)': valid = not existing
                elif condition == 'attribute_not_exists(#v)': valid = 'version' not in existing
                elif condition == '#v = :expected': valid = existing.get('version') == values[':expected']
                else: raise ValueError(f'Unsupported local write condition {condition}')
                if not valid:
                    raise ClientError({'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Write conflict'}}, 'PutItem')
            db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?)', (self.name, self.key(Item), json.dumps(Item, default=float)))
        return {}
    def delete_item(self, Key, **kwargs):
        with self.connect() as db:
            db.execute('DELETE FROM items WHERE table_name=? AND key=?', (self.name, self.key(Key)))
        return {}
    def scan(self, **kwargs):
        with self.connect() as db:
            rows = db.execute('SELECT value FROM items WHERE table_name=? ORDER BY key', (self.name,)).fetchall()
        items = [json.loads(row[0]) for row in rows]
        items = [i for i in items if matches(kwargs.get('FilterExpression'), i)]
        items = items[:kwargs.get('Limit', len(items))]
        return {'Items': items, 'Count': len(items)}
    def query(self, **kwargs):
        items = [i for i in self.scan()['Items'] if matches(kwargs.get('KeyConditionExpression'), i)]
        sort_key = 'created_at' if kwargs.get('IndexName') == 'ServiceIndex' and 'incident_id' in self.keys else 'timestamp'
        items.sort(key=lambda i: i.get(sort_key, ''), reverse=not kwargs.get('ScanIndexForward', True))
        items = items[:kwargs.get('Limit', len(items))]
        return {'Items': items, 'Count': len(items)}
    def update_item(self, Key, **kwargs):
        item = self.get_item(Key).get('Item', dict(Key))
        names, values = kwargs.get('ExpressionAttributeNames', {}), kwargs.get('ExpressionAttributeValues', {})
        expr = kwargs['UpdateExpression']
        if not expr.startswith('SET '): raise ValueError('Unsupported local update')
        for assignment in expr[4:].split(','):
            key, value = assignment.strip().split(' = ')
            item[names.get(key, key)] = values[value]
        self.put_item(Item=item)
        return {'Attributes': item}
