from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.execution_bridge import BridgeAction, BridgeResult


@dataclass
class OrderRequestCandidate:
    action_type: str = ""
    symbol: str = ""
    order_side: str = ""
    amount_krw: float = 0.0
    quantity: float = 0.0
    reduce_ratio: float = 0.0
    dry_run: bool = True
    reason: str = ""
    source_module: str = ""
    source_provider: str = ""


@dataclass
class OrderAdapterRecord:
    action_type: str = ""
    symbol: str = ""
    status: str = ""
    reason: str = ""
    detail_ko: str = ""


@dataclass
class OrderAdapterResult:
    ok: bool = True
    execution_mode: str = "disabled"
    submitted_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    candidates: List[OrderRequestCandidate] = field(default_factory=list)
    submitted_orders: List[OrderAdapterRecord] = field(default_factory=list)
    blocked_orders: List[OrderAdapterRecord] = field(default_factory=list)
    failed_orders: List[OrderAdapterRecord] = field(default_factory=list)
    skipped_orders: List[OrderAdapterRecord] = field(default_factory=list)
    summary_ko: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def total_actions(self) -> int:
        return len(self.candidates)

    def summary_text(self) -> str:
        return (
            f"OrderAdapterResult(mode={self.execution_mode}, submitted={self.submitted_count}, "
            f"blocked={self.blocked_count}, failed={self.failed_count}, skipped={self.skipped_count})"
        )


class AITSOrderAdapter:
    def __init__(
        self,
        execution_mode: str = "disabled",
        min_order_krw: float = 5000.0,
        allow_reduce_live: bool = False,
        logger: Optional[Any] = None,
    ) -> None:
        self.execution_mode = execution_mode if self._is_valid_mode(execution_mode) else "disabled"
        self.min_order_krw = self._safe_float(min_order_krw, 5000.0)
        self.allow_reduce_live = bool(allow_reduce_live)
        self.logger = logger

    def set_execution_mode(self, execution_mode: str) -> None:
        self.execution_mode = execution_mode if self._is_valid_mode(execution_mode) else "disabled"

    def build_candidates(self, bridge: Optional[BridgeResult]) -> OrderAdapterResult:
        result = OrderAdapterResult(execution_mode=self.execution_mode)
        try:
            if bridge is None:
                result.ok = False
                result.summary_ko = "실행 브릿지 결과가 없어 주문 후보를 생성하지 않습니다."
                result.errors.append("bridge_missing")
                return result

            raw_actions = getattr(bridge, "actions", None) or []
            for raw in raw_actions:
                ba = raw if isinstance(raw, BridgeAction) else self._to_bridge_action(raw)
                action_type = str(getattr(ba, "action_type", "") or "").strip().lower()
                symbol = str(getattr(ba, "symbol", "") or "").strip()
                reason = str(getattr(ba, "reason", "") or "")

                if action_type in ("hold", "wait"):
                    result.skipped_orders.append(
                        self._make_record(
                            action_type=action_type,
                            symbol=symbol,
                            status="skipped",
                            reason="non_executable_action",
                            detail_ko="hold/wait 액션은 주문 후보로 제출하지 않습니다.",
                        )
                    )
                    continue

                side = ""
                if action_type == "buy":
                    side = "buy"
                elif action_type in ("sell", "reduce"):
                    side = "sell"
                else:
                    result.skipped_orders.append(
                        self._make_record(
                            action_type=action_type or "unknown",
                            symbol=symbol,
                            status="skipped",
                            reason="unsupported_action_type",
                            detail_ko="지원하지 않는 액션 유형이라 주문 후보에서 제외했습니다.",
                        )
                    )
                    continue

                candidate = OrderRequestCandidate(
                    action_type=action_type,
                    symbol=symbol,
                    order_side=side,
                    amount_krw=self._safe_float(getattr(ba, "amount_krw", 0.0), 0.0),
                    quantity=0.0,
                    reduce_ratio=0.0,
                    dry_run=self.execution_mode != "live",
                    reason=reason,
                    source_module=str(getattr(ba, "source_module", "") or ""),
                    source_provider=str(getattr(ba, "source_provider", "") or ""),
                )
                result.candidates.append(candidate)

            if result.candidates:
                result.summary_ko = "브릿지 결과를 주문 후보로 변환했습니다."
            else:
                result.summary_ko = "실행 가능한 주문 후보가 없습니다."

            result.skipped_count = len(result.skipped_orders)
            return result
        except Exception as exc:
            result.ok = False
            result.errors.append(str(exc)[:200])
            result.summary_ko = "주문 후보 변환 중 오류가 발생해 보수적으로 중단했습니다."
            self._safe_log_error(f"build_candidates failed: {exc}")
            return result

    def validate_candidates(self, result: OrderAdapterResult) -> OrderAdapterResult:
        try:
            valid_candidates: List[OrderRequestCandidate] = []
            for c in list(result.candidates):
                at = (c.action_type or "").strip().lower()
                sym = (c.symbol or "").strip()

                if at in ("hold", "wait"):
                    result.skipped_orders.append(
                        self._make_record(
                            action_type=at,
                            symbol=sym,
                            status="skipped",
                            reason="non_executable_action",
                            detail_ko="hold/wait 액션은 검증 단계에서 제외됩니다.",
                        )
                    )
                    continue

                if not at:
                    result.blocked_orders.append(
                        self._make_record(
                            action_type=at,
                            symbol=sym,
                            status="blocked",
                            reason="missing_action_type",
                            detail_ko="액션 유형이 비어 있어 후보를 차단했습니다.",
                        )
                    )
                    continue

                if not sym:
                    result.blocked_orders.append(
                        self._make_record(
                            action_type=at,
                            symbol=sym,
                            status="blocked",
                            reason="missing_symbol",
                            detail_ko="심볼 정보가 없어 주문 후보를 차단했습니다.",
                        )
                    )
                    continue

                if at == "buy" and self._safe_float(c.amount_krw, 0.0) < self.min_order_krw:
                    result.blocked_orders.append(
                        self._make_record(
                            action_type=at,
                            symbol=sym,
                            status="blocked",
                            reason="below_min_order_krw",
                            detail_ko="최소 주문 금액 미만이라 매수 후보를 차단했습니다.",
                        )
                    )
                    continue

                if at == "reduce" and self.execution_mode == "live" and not self.allow_reduce_live:
                    result.blocked_orders.append(
                        self._make_record(
                            action_type=at,
                            symbol=sym,
                            status="blocked",
                            reason="reduce_not_allowed_in_live",
                            detail_ko="live 모드에서 reduce 실행이 비활성화되어 차단했습니다.",
                        )
                    )
                    continue

                valid_candidates.append(c)

            result.candidates = valid_candidates
            result.blocked_count = len(result.blocked_orders)
            result.skipped_count = len(result.skipped_orders)
            if result.blocked_count > 0:
                result.summary_ko = "주문 후보 검증을 완료했습니다. 일부 후보는 조건 미충족으로 차단되었습니다."
            else:
                result.summary_ko = "주문 후보 검증을 완료했습니다."
            return result
        except Exception as exc:
            result.ok = False
            result.errors.append(str(exc)[:200])
            result.summary_ko = "주문 후보 검증 중 오류가 발생해 보수적으로 중단했습니다."
            self._safe_log_error(f"validate_candidates failed: {exc}")
            return result

    def execute(self, bridge: Optional[BridgeResult]) -> OrderAdapterResult:
        result = self.build_candidates(bridge)
        result = self.validate_candidates(result)
        try:
            valid_candidates = list(result.candidates)

            if self.execution_mode == "disabled":
                for c in valid_candidates:
                    result.skipped_orders.append(
                        self._make_record(
                            action_type=c.action_type,
                            symbol=c.symbol,
                            status="skipped",
                            reason="execution_disabled",
                            detail_ko="현재 실행 모드가 비활성화되어 주문을 제출하지 않았습니다.",
                        )
                    )
                result.candidates = []
                result.summary_ko = "현재 실행 모드가 비활성화되어 주문은 제출되지 않았습니다."

            elif self.execution_mode == "dry_run":
                for c in valid_candidates:
                    result.submitted_orders.append(
                        self._make_record(
                            action_type=c.action_type,
                            symbol=c.symbol,
                            status="dry_run",
                            reason="dry_run_mode",
                            detail_ko="드라이런 모드로 실제 주문은 제출되지 않았습니다.",
                        )
                    )
                result.summary_ko = "드라이런 모드로 주문 후보를 검토했습니다."

            elif self.execution_mode == "live":
                for c in valid_candidates:
                    result.failed_orders.append(
                        self._make_record(
                            action_type=c.action_type,
                            symbol=c.symbol,
                            status="failed",
                            reason="live_not_implemented",
                            detail_ko="live 모드는 아직 실제 주문 연결 전 단계입니다.",
                        )
                    )
                if "live_not_implemented" not in result.warnings:
                    result.warnings.append("live_not_implemented")
                result.summary_ko = (
                    "live 모드가 선택되었지만 실제 주문 연결 전 단계이므로 제출하지 않았습니다."
                )
            else:
                for c in valid_candidates:
                    result.skipped_orders.append(
                        self._make_record(
                            action_type=c.action_type,
                            symbol=c.symbol,
                            status="skipped",
                            reason="invalid_execution_mode",
                            detail_ko="실행 모드가 유효하지 않아 주문 제출을 건너뛰었습니다.",
                        )
                    )
                result.summary_ko = "실행 모드가 유효하지 않아 주문은 제출되지 않았습니다."

            result.submitted_count = len(result.submitted_orders)
            result.blocked_count = len(result.blocked_orders)
            result.failed_count = len(result.failed_orders)
            result.skipped_count = len(result.skipped_orders)
            if not result.summary_ko:
                result.summary_ko = "주문 어댑터 실행을 완료했습니다."
            self._safe_log_info(result.summary_text())
            return result
        except Exception as exc:
            result.ok = False
            result.errors.append(str(exc)[:200])
            result.submitted_count = len(result.submitted_orders)
            result.blocked_count = len(result.blocked_orders)
            result.failed_count = len(result.failed_orders)
            result.skipped_count = len(result.skipped_orders)
            result.summary_ko = "주문 어댑터 실행 중 오류가 발생해 안전하게 중단했습니다."
            self._safe_log_error(f"execute failed: {exc}")
            return result

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

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _is_valid_mode(self, mode: str) -> bool:
        return str(mode or "").strip().lower() in ("disabled", "dry_run", "live")

    def _make_record(
        self,
        action_type: str,
        symbol: str,
        status: str,
        reason: str,
        detail_ko: str,
    ) -> OrderAdapterRecord:
        return OrderAdapterRecord(
            action_type=str(action_type or ""),
            symbol=str(symbol or ""),
            status=str(status or ""),
            reason=str(reason or ""),
            detail_ko=str(detail_ko or ""),
        )

    def _to_bridge_action(self, action: Any) -> BridgeAction:
        try:
            if isinstance(action, BridgeAction):
                return action
            return BridgeAction(
                action_type=str(getattr(action, "action_type", "") if action is not None else ""),
                symbol=str(getattr(action, "symbol", "") if action is not None else ""),
                amount_krw=self._safe_float(getattr(action, "amount_krw", 0.0), 0.0),
                reason=str(getattr(action, "reason", "") if action is not None else ""),
                source_module=str(getattr(action, "source_module", "") if action is not None else ""),
                source_provider=str(
                    getattr(action, "source_provider", "") if action is not None else ""
                ),
            )
        except Exception:
            return BridgeAction()
