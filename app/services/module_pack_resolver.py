from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.module_pack_state import (
    ModuleDefinition,
    ModulePackDefinition,
    ModulePackRuntimeState,
    UserModulePackSelection,
)


class ModulePackResolver:
    def __init__(
        self,
        pack_definitions: Optional[List[ModulePackDefinition]] = None,
        base_pack_id: str = "ai_default",
        logger: Optional[Any] = None,
    ) -> None:
        self.pack_definitions = pack_definitions or []
        self.base_pack_id = base_pack_id
        self.logger = logger
        self._pack_index = self._build_pack_index(self.pack_definitions)

    def resolve(
        self,
        selection: Optional[UserModulePackSelection],
        current_time: Optional[datetime] = None,
    ) -> ModulePackRuntimeState:
        now = current_time or datetime.now()
        try:
            if selection is None:
                return self._default_runtime_state("AI 기본 모드로 동작 중입니다.")

            active_pack_id = (getattr(selection, "active_pack_id", None) or "").strip()
            is_active = bool(getattr(selection, "is_active", False))
            if not is_active or not active_pack_id:
                return self._default_runtime_state("AI 기본 모드로 동작 중입니다.")

            pack = self.get_pack_definition(active_pack_id)
            if pack is None:
                return self._default_runtime_state(
                    "선택된 모듈팩을 찾지 못해 AI 기본 모드로 전환합니다."
                )

            timer_enabled = bool(getattr(selection, "timer_enabled", False))
            raw_remaining = getattr(selection, "remaining_seconds", 0)
            try:
                remaining_seconds = int(raw_remaining)
            except (TypeError, ValueError):
                remaining_seconds = 0
            if remaining_seconds < 0:
                remaining_seconds = 0

            if timer_enabled:
                activated_at = getattr(selection, "activated_at", None)
                duration_minutes = getattr(selection, "duration_minutes", 0)
                if isinstance(activated_at, datetime):
                    try:
                        dmin = int(duration_minutes)
                    except (TypeError, ValueError):
                        dmin = 0
                    if dmin > 0:
                        elapsed = int((now - activated_at).total_seconds())
                        if elapsed >= 0:
                            computed = max(0, dmin * 60 - elapsed)
                            if remaining_seconds <= 0:
                                remaining_seconds = computed

                expired = self._is_selection_expired(selection, now)
                if not expired and remaining_seconds <= 0:
                    expires_at = getattr(selection, "expires_at", None)
                    if isinstance(expires_at, datetime):
                        expired = now >= expires_at
                    else:
                        expired = True
                if expired:
                    auto_revert = bool(getattr(selection, "auto_revert_to_ai_default", True))
                    if auto_revert:
                        return self._default_runtime_state(
                            "모듈팩 시간이 종료되어 AI 기본 모드로 복귀했습니다."
                        )
                    return self._default_runtime_state("모듈팩이 만료되었습니다.")

            pack_name_ko = str(getattr(pack, "pack_name_ko", "") or "모듈팩")
            preferred = list(getattr(pack, "preferred_modules", []) or [])
            suppressed = list(getattr(pack, "suppressed_modules", []) or [])
            risk_bias = str(getattr(pack, "risk_bias_override", "") or "none")
            asset_scope = str(getattr(pack, "asset_scope_override", "") or "all")
            buy_delta = float(getattr(pack, "buy_bias_delta", 0.0) or 0.0)
            wait_delta = float(getattr(pack, "wait_bias_delta", 0.0) or 0.0)
            reduce_delta = float(getattr(pack, "reduce_bias_delta", 0.0) or 0.0)
            sell_delta = float(getattr(pack, "sell_bias_delta", 0.0) or 0.0)
            exit_delta = float(getattr(pack, "exit_strictness_delta", 0.0) or 0.0)

            if timer_enabled:
                summary_ko = (
                    f"{pack_name_ko} 팩이 활성화되어 있으며, 남은 시간은 "
                    f"{self._format_remaining_time(remaining_seconds)}입니다."
                )
            else:
                summary_ko = f"{pack_name_ko} 팩이 활성화되어 있으며, 해제 전까지 계속 적용됩니다."

            return ModulePackRuntimeState(
                active_pack_id=str(getattr(pack, "pack_id", "") or active_pack_id),
                pack_name_ko=pack_name_ko,
                effective_preferred_modules=preferred,
                effective_suppressed_modules=suppressed,
                effective_risk_bias=risk_bias,
                effective_asset_scope=asset_scope,
                effective_buy_bias_delta=buy_delta,
                effective_wait_bias_delta=wait_delta,
                effective_reduce_bias_delta=reduce_delta,
                effective_sell_bias_delta=sell_delta,
                effective_exit_strictness_delta=exit_delta,
                timer_enabled=timer_enabled,
                remaining_seconds=max(0, remaining_seconds),
                expired=False,
                runtime_summary_ko=summary_ko or "모듈팩이 활성 상태입니다.",
            )
        except Exception as exc:
            self._safe_log_debug(f"resolve fallback: {exc}")
            return self._default_runtime_state(
                "모듈팩 해석 중 문제가 발생하여 AI 기본 모드로 전환합니다."
            )

    def tick(
        self,
        selection: Optional[UserModulePackSelection],
        current_time: Optional[datetime] = None,
    ) -> ModulePackRuntimeState:
        try:
            return self.resolve(selection=selection, current_time=current_time)
        except Exception as exc:
            self._safe_log_debug(f"tick fallback: {exc}")
            return self._default_runtime_state(
                "모듈팩 해석 중 문제가 발생하여 AI 기본 모드로 전환합니다."
            )

    def clear_selection(
        self,
        selection: Optional[UserModulePackSelection],
    ) -> UserModulePackSelection:
        try:
            sel = selection or UserModulePackSelection()
            sel.active_pack_id = None
            sel.is_active = False
            sel.timer_enabled = False
            sel.duration_minutes = 0
            sel.remaining_seconds = 0
            sel.activated_at = None
            sel.expires_at = None
            sel.auto_revert_to_ai_default = True
            sel.status_text_ko = "AI 기본 모드"
            sel.selection_reason = ""
            if not hasattr(sel, "manual_deactivation_allowed"):
                setattr(sel, "manual_deactivation_allowed", True)
            return sel
        except Exception as exc:
            self._safe_log_debug(f"clear_selection fallback: {exc}")
            try:
                return UserModulePackSelection(
                    active_pack_id=None,
                    is_active=False,
                    timer_enabled=False,
                    duration_minutes=0,
                    remaining_seconds=0,
                    activated_at=None,
                    expires_at=None,
                    auto_revert_to_ai_default=True,
                    status_text_ko="AI 기본 모드",
                    selection_reason="",
                    manual_deactivation_allowed=True,
                )
            except Exception:
                return UserModulePackSelection()

    def get_pack_definition(
        self,
        pack_id: Optional[str],
    ) -> Optional[ModulePackDefinition]:
        try:
            if not pack_id:
                return None
            return self._pack_index.get(str(pack_id))
        except Exception as exc:
            self._safe_log_debug(f"get_pack_definition fallback: {exc}")
            return None

    def _build_pack_index(self, packs: List[ModulePackDefinition]) -> Dict[str, ModulePackDefinition]:
        index: Dict[str, ModulePackDefinition] = {}
        for pack in packs:
            try:
                pid = str(getattr(pack, "pack_id", "") or "").strip()
                if pid:
                    index[pid] = pack
            except Exception:
                continue
        return index

    def _default_runtime_state(
        self,
        summary_ko: str = "AI 기본 모드로 동작 중입니다.",
    ) -> ModulePackRuntimeState:
        text = summary_ko.strip() or "AI 기본 모드로 동작 중입니다."
        return ModulePackRuntimeState(
            active_pack_id=None,
            pack_name_ko="AI 기본 모드",
            effective_preferred_modules=[],
            effective_suppressed_modules=[],
            effective_risk_bias="none",
            effective_asset_scope="all",
            effective_buy_bias_delta=0.0,
            effective_wait_bias_delta=0.0,
            effective_reduce_bias_delta=0.0,
            effective_sell_bias_delta=0.0,
            effective_exit_strictness_delta=0.0,
            timer_enabled=False,
            remaining_seconds=0,
            expired=False,
            runtime_summary_ko=text,
        )

    def _is_selection_expired(
        self,
        selection: UserModulePackSelection,
        current_time: datetime,
    ) -> bool:
        try:
            raw_remaining = getattr(selection, "remaining_seconds", 0)
            try:
                remaining_seconds = int(raw_remaining)
            except (TypeError, ValueError):
                remaining_seconds = 0
            if remaining_seconds <= 0:
                return True
            expires_at = getattr(selection, "expires_at", None)
            if isinstance(expires_at, datetime) and current_time >= expires_at:
                return True
            return False
        except Exception:
            return True

    def _format_remaining_time(self, remaining_seconds: int) -> str:
        try:
            seconds = int(remaining_seconds)
        except (TypeError, ValueError):
            seconds = 0
        if seconds < 0:
            seconds = 0
        duration = timedelta(seconds=seconds)
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
        except Exception:
            pass

    def _safe_log_debug(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "debug"):
                self.logger.debug(message)
        except Exception:
            pass
