from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, asdict


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "inference_called": False,
        "real_order": False,
        "submitted": 0,
        "shadow_only": True,
        "research_mode": True,
        "selection_only": True,
    }


@dataclass
class OllamaModelSelectionResult:
    selected_model: str
    selected: bool
    reason: str
    preferred_model: str
    fallback_used: bool
    candidate_count: int
    metadata: dict = field(default_factory=_metadata)


class OllamaModelSelector:
    """Selects an AITS local model candidate from inventory data."""

    def select(self, inventory_result) -> OllamaModelSelectionResult:
        inv = self._to_dict(inventory_result)
        model_names = self._model_names(inv.get("models") or [])
        preferred = str(inv.get("preferred_model") or "qwen2.5:7b-instruct-q4")
        if bool(inv.get("preferred_model_found")) and preferred:
            return self._result(preferred, True, "preferred_model", preferred, False, model_names)
        for prefix, reason in (
            ("qwen2.5", "fallback_qwen25"),
            ("qwen", "fallback_qwen"),
            ("llama", "fallback_llama"),
            ("mistral", "fallback_mistral"),
        ):
            selected = self._find_by_prefix(model_names, prefix)
            if selected:
                return self._result(selected, True, reason, preferred, True, model_names)
        if model_names:
            return self._result(model_names[0], True, "fallback_first_model", preferred, True, model_names)
        return self._result("", False, "no_models", preferred, False, model_names)

    def _result(
        self,
        selected_model: str,
        selected: bool,
        reason: str,
        preferred: str,
        fallback_used: bool,
        model_names: list[str],
    ) -> OllamaModelSelectionResult:
        metadata = _metadata()
        metadata.update({"candidate_models": list(model_names)})
        return OllamaModelSelectionResult(
            selected_model=str(selected_model or ""),
            selected=bool(selected),
            reason=str(reason or "unknown"),
            preferred_model=str(preferred or ""),
            fallback_used=bool(fallback_used),
            candidate_count=len(model_names),
            metadata=metadata,
        )

    def _model_names(self, models: list) -> list[str]:
        names: list[str] = []
        for model in models:
            data = self._to_dict(model)
            name = str(data.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    def _find_by_prefix(self, names: list[str], prefix: str) -> str:
        p = str(prefix or "").lower()
        for name in names:
            if str(name or "").lower().startswith(p):
                return name
        return ""

    def _to_dict(self, value) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_ollama_model_selection() -> OllamaModelSelectionResult:
    from app.services.ollama_model_inventory import OllamaModelInventory

    return OllamaModelSelector().select(OllamaModelInventory().list_models())


__all__ = [
    "OllamaModelSelectionResult",
    "OllamaModelSelector",
    "build_sample_ollama_model_selection",
]
