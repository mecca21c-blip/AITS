from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.aits_state import AITSRuntimeState, ActionItem, ExecutionPlan, ExecutionState
from app.services.aits_orchestrator import CycleResult, ExecutionRequest

# ---------------------------------------------------------------------------
# Bridge types (Phase 1 — dry-run only, no broker calls)
# ---------------------------------------------------------------------------


@dataclass
class BridgeAction:
    action_type: str = "wait"
    symbol: str = ""
    amount_krw: float = 0.0
    quantity: float = 0.0
    priority: int = 0
    reason: str = ""
    source_module: str = ""
    source_provider: str = ""
    blocked: bool = False
    risk_guard: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeResult:
    ok: bool = True
    dry_run: bool = True
    action_count: int = 0
    approved_count: int = 0
    blocked_count: int = 0
    actions: List[BridgeAction] = field(default_factory=list)
    summary: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def has_actions(self) -> bool:
        return self.action_count > 0

    def summary_text(self) -> str:
        return (
            f"BridgeResult(ok={self.ok}, dry_run={self.dry_run}, actions={self.action_count}, "
            f"approved={self.approved_count}, blocked={self.blocked_count})"
        )


class ExecutionBridge:
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        self.config = config if config is not None else {}
        self.logger = logger

    def build_from_cycle_result(self, result: Optional[CycleResult]) -> BridgeResult:
        try:
            if result is None:
                return self._fallback_result(
                    "사이클 결과가 없어 실행 브릿지를 구성할 수 없습니다. dry-run 요약만 유지합니다."
                )
            if not result.status.ok:
                errs = list(result.errors) if result.errors else []
                if "cycle_result_failed" not in errs:
                    errs.insert(0, "cycle_result_failed")
                return BridgeResult(
                    ok=False,
                    dry_run=True,
                    action_count=0,
                    approved_count=0,
                    blocked_count=0,
                    actions=[],
                    summary="사이클 결과가 실패 상태이므로 실행 브릿지를 생성하지 않습니다.",
                    warnings=list(result.warnings) if result.warnings else [],
                    errors=errs,
                )
            if result.execution_request is not None:
                br = self.build_from_execution_request(result.execution_request)
                if not br.summary.strip():
                    br.summary = result.execution_request.request_summary or br.summary
                return br
            if result.runtime_state is not None:
                return self.build_from_runtime_state(result.runtime_state)
            return self._fallback_result(
                "실행 요청과 런타임 상태가 모두 없어 신규 액션 없이 dry-run 계획만 유지합니다."
            )
        except Exception as exc:
            self._safe_log_error(f"build_from_cycle_result: {exc}")
            return BridgeResult(
                ok=False,
                dry_run=True,
                action_count=0,
                approved_count=0,
                blocked_count=0,
                actions=[],
                summary="사이클 기반 브릿지 변환 중 오류가 발생하여 보수적으로 중단했습니다.",
                errors=[str(exc)[:200]],
            )

    def build_from_runtime_state(self, runtime_state: Optional[AITSRuntimeState]) -> BridgeResult:
        try:
            if runtime_state is None:
                return self._fallback_result(
                    "런타임 상태가 없어 실행 브릿지를 구성할 수 없습니다. dry-run만 유지합니다."
                )
            ex: Optional[ExecutionState] = getattr(runtime_state, "execution", None)
            plan: Optional[ExecutionPlan] = getattr(ex, "plan", None) if ex else None
            if plan is None:
                return self._fallback_result(
                    "실행 계획이 없어 현재는 신규 액션이 없으며 dry-run 계획만 유지합니다."
                )
            approved_raw = getattr(plan, "approved_actions", None) or []
            blocked_raw = getattr(plan, "blocked_actions", None) or []
            actions: List[BridgeAction] = []
            for a in approved_raw:
                actions.append(self._to_bridge_action(a, blocked=False))
            for a in blocked_raw:
                actions.append(self._to_bridge_action(a, blocked=True))
            ap = len(approved_raw)
            bp = len(blocked_raw)
            ac = len(actions)
            rs = (getattr(plan, "reason_summary", None) or "").strip()
            if not rs:
                if bp > 0 and ap == 0:
                    rs = "차단된 액션만 존재하여 실제 실행은 보류됩니다."
                elif ac == 0:
                    rs = "현재는 실행 가능한 신규 액션이 없으며 dry-run 계획만 유지합니다."
                else:
                    rs = "실행 계획을 dry-run 기준으로 브릿지에 반영했습니다."
            return BridgeResult(
                ok=True,
                dry_run=True,
                action_count=ac,
                approved_count=ap,
                blocked_count=bp,
                actions=actions,
                summary=rs,
                warnings=[],
                errors=[],
            )
        except Exception as exc:
            self._safe_log_error(f"build_from_runtime_state: {exc}")
            return BridgeResult(
                ok=False,
                dry_run=True,
                action_count=0,
                approved_count=0,
                blocked_count=0,
                actions=[],
                summary="런타임 상태 기반 브릿지 변환 중 오류가 발생했습니다.",
                errors=[str(exc)[:200]],
            )

    def build_from_execution_request(self, request: Optional[ExecutionRequest]) -> BridgeResult:
        try:
            if request is None:
                return self._fallback_result(
                    "실행 요청이 없어 브릿지를 구성할 수 없습니다. dry-run만 유지합니다."
                )
            raw_actions = getattr(request, "actions", None) or []
            actions = [self._to_bridge_action(a, blocked=False) for a in raw_actions]
            n = len(actions)
            sm = (getattr(request, "request_summary", None) or "").strip()
            if not sm:
                if n == 0:
                    sm = "현재는 실행 가능한 신규 액션이 없으며 dry-run 계획만 유지합니다."
                else:
                    sm = "실행 요청을 dry-run 기준으로 변환했습니다."
            dry = bool(getattr(request, "dry_run", True))
            return BridgeResult(
                ok=True,
                dry_run=dry,
                action_count=n,
                approved_count=n,
                blocked_count=0,
                actions=actions,
                summary=sm,
                warnings=[],
                errors=[],
            )
        except Exception as exc:
            self._safe_log_error(f"build_from_execution_request: {exc}")
            return BridgeResult(
                ok=False,
                dry_run=True,
                action_count=0,
                approved_count=0,
                blocked_count=0,
                actions=[],
                summary="실행 요청 기반 브릿지 변환 중 오류가 발생했습니다.",
                errors=[str(exc)[:200]],
            )

    def build_guarded_one_shot_bridge(self, contract: Dict[str, Any]) -> BridgeResult:
        data = dict(contract or {}) if isinstance(contract, dict) else {}
        symbol = str(data.get("symbol") or "").strip().upper()
        side = str(data.get("side") or "").strip().lower()
        try:
            amount_krw = float(data.get("amount_krw") or 0.0)
        except Exception:
            amount_krw = 0.0
        try:
            quantity = float(data.get("quantity") or data.get("volume") or 0.0)
        except Exception:
            quantity = 0.0
        execution_allowed = bool(data.get("execution_allowed", False))
        risk_guard = dict(data.get("risk_guard") or {})
        if not execution_allowed:
            return BridgeResult(
                ok=False,
                dry_run=False,
                action_count=0,
                approved_count=0,
                blocked_count=1,
                actions=[
                    BridgeAction(
                        action_type=side or "buy",
                        symbol=symbol,
                        amount_krw=amount_krw,
                        quantity=quantity,
                        reason=str(data.get("blocker") or "guarded_execution_not_allowed"),
                        source_module="guarded_execution_contract",
                        source_provider=str(data.get("source_provider") or ""),
                        blocked=True,
                        risk_guard=risk_guard,
                    )
                ],
                summary="guarded execution contract is not allowed",
                warnings=[str(data.get("blocker") or "guarded_execution_not_allowed")],
                errors=[],
            )
        action = BridgeAction(
            action_type=side,
            symbol=symbol,
            amount_krw=amount_krw,
            quantity=quantity,
            priority=1,
            reason=str(data.get("request_id") or data.get("source_request_id") or "guarded_one_shot"),
            source_module="guarded_execution_contract",
            source_provider=str(data.get("source_provider") or ""),
            blocked=False,
            risk_guard=risk_guard,
        )
        return BridgeResult(
            ok=True,
            dry_run=False,
            action_count=1,
            approved_count=1,
            blocked_count=0,
            actions=[action],
            summary="guarded one-shot live order bridge",
            warnings=[],
            errors=[],
        )

    def build_live_guarded_window_bridge(self, contract: Dict[str, Any]) -> BridgeResult:
        data = dict(contract or {}) if isinstance(contract, dict) else {}
        symbol = str(data.get("symbol") or "").strip().upper()
        side = str(data.get("side") or "").strip().lower()
        try:
            amount_krw = float(data.get("amount_krw") or 0.0)
        except Exception:
            amount_krw = 0.0
        try:
            quantity = float(data.get("quantity") or data.get("volume") or 0.0)
        except Exception:
            quantity = 0.0
        execution_allowed = bool(data.get("execution_allowed", False))
        risk_guard = dict(data.get("risk_guard") or {})
        risk_guard["live_guarded_window_order"] = True
        risk_guard["live_guarded_one_shot_order"] = False
        if not execution_allowed:
            return BridgeResult(
                ok=False,
                dry_run=False,
                action_count=0,
                approved_count=0,
                blocked_count=1,
                actions=[
                    BridgeAction(
                        action_type=side or "buy",
                        symbol=symbol,
                        amount_krw=amount_krw,
                        quantity=quantity,
                        reason=str(data.get("blocker") or "live_guarded_window_not_allowed"),
                        source_module="live_auto_trading_flow",
                        source_provider=str(data.get("source_provider") or ""),
                        blocked=True,
                        risk_guard=risk_guard,
                    )
                ],
                summary="live guarded-window contract is not allowed",
                warnings=[str(data.get("blocker") or "live_guarded_window_not_allowed")],
                errors=[],
            )
        return BridgeResult(
            ok=True,
            dry_run=False,
            action_count=1,
            approved_count=1,
            blocked_count=0,
            actions=[
                BridgeAction(
                    action_type=side or "buy",
                    symbol=symbol,
                    amount_krw=amount_krw,
                    quantity=quantity,
                    priority=1,
                    reason=str(data.get("request_id") or "live_guarded_window"),
                    source_module="live_auto_trading_flow",
                    source_provider=str(data.get("source_provider") or ""),
                    blocked=False,
                    risk_guard=risk_guard,
                )
            ],
            summary="live guarded-window order bridge",
            warnings=[],
            errors=[],
        )

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
        except Exception:
            pass

    def _safe_log_error(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "error"):
                self.logger.error(message)
        except Exception:
            pass

    def _to_bridge_action(self, action: Any, blocked: bool = False) -> BridgeAction:
        try:
            at = getattr(action, "action_type", None)
            if at is None and isinstance(action, dict):
                at = action.get("action_type", "wait")
            at_s = str(at if at is not None else "wait")

            sym = getattr(action, "symbol", None)
            if sym is None and isinstance(action, dict):
                sym = action.get("symbol", "")
            sym_s = str(sym if sym is not None else "")

            amt = getattr(action, "amount_krw", None)
            if amt is None and isinstance(action, dict):
                amt = action.get("amount_krw", 0.0)
            try:
                amt_f = float(amt if amt is not None else 0.0)
            except (TypeError, ValueError):
                amt_f = 0.0

            qty = getattr(action, "quantity", None)
            if qty is None and isinstance(action, dict):
                qty = action.get("quantity", action.get("volume", 0.0))
            try:
                qty_f = float(qty if qty is not None else 0.0)
            except (TypeError, ValueError):
                qty_f = 0.0

            pr = getattr(action, "priority", None)
            if pr is None and isinstance(action, dict):
                pr = action.get("priority", 0)
            try:
                pr_i = int(pr if pr is not None else 0)
            except (TypeError, ValueError):
                pr_i = 0

            rs = getattr(action, "reason", None)
            if rs is None and isinstance(action, dict):
                rs = action.get("reason", "")
            rs_s = str(rs if rs is not None else "")

            sm = getattr(action, "source_module", None)
            if sm is None and isinstance(action, dict):
                sm = action.get("source_module", "")
            sm_s = str(sm if sm is not None else "")

            sp = getattr(action, "source_provider", None)
            if sp is None and isinstance(action, dict):
                sp = action.get("source_provider", "")
            sp_s = str(sp if sp is not None else "")
            rg = getattr(action, "risk_guard", None)
            if rg is None and isinstance(action, dict):
                rg = action.get("risk_guard", {})
            if not isinstance(rg, dict):
                rg = {}

            return BridgeAction(
                action_type=at_s,
                symbol=sym_s,
                amount_krw=amt_f,
                quantity=qty_f,
                priority=pr_i,
                reason=rs_s,
                source_module=sm_s,
                source_provider=sp_s,
                blocked=blocked,
                risk_guard=dict(rg),
            )
        except Exception:
            return BridgeAction(action_type="wait", symbol="", blocked=blocked)

    def _fallback_result(self, message: str, ok: bool = True) -> BridgeResult:
        return BridgeResult(
            ok=ok,
            dry_run=True,
            action_count=0,
            approved_count=0,
            blocked_count=0,
            actions=[],
            summary=message,
            warnings=[],
            errors=[],
        )
