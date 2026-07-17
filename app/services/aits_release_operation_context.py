from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Iterator
from uuid import uuid4


SUPPORTED_OPERATIONS = {
    "essential_backup", "learning_backup", "full_backup", "migration",
    "support_bundle", "restore", "update", "rollback",
}


@dataclass(frozen=True)
class AITSReleaseOperationContext:
    operation_id: str
    operation_type: str
    requested_at: str
    requested_by: str
    explicit_user_approval: bool
    runtime_off_confirmed: bool
    source_root: Path
    target_root: Path
    staging_root: Path
    isolated_acceptance_mode: bool
    destructive_operation: bool
    source_preservation_required: bool
    rollback_required: bool
    execution_authorized: bool
    authorization_reason: str
    blocker: str = ""

    @classmethod
    def create(
        cls,
        *,
        operation_type: str,
        source_root: Path | str,
        target_root: Path | str,
        staging_root: Path | str,
        explicit_user_approval: bool,
        runtime_off_confirmed: bool,
        execution_authorized: bool,
        isolated_acceptance_mode: bool = False,
        destructive_operation: bool = False,
        source_preservation_required: bool = True,
        rollback_required: bool = True,
        requested_by: str = "user",
        authorization_reason: str = "explicit_user_request",
    ) -> "AITSReleaseOperationContext":
        return cls(
            operation_id=f"{operation_type}-{uuid4().hex}",
            operation_type=operation_type,
            requested_at=datetime.now(timezone.utc).isoformat(),
            requested_by=requested_by,
            explicit_user_approval=bool(explicit_user_approval),
            runtime_off_confirmed=bool(runtime_off_confirmed),
            source_root=Path(source_root).resolve(),
            target_root=Path(target_root).resolve(),
            staging_root=Path(staging_root).resolve(),
            isolated_acceptance_mode=bool(isolated_acceptance_mode),
            destructive_operation=bool(destructive_operation),
            source_preservation_required=bool(source_preservation_required),
            rollback_required=bool(rollback_required),
            execution_authorized=bool(execution_authorized),
            authorization_reason=authorization_reason,
        )

    def validate(self) -> dict[str, object]:
        blockers: list[str] = []
        if self.operation_type not in SUPPORTED_OPERATIONS:
            blockers.append("unsupported_operation_type")
        if not self.explicit_user_approval:
            blockers.append("explicit_user_approval_required")
        if not self.runtime_off_confirmed:
            blockers.append("runtime_must_be_off")
        if not self.execution_authorized:
            blockers.append("execution_not_authorized")
        if not self.source_root.exists():
            blockers.append("source_root_missing")
        if self.destructive_operation and not self.rollback_required:
            blockers.append("destructive_operation_requires_rollback")
        if self.source_root == self.target_root:
            blockers.append("source_target_must_differ")
        return {
            "schema": "aits_release_operation_context.v1",
            **{key: str(value) if isinstance(value, Path) else value for key, value in asdict(self).items()},
            "valid": not blockers,
            "blockers": blockers,
            "blocker": blockers[0] if blockers else "",
        }

    def require_authorized(self, expected_type: str) -> None:
        result = self.validate()
        blockers = list(result["blockers"])
        if self.operation_type != expected_type:
            blockers.insert(0, "operation_type_mismatch")
        if blockers:
            raise PermissionError(str(blockers[0]))

    @contextmanager
    def operation_lock(self) -> Iterator[Path]:
        lock_root = self.staging_root.parent / ".aits_release_operation_locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        lock_path = lock_root / f"{self.operation_type}.lock"
        descriptor: int | None = None
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, self.operation_id.encode("utf-8"))
            os.fsync(descriptor)
            yield lock_path
        except FileExistsError as exc:
            raise RuntimeError("duplicate_operation_in_progress") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock_path.unlink(missing_ok=True)


def observe_only_context(operation_type: str, source_root: Path | str, target_root: Path | str) -> AITSReleaseOperationContext:
    target = Path(target_root)
    return AITSReleaseOperationContext.create(
        operation_type=operation_type,
        source_root=source_root,
        target_root=target,
        staging_root=target.parent / ".observe-only-staging",
        explicit_user_approval=False,
        runtime_off_confirmed=True,
        execution_authorized=False,
        authorization_reason="observe_only",
    )
