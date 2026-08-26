"""Fail-closed control plane for a derivation-bound Phase 4 live mission.

This module deliberately contains no provider invocation.  It prepares and
validates the exact material a future approved transport may transmit, while
keeping live execution disabled until a separately reviewed activation change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .phase4_broker import require_digest, require_within, sha256_bytes
from .phase4_payloads import canonical, make_stage_payload


LIVE_EXECUTION_STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"
STAGE_ORDER = (
    "ATLAS_TRIAGE",
    "ARIA_BLUEPRINT",
    "VERA_SPEC_REVIEW",
    "MASON_PLAN",
    "VERA_BUILD_REVIEW",
)
REQUIRED_VERDICTS = {
    "VERA_SPEC_REVIEW": "SPECIFICATION_READY_FOR_BUILD",
    "MASON_PLAN": "IMPLEMENTATION_PLAN_READY",
    "VERA_BUILD_REVIEW": "CONTAINED_DRAFT_READY",
}


def file_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical(value))


def validate_json(value: Any, schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
    if errors:
        message = "; ".join(error.message for error in errors[:5])
        raise PermissionError(f"{label} failed schema validation: {message}")


@dataclass
class TransactionLedger:
    maximum: int = 5
    stages: list[str] = field(default_factory=list)

    def reserve(self, stage: str) -> int:
        if len(self.stages) >= self.maximum:
            raise PermissionError("Maximum model transaction count exceeded")
        if stage in self.stages:
            raise PermissionError(f"Retry prohibited for {stage}")
        expected = STAGE_ORDER[len(self.stages)] if len(self.stages) < len(STAGE_ORDER) else None
        if stage != expected:
            raise PermissionError(f"Stage order violation: expected {expected}, received {stage}")
        self.stages.append(stage)
        return len(self.stages)


@dataclass
class DerivationBoundRunner:
    factory_root: Path
    mission_id: str
    manifest: dict[str, Any]
    policy: dict[str, Any]
    manifest_schema: dict[str, Any]
    ledger: TransactionLedger = field(default_factory=TransactionLedger)
    chain: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.factory_root = self.factory_root.resolve()
        validate_json(self.manifest, self.manifest_schema, "live mission manifest")
        if self.manifest["mission_id"] != self.mission_id:
            raise PermissionError("Mission ID does not match the bound manifest")
        if self.policy.get("status") != "DRAFT_NOT_ACTIVE":
            raise PermissionError("Unexpected derivation policy status")
        runtime = self.policy.get("runtime", {})
        expected = ("openai-codex", "gpt-5.6-luna", "low", 5, 1, False, 0, False)
        actual = (
            runtime.get("provider"), runtime.get("model"), runtime.get("reasoning"),
            runtime.get("maximum_model_transactions"), runtime.get("maximum_transactions_per_stage"),
            runtime.get("retry_authorized"), runtime.get("tool_calls_per_stage"),
            runtime.get("oauth_refresh_authorized"),
        )
        if actual != expected:
            raise PermissionError("Runtime policy drift")

    def verify_authentication_baseline(self, paths: dict[str, Path]) -> None:
        expected = self.manifest["authentication_baseline"]
        if set(paths) != set(expected):
            raise PermissionError("Authentication baseline path set mismatch")
        for name, path in paths.items():
            if not path.is_file() or file_digest(path) != expected[name]:
                raise PermissionError(f"Authentication drift: {name}")

    def verify_bound_files(self, paths: dict[str, Path], manifest_section: str) -> None:
        expected = self.manifest[manifest_section]
        if set(paths) != set(expected):
            raise PermissionError(f"{manifest_section} path set mismatch")
        for name, path in paths.items():
            if not path.is_file() or file_digest(path) != expected[name]:
                raise PermissionError(f"Bound file drift: {manifest_section}.{name}")

    def contained_path(self, requested: Path) -> Path:
        mission_root = self.factory_root / "runs" / "contained" / self.mission_id
        return require_within(requested, mission_root, "live mission write")

    def derive_stage_payload(
        self,
        stage: str,
        artifacts: dict[str, Any],
        output_schema_id: str,
        bound_artifact_hashes: dict[str, str],
    ) -> dict[str, Any]:
        payload = make_stage_payload(stage, self.mission_id, artifacts, output_schema_id)
        if set(bound_artifact_hashes) != set(payload["input_hashes"]):
            raise PermissionError("Dynamic payload contamination: artifact set changed")
        for name, expected_hash in bound_artifact_hashes.items():
            require_digest(expected_hash, f"{stage}.{name}")
            if payload["input_hashes"][name] != expected_hash:
                raise PermissionError(f"Dynamic payload contamination: {name} hash changed")
        return payload

    def record_transaction(
        self,
        stage: str,
        prompt: str,
        payload: dict[str, Any],
        output: dict[str, Any],
        output_schema: dict[str, Any],
        *,
        tool_calls: int = 0,
    ) -> dict[str, Any]:
        if tool_calls != 0:
            raise PermissionError("Tool use is prohibited")
        validate_json(output, output_schema, f"{stage} output")
        required_verdict = REQUIRED_VERDICTS.get(stage)
        if required_verdict and output.get("verdict", output.get("decision")) != required_verdict:
            raise PermissionError(f"{stage} required verdict is absent")
        transaction_number = self.ledger.reserve(stage)
        record = {
            "transaction": transaction_number,
            "stage": stage,
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "payload_sha256": canonical_digest(payload),
            "output_sha256": canonical_digest(output),
            "tool_calls": 0,
            "retry": False,
        }
        self.chain.append(record)
        return record

    def execution_preview(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "status": LIVE_EXECUTION_STATUS,
            "mission_id": self.mission_id,
            "manifest_sha256": canonical_digest(self.manifest),
            "policy_sha256": canonical_digest(self.policy),
            "provider": self.manifest["provider"],
            "model": self.manifest["model"],
            "reasoning": self.manifest["reasoning"],
            "maximum_model_transactions": self.ledger.maximum,
            "provider_transport_present": False,
            "transactions_recorded": len(self.chain),
            "hash_chain": self.chain,
        }

    def execute(self) -> None:
        raise PermissionError(
            "Live provider execution is not implemented or activated; an approved manifest and separate activation change are required"
        )
