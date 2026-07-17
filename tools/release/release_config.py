from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = ROOT / "release"
OUTPUT_ROOT = RELEASE_ROOT / "output"
BUILD_ROOT = RELEASE_ROOT / "build"
MANIFEST_ROOT = RELEASE_ROOT / "manifests"
CANONICAL_SPEC = RELEASE_ROOT / "pyinstaller" / "AITS.spec"
SENSITIVE_NAMES = {".env", "secrets.json", "secret.bin", "prefs.json", "credentials.json"}
FORBIDDEN_PARTS = {"data", "logs", "backups", "archive", "cache", "temp", ".git", ".venv", "__pycache__"}
FORBIDDEN_MODEL_SUFFIXES = {".gguf", ".ollama"}
REQUIRED_QT_PLUGIN_DIRS = ("_internal/PySide6/plugins/platforms", "_internal/PySide6/plugins/imageformats")
