"""Dumps the current OpenAPI schema to docs/openapi.json.

Run after changing any router/schema so the committed spec stays in sync:
    .venv/bin/python scripts/export_openapi.py
"""
import json
from pathlib import Path

from app.main import app

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"

if __name__ == "__main__":
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
