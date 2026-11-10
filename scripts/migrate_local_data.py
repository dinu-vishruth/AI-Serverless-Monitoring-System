"""Copy legacy JSON records into local SQLite without changing the source file."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.utils.config import get_settings
from backend.database.local import LocalTable

settings = get_settings()
if settings.environment.lower() not in {"development", "dev", "local", "test"}:
    raise SystemExit("Migration is local-only; set ENVIRONMENT=development")
source = Path(__file__).resolve().parents[1] / ".local_db.json"
numeric = {"response_time", "status_code", "availability", "error", "error_rate", "timeout", "request_success", "risk_score", "anomaly_score", "check_interval", "response_time_threshold", "error_threshold", "expected_status_code"}
def normalize(value):
    if isinstance(value, list): return [normalize(v) for v in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in numeric and isinstance(item, str):
                try: item = float(item)
                except ValueError: pass
            result[key] = normalize(item)
        return result
    return value
tables = json.loads(source.read_text(encoding="utf-8"))
count = 0
for name, items in tables.items():
    table = LocalTable(name)
    for raw in items:
        item = normalize(raw)
        key = {k:item[k] for k in table.keys}
        if not table.get_item(Key=key):
            table.put_item(Item=item)
            count += 1
print(f"Imported {count} missing local records; original JSON retained")
