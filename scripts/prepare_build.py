"""Stage only deployable backend files for workspaces containing nested venvs.

Normal clean checkouts can use `sam build --use-container` directly. For this
workspace use `sam build --use-container --base-dir .build-source` after staging.
The SAM template and runtime package layout are unchanged.
"""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
destination = root / ".build-source" / "backend"
shutil.copytree(root / "backend", destination, dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("venv", ".venv", "__pycache__", "*.pyc", ".env*"))
print("Prepared deployable sources in .build-source/backend")
