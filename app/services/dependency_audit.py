from __future__ import annotations

import importlib.metadata
import importlib.util
from dataclasses import dataclass, field


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "audit_only": True,
        "pip_executed": False,
    }


@dataclass
class DependencyAuditItem:
    package: str
    import_name: str
    installed: bool
    version: str
    required_by: str
    severity: str
    note: str


@dataclass
class DependencyAuditResult:
    total: int
    installed: int
    missing: int
    missing_packages: list
    items: list
    metadata: dict = field(default_factory=_metadata)


DEPENDENCIES = [
    {
        "package": "cryptography",
        "import_name": "cryptography",
        "required_by": "encrypted prefs and secrets handling",
        "severity": "critical",
        "note": "Required by app.utils.prefs.",
    },
    {
        "package": "pydantic",
        "import_name": "pydantic",
        "required_by": "settings schema",
        "severity": "critical",
        "note": "Required by app.utils.settings_schema.",
    },
    {
        "package": "PySide6",
        "import_name": "PySide6",
        "required_by": "desktop UI",
        "severity": "critical",
        "note": "Required for GUI startup.",
    },
    {
        "package": "pandas",
        "import_name": "pandas",
        "required_by": "market data and reports",
        "severity": "high",
        "note": "Used by data and chart workflows.",
    },
    {
        "package": "matplotlib",
        "import_name": "matplotlib",
        "required_by": "charts",
        "severity": "high",
        "note": "Required by mplfinance/chart rendering.",
    },
    {
        "package": "mplfinance",
        "import_name": "mplfinance",
        "required_by": "candlestick charts",
        "severity": "high",
        "note": "Listed in current requirements.txt.",
    },
    {
        "package": "requests",
        "import_name": "requests",
        "required_by": "HTTP utilities and provider tests",
        "severity": "high",
        "note": "Import check only; no network call.",
    },
    {
        "package": "pyupbit",
        "import_name": "pyupbit",
        "required_by": "Upbit data/account adapters",
        "severity": "high",
        "note": "Import check only; no exchange call.",
    },
    {
        "package": "openai",
        "import_name": "openai",
        "required_by": "OpenAI provider bridge",
        "severity": "medium",
        "note": "Import check only; no provider call.",
    },
    {
        "package": "google-generativeai",
        "import_name": "google.generativeai",
        "required_by": "Gemini provider bridge",
        "severity": "medium",
        "note": "Import check only; no provider call.",
    },
    {
        "package": "numpy",
        "import_name": "numpy",
        "required_by": "numeric processing",
        "severity": "high",
        "note": "Installed as pandas/matplotlib dependency in many setups.",
    },
    {
        "package": "python-dotenv",
        "import_name": "dotenv",
        "required_by": "environment loading",
        "severity": "high",
        "note": "Listed in current requirements.txt.",
    },
]


class DependencyAuditor:
    """Audits package availability without installing or calling providers."""

    def audit(self) -> DependencyAuditResult:
        items = [self._audit_item(spec) for spec in DEPENDENCIES]
        installed_count = sum(1 for item in items if item.installed)
        missing_packages = [item.package for item in items if not item.installed]
        metadata = _metadata()
        metadata.update(
            {
                "provider_api_called": False,
                "ollama_executed": False,
                "orders_touched": False,
                "requirements_modified": False,
            }
        )
        return DependencyAuditResult(
            total=len(items),
            installed=installed_count,
            missing=len(missing_packages),
            missing_packages=missing_packages,
            items=items,
            metadata=metadata,
        )

    def _audit_item(self, spec: dict) -> DependencyAuditItem:
        package = str(spec.get("package") or "")
        import_name = str(spec.get("import_name") or package)
        try:
            installed = importlib.util.find_spec(import_name) is not None
        except ModuleNotFoundError:
            installed = False
        version = "-"
        if installed:
            version = self._version_for(package)
        return DependencyAuditItem(
            package=package,
            import_name=import_name,
            installed=installed,
            version=version,
            required_by=str(spec.get("required_by") or "-"),
            severity=str(spec.get("severity") or "medium"),
            note=str(spec.get("note") or ""),
        )

    def _version_for(self, package: str) -> str:
        try:
            return importlib.metadata.version(package)
        except Exception:
            return "installed"


def build_sample_dependency_audit() -> DependencyAuditResult:
    return DependencyAuditor().audit()


__all__ = [
    "DependencyAuditItem",
    "DependencyAuditResult",
    "DependencyAuditor",
    "build_sample_dependency_audit",
]
