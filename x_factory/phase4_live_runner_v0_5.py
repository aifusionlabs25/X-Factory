"""Phase 4.4 runner: Codex CLI credentials are prohibited and nonparticipating."""

from __future__ import annotations

from typing import Any

from .phase4_live_runner_v0_4 import DerivationBoundRunnerV04


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"


class DerivationBoundRunnerV05(DerivationBoundRunnerV04):
    def __post_init__(self) -> None:
        super().__post_init__()
        expected = {
            "participates": False,
            "read_authorized": False,
            "import_authorized": False,
            "mutation_authorized": False,
        }
        if self.manifest.get("codex_cli_auth_policy") != expected:
            raise PermissionError("Codex CLI authentication policy drift")
        if "codex_cli_auth_json" in self.manifest.get("authentication_baseline", {}):
            raise PermissionError("Nonparticipating Codex CLI auth cannot be baseline-bound")

    def bind_runtime(self, *, authentication_paths: dict[str, Any], **kwargs: Any) -> None:
        if "codex_cli_auth_json" in authentication_paths:
            raise PermissionError("Codex CLI authentication path binding is prohibited")
        super().bind_runtime(authentication_paths=authentication_paths, **kwargs)

    def _accept_bound_execution(self, stage: str, output: dict[str, Any], **kwargs: Any) -> None:
        execution = kwargs.get("execution", {})
        if execution.get("codex_cli_import_attempts") != 0:
            raise PermissionError("Codex CLI credential import was attempted and blocked")
        super()._accept_bound_execution(stage, output, **kwargs)

    def execution_preview(self) -> dict[str, Any]:
        preview = super().execution_preview()
        preview["schema_version"] = "0.5"
        preview["codex_cli_auth_participates"] = False
        preview["codex_cli_import_guard_required"] = True
        return preview
