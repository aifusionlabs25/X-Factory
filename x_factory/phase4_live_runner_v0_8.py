"""Phase 4.8 runner with exact broker-governance payload binding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .phase4_broker import sha256_bytes
from .phase4_live_runner_v0_2 import ORIGINS
from .phase4_live_runner_v0_7 import DerivationBoundRunnerV07
from .phase4_payloads_v0_3 import make_stage_payload_v0_3


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"
SCHEMA_IDS_V0_8 = {
    "ATLAS_TRIAGE": "normalized_intake.v0.2",
    "ARIA_BLUEPRINT": "x_agent_blueprint.v0.2",
    "VERA_SPEC_REVIEW": "evaluation_contract.v0.1",
    "MASON_PLAN": "implementation_decision.v0.1",
    "VERA_BUILD_REVIEW": "build_review.v0.1",
}


class GovernanceBoundRunnerV08(DerivationBoundRunnerV07):
    governance_binding_path: Path | None = None
    governance_binding: dict[str, Any] | None = None

    def bind_governance(self, path: Path) -> None:
        self._verify_baseline()
        path = path.resolve(strict=True)
        expected = self.manifest["starting_input_hashes"].get("governance_binding")
        if expected is None or sha256_bytes(path.read_bytes()) != expected:
            raise PermissionError("Governance binding drift")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("mission_id") != self.mission_id:
            raise PermissionError("Governance binding mission mismatch")
        self.governance_binding_path = path
        self.governance_binding = value

    def _verify_baseline(self) -> None:
        super()._verify_baseline()
        if self.governance_binding_path is not None:
            expected = self.manifest["starting_input_hashes"].get("governance_binding")
            if sha256_bytes(self.governance_binding_path.read_bytes()) != expected:
                raise PermissionError("Governance binding drift")

    def derive_payload(self, stage: str) -> dict[str, Any]:
        if self.terminal_failure:
            raise PermissionError(f"Mission is terminal: {self.terminal_failure}")
        if self.governance_binding is None:
            raise PermissionError("Governance binding is required")
        artifacts: dict[str, Any] = {}
        for payload_name, registry_name in ORIGINS.get(stage, {}).items():
            if registry_name not in self.artifacts:
                raise PermissionError(f"Approved origin missing: {registry_name}")
            artifacts[payload_name] = self.artifacts[registry_name]
        return make_stage_payload_v0_3(
            stage,
            self.mission_id,
            artifacts,
            SCHEMA_IDS_V0_8[stage],
            self.governance_binding,
        )

    def execution_preview(self) -> dict[str, Any]:
        preview = super().execution_preview()
        preview["schema_version"] = "0.8"
        preview["governed_run_marker"] = "X_FACTORY_GOVERNED_RUN_V0_1"
        preview["broker_governance_binding_required"] = True
        return preview
