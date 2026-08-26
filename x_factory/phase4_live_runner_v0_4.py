"""Phase 4.3 runner: acceptance is restricted to the bound executor."""

from __future__ import annotations

from typing import Any

from .phase4_live_runner_v0_3 import DerivationBoundRunnerV03


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"
_BOUND_EXECUTOR_CAPABILITY = object()


class DerivationBoundRunnerV04(DerivationBoundRunnerV03):
    def accept_captured_response(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Direct response acceptance is prohibited")

    def _accept_bound_execution(
        self,
        stage: str,
        output: dict[str, Any],
        *,
        execution: dict[str, Any],
        execution_sha256: str,
        capability: object,
    ) -> None:
        if capability is not _BOUND_EXECUTOR_CAPABILITY:
            raise PermissionError("Bound executor capability is required")
        if execution.get("mission_id") != self.mission_id:
            raise PermissionError("Execution evidence mission mismatch")
        if not self.chain or execution.get("transaction") != self.chain[-1].get("transaction"):
            raise PermissionError("Execution evidence transaction mismatch")
        if execution.get("stage") != stage:
            raise PermissionError("Execution evidence stage mismatch")
        if execution.get("prompt_sha256") != self.chain[-1].get("prompt_sha256"):
            raise PermissionError("Execution evidence prompt mismatch")
        if execution.get("payload_sha256") != self.chain[-1].get("payload_sha256"):
            raise PermissionError("Execution evidence payload mismatch")
        if execution.get("exit_code") != 0:
            raise PermissionError("Bridge execution did not exit successfully")
        if execution.get("oauth_refresh_attempts") != 0:
            raise PermissionError("OAuth refresh was attempted and blocked")
        if execution.get("auth_write_attempts") != 0:
            raise PermissionError("Authentication write was attempted and blocked")
        super().accept_captured_response(
            stage,
            output,
            raw_evidence={
                "stdout_sha256": execution["stdout_sha256"],
                "stderr_sha256": execution["stderr_sha256"],
                "execution_sha256": execution_sha256,
            },
            physical_requests=execution["physical_requests"],
            tool_calls=execution["tool_attempts"],
        )

    def execution_preview(self) -> dict[str, Any]:
        preview = super().execution_preview()
        preview["schema_version"] = "0.4"
        preview["direct_acceptance_present"] = False
        preview["transaction_bound_executor_required"] = True
        return preview
