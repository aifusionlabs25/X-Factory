"""Governance-bound payload adapter for fresh Phase 4 missions."""

from __future__ import annotations

from typing import Any

from .phase4_payloads import EXECUTION_MODE, MODEL_ACTOR, TOOL_POLICY, assert_public_safe, digest
from .phase4_payloads_v0_2 import STAGE_INPUTS_V0_2


MARKER = "X_FACTORY_GOVERNED_RUN_V0_1"
REQUIRED_GOVERNANCE_KEYS = {
    "schema_version",
    "governed_run_marker",
    "mission_id",
    "disclosure_manifest_sha256",
    "owner_approval_sha256",
    "broker_run_record",
    "evidence_approvals",
}


def make_stage_payload_v0_3(
    stage: str,
    mission_id: str,
    artifacts: dict[str, Any],
    output_schema_id: str,
    governance: dict[str, Any],
) -> dict[str, Any]:
    expected = STAGE_INPUTS_V0_2.get(stage)
    if expected is None:
        raise ValueError(f"Unsupported model stage: {stage}")
    if set(artifacts) != set(expected):
        raise PermissionError(f"{stage} requires exactly {list(expected)}")
    if set(governance) != REQUIRED_GOVERNANCE_KEYS:
        raise PermissionError("Governance binding field set mismatch")
    if governance.get("schema_version") != "0.1" or governance.get("governed_run_marker") != MARKER:
        raise PermissionError("Governance marker mismatch")
    if governance.get("mission_id") != mission_id:
        raise PermissionError("Governance mission mismatch")
    broker = governance.get("broker_run_record")
    if not isinstance(broker, dict) or broker.get("governed_run_marker") != MARKER:
        raise PermissionError("Broker run record is absent or invalid")
    if broker.get("mission_id") != mission_id:
        raise PermissionError("Broker run record mission mismatch")
    if broker.get("disclosure_manifest_sha256") != governance["disclosure_manifest_sha256"]:
        raise PermissionError("Broker disclosure binding mismatch")
    if broker.get("owner_approval_sha256") != governance["owner_approval_sha256"]:
        raise PermissionError("Broker owner-approval binding mismatch")
    evidence_approvals = governance.get("evidence_approvals")
    if not isinstance(evidence_approvals, list):
        raise PermissionError("Evidence approvals must be a list")

    assert_public_safe(artifacts, f"{stage}.artifacts")
    assert_public_safe(governance, f"{stage}.governance")
    payload = {
        "schema_version": "0.3",
        "governed_run_marker": MARKER,
        "execution_mode": EXECUTION_MODE,
        "mission_id": mission_id,
        "stage": stage,
        "actor": MODEL_ACTOR[stage],
        "tool_policy": TOOL_POLICY,
        "governance": governance,
        "input_hashes": {name: digest(artifacts[name]) for name in expected},
        "inline_artifacts": {name: artifacts[name] for name in expected},
        "required_output_schema_id": output_schema_id,
        "authority": {
            "contained_draft_only": True,
            "file_access": False,
            "tools": False,
            "installation": False,
            "deployment": False,
            "production": False,
        },
    }
    assert_public_safe(payload)
    return payload
