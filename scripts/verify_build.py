"""Verify SAM artifacts match current sources and fit Lambda's combined limit."""
import hashlib
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "backend"
build = root / ".aws-sam" / "build"
expected = {}
for directory, children, files in os.walk(source):
    children[:] = [c for c in children if c not in {"venv", ".venv", "__pycache__"}]
    for name in files:
        path = Path(directory) / name
        if path.suffix == ".py" and name != "build_package.py":
            expected[path.relative_to(source)] = hashlib.sha256(path.read_bytes()).hexdigest()
layer = build / "PythonDependencies"
layer_size = sum(p.stat().st_size for p in layer.rglob("*") if p.is_file())
assert layer_size, "Missing dependency layer"
for function in ("ApiFunction", "HealthCheckerFunction", "AnomalyDetectorFunction", "IncidentAnalyzerFunction", "DemoFunction"):
    package = build / function
    for relative, digest in expected.items():
        deployed = package / "backend" / relative
        assert deployed.is_file() and hashlib.sha256(deployed.read_bytes()).hexdigest() == digest, f"Stale/missing artifact: {function}/{relative}"
    files = [p for p in package.rglob("*") if p.is_file()]
    assert not any(p.name.startswith(".env") or "venv" in p.parts or "node_modules" in p.parts or p.name.startswith(".local_db") for p in files)
    combined = layer_size + sum(p.stat().st_size for p in files)
    assert combined < 240 * 1024 * 1024, f"Lambda package exceeds deployment headroom: {function}"
    print(f"{function}: {len(expected)} source files match; combined size {combined / 1024 / 1024:.2f} MiB")
