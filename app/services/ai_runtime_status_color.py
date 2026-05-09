from __future__ import annotations


class AIRuntimeStatusColorResolver:
    """Resolves runtime status to string color tokens only."""

    def resolve(self, status: str) -> dict:
        status_text = str(status or "").strip()
        palette = {
            "정상": {"bg": "#E8F5E9", "fg": "#1B5E20", "accent": "#43A047"},
            "관찰 필요": {"bg": "#FFF8E1", "fg": "#7A4F00", "accent": "#F9A825"},
            "불안정": {"bg": "#FBE9E7", "fg": "#8A1C0A", "accent": "#E64A19"},
            "런타임 불안정": {"bg": "#FBE9E7", "fg": "#8A1C0A", "accent": "#E64A19"},
            "차단 필요": {"bg": "#FFEBEE", "fg": "#8B0000", "accent": "#C62828"},
        }
        return dict(palette.get(status_text) or palette["관찰 필요"])


def build_sample_status_color() -> dict:
    return AIRuntimeStatusColorResolver().resolve("정상")


__all__ = [
    "AIRuntimeStatusColorResolver",
    "build_sample_status_color",
]
