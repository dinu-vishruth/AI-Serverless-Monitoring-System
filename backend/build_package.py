"""SAM Makefile builder: ship backend sources only, never .env or local data."""
import os
import shutil
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
artifacts = Path(os.environ['ARTIFACTS_DIR'])
if sys.argv[1] == 'code':
    shutil.copytree(root, artifacts / 'backend', dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('venv', '.venv', '.env*', '__pycache__', '*.pyc', 'Makefile', 'build_package.py', '*requirements*.txt'))
    code_size = sum(p.stat().st_size for p in artifacts.rglob('*') if p.is_file())
    if code_size >= 1024 * 1024:
        raise RuntimeError('Code package exceeds the 1 MiB reserved combined-size budget')
else:
    import subprocess
    if sys.argv[1] != 'prune':
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'requirements-lambda.txt'), '-t', str(artifacts / 'python'), '--no-compile'])
    # Keep the pinned SDK and its shared endpoint metadata, but ship service
    # models only for clients used by this application or credential providers.
    service_models = artifacts / 'python' / 'botocore' / 'data'
    required_services = {'dynamodb', 's3', 'sns', 'secretsmanager', 'bedrock-runtime', 'sts', 'sso', 'sso-oidc'}
    for directory in service_models.iterdir():
        if directory.is_dir() and directory.name not in required_services:
            shutil.rmtree(directory)
    # NumPy's public testing module is imported by SciPy at runtime and depends
    # on this helper despite its location in an upstream tests directory.
    helper_paths = [artifacts / 'python' / 'numpy' / '_core' / 'tests' / name for name in ('__init__.py', '_natype.py')]
    runtime_helpers = {path:path.read_bytes() for path in helper_paths if path.exists()}
    # Wheels include their upstream test suites. They are not runtime code and
    # would push scipy/pandas/sklearn beyond Lambda's combined 250 MiB limit.
    for directory in list((artifacts / 'python').rglob('*')):
        if directory.is_dir() and directory.name in {'tests', 'test', '__pycache__'}:
            shutil.rmtree(directory)
    for path, data in runtime_helpers.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    size = sum(p.stat().st_size for p in artifacts.rglob('*') if p.is_file())
    print(f'Runtime layer size: {size / 1024 / 1024:.1f} MiB')
    if size >= 235 * 1024 * 1024:
        raise RuntimeError('Runtime layer exceeds safe Lambda package size')
    verification_env = dict(os.environ, PYTHONPATH=str(artifacts / 'python'), PYTHONDONTWRITEBYTECODE='1')
    subprocess.check_call([sys.executable, '-c', 'import boto3; services=["dynamodb","s3","sns","secretsmanager","bedrock-runtime","sts","sso","sso-oidc"]; clients=[boto3.client(s,region_name="ap-south-2",aws_access_key_id="build",aws_secret_access_key="build") for s in services]; boto3.resource("dynamodb",region_name="ap-south-2",aws_access_key_id="build",aws_secret_access_key="build"); print("PRUNED_SDK_CLIENTS_OK")'], env=verification_env)
    subprocess.check_call([sys.executable, '-c', 'import fastapi, numpy, pandas, sklearn; from sklearn.ensemble import IsolationForest; m=IsolationForest(n_estimators=2,n_jobs=1).fit(numpy.array([[1.],[2.],[3.]])); assert numpy.isfinite(m.decision_function([[2.]])).all(); print("PRUNED_LAYER_IMPORT_AND_INFERENCE_OK")'], env=verification_env)
