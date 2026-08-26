"""Phase 4.6 runner with evidence-bound accepted-stage restoration."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .phase4_broker import sha256_bytes
from .phase4_live_runner_v0_2 import OUTPUT_ALIASES, STAGES, canonical_digest
from .phase4_live_runner_v0_6 import DerivationBoundRunnerV06


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"


class DerivationBoundRunnerV07(DerivationBoundRunnerV06):
    def __post_init__(self) -> None:
        if self.chain:
            raise PermissionError("Caller-supplied transaction chain is prohibited")
        super().__post_init__()
        if self.ledger_path.is_file():
            document = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            entries = document.get("entries")
            if not isinstance(entries, list) or len(entries) != len(self.ledger.stages):
                raise PermissionError("Durable ledger entries cannot be rehydrated")
            if any(entry.get("status") != "ACCEPTED" for entry in entries):
                raise PermissionError("Only a fully accepted ledger prefix may continue")
            if [entry.get("stage") for entry in entries] != list(STAGES[:len(entries)]):
                raise PermissionError("Accepted ledger prefix stage order mismatch")
            if [entry.get("transaction") for entry in entries] != list(range(1, len(entries) + 1)):
                raise PermissionError("Accepted ledger transaction sequence mismatch")
            self.chain = entries

    def restore_accepted_output(self, stage: str, output: dict[str, Any], execution_path: Path) -> None:
        self._verify_baseline()
        index = STAGES.index(stage)
        if index >= len(self.chain) or self.chain[index].get("stage") != stage:
            raise PermissionError("Accepted stage is absent from the durable chain")
        record = self.chain[index]
        if record.get("status") != "ACCEPTED" or record.get("transaction") != index + 1:
            raise PermissionError("Accepted stage ledger record is invalid")
        if canonical_digest(output) != record.get("output_sha256"):
            raise PermissionError("Restored output hash mismatch")
        schema = json.loads(self._baseline["schema_paths"][stage].read_text(encoding="utf-8"))
        if list(Draft202012Validator(schema).iter_errors(output)):
            raise PermissionError("Restored output failed its bound schema")
        output_identifier = output.get("mission_id", output.get("run_id"))
        if output_identifier != self.mission_id:
            raise PermissionError("Restored output mission identifier mismatch")

        evidence_bytes = execution_path.read_bytes()
        raw = record.get("raw_evidence") or {}
        if sha256_bytes(evidence_bytes) != raw.get("execution_sha256"):
            raise PermissionError("Restored execution evidence hash mismatch")
        execution = json.loads(evidence_bytes.decode("utf-8"))
        expected = {
            "mission_id": self.mission_id,
            "stage": stage,
            "transaction": index + 1,
            "exit_code": 0,
            "physical_requests": 1,
            "tool_attempts": 0,
            "oauth_refresh_attempts": 0,
            "auth_write_attempts": 0,
            "codex_cli_import_attempts": 0,
            "extraction_error": None,
        }
        for name, value in expected.items():
            if execution.get(name) != value:
                raise PermissionError(f"Restored execution evidence mismatch: {name}")
        response_bytes = base64.b64decode(execution["response_base64"], validate=True)
        if sha256_bytes(response_bytes) != execution.get("response_sha256"):
            raise PermissionError("Restored machine response hash mismatch")
        if json.loads(response_bytes.decode("utf-8")) != output:
            raise PermissionError("Restored machine response content mismatch")
        if execution.get("stdout_sha256") != raw.get("stdout_sha256") or execution.get("stderr_sha256") != raw.get("stderr_sha256"):
            raise PermissionError("Restored terminal evidence hash mismatch")

        for alias in OUTPUT_ALIASES[stage]:
            if alias in self.artifacts:
                raise PermissionError(f"Restored artifact already exists: {alias}")
            self.artifacts[alias] = output
            self.artifact_origins[alias] = f"RESTORED_VALIDATED_OUTPUT.{stage}"

    def execution_preview(self) -> dict[str, Any]:
        preview = super().execution_preview()
        preview["schema_version"] = "0.7"
        preview["rehydrated_accepted_transactions"] = len(self.chain)
        preview["accepted_output_restoration_requires_execution_evidence"] = True
        return preview
