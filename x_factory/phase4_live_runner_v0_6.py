"""Phase 4.5 runner with explicit bound output schemas in every prompt."""

from __future__ import annotations

import json
from typing import Any

from .phase4_broker import sha256_bytes
from .phase4_live_runner_v0_2 import ORIGINS, SCHEMA_IDS
from .phase4_live_runner_v0_5 import DerivationBoundRunnerV05
from .phase4_payloads import canonical
from .phase4_payloads_v0_2 import make_stage_payload_v0_2


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"


class DerivationBoundRunnerV06(DerivationBoundRunnerV05):
    def derive_payload(self, stage: str) -> dict[str, Any]:
        if self.terminal_failure:
            raise PermissionError(f"Mission is terminal: {self.terminal_failure}")
        artifacts: dict[str, Any] = {}
        for payload_name, registry_name in ORIGINS.get(stage, {}).items():
            if registry_name not in self.artifacts:
                raise PermissionError(f"Approved origin missing: {registry_name}")
            artifacts[payload_name] = self.artifacts[registry_name]
        schema_id = "normalized_intake.v0.1" if stage == "ATLAS_TRIAGE" else SCHEMA_IDS[stage]
        return make_stage_payload_v0_2(stage, self.mission_id, artifacts, schema_id)

    def compose_transmission(self, stage: str) -> tuple[dict[str, Any], str]:
        payload = self.derive_payload(stage)
        schema = json.loads(self._baseline["schema_paths"][stage].read_text(encoding="utf-8"))
        prompt = (
            "Return only one JSON object that validates against the exact JSON Schema below. "
            "Do not wrap it in Markdown. Do not use tools, MCP, memory, delegation, files, or external actions.\n"
            "GOVERNED PAYLOAD:\n" + canonical(payload).decode("utf-8") + "\n"
            "EXACT OUTPUT JSON SCHEMA:\n" + canonical(schema).decode("utf-8")
        )
        return payload, prompt

    def prepare_transmission(self, stage: str) -> dict[str, Any]:
        self._verify_baseline()
        payload, prompt = self.compose_transmission(stage)
        transaction = len(self.ledger.stages) + 1
        record = {
            "transaction": transaction,
            "stage": stage,
            "status": "RESERVED_BEFORE_TRANSMISSION",
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "payload_sha256": sha256_bytes(canonical(payload)),
            "output_sha256": None,
            "raw_evidence": None,
            "physical_requests": None,
            "tool_calls": None,
            "retry": False,
        }
        self.ledger.reserve_before_transmission(stage, record, self.chain)
        return {"transaction": transaction, "stage": stage, "prompt": prompt, "payload": payload}

    def execution_preview(self) -> dict[str, Any]:
        preview = super().execution_preview()
        preview["schema_version"] = "0.6"
        preview["exact_output_schema_embedded_in_prompt"] = True
        preview["atlas_output_schema_id"] = "normalized_intake.v0.1"
        return preview
