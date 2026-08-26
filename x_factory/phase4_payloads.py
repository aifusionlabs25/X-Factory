"""Model-safe Phase 4 payload envelopes and public Factory Floor events."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


MARKER = "X_FACTORY_CONTAINED_MISSION_V0_1"
EXECUTION_MODE = "BROKERED_NO_TOOLS"
TOOL_POLICY = "ZERO_TOOLS_NO_MCP_NO_MEMORY_NO_DELEGATION"
STAGE_INPUTS = {
    "ATLAS_TRIAGE": {"owner_intake"},
    "ARIA_BLUEPRINT": {"normalized_intake", "component_catalog"},
    "VERA_SPEC_REVIEW": {"normalized_intake", "frozen_blueprint", "evidence_index"},
    "MASON_PLAN": {"approved_blueprint", "generation_contract", "output_contract", "acceptance_fixture", "owner_build_approval"},
    "VERA_BUILD_REVIEW": {"approved_blueprint", "candidate_manifest", "test_evidence", "build_record"},
}
MODEL_ACTOR = {
    "ATLAS_TRIAGE": "ATLAS",
    "ARIA_BLUEPRINT": "ARIA",
    "VERA_SPEC_REVIEW": "VERA",
    "MASON_PLAN": "MASON",
    "VERA_BUILD_REVIEW": "VERA",
}
PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?:^|[\s\"'])\.\.[\\/]|(?:^|[\s\"'])/[A-Za-z0-9_.-])")
SECRET_PATTERN = re.compile(r"(?i)(?:bearer\s+[a-z0-9._-]{8,}|\bsk-[a-z0-9_-]{8,}|\beyJ[a-z0-9._-]{8,}|(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\s*[:=]\s*[^\s]+)")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def assert_public_safe(value: Any, label: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert_public_safe(key, f"{label}.key")
            assert_public_safe(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_public_safe(item, f"{label}[{index}]")
    elif isinstance(value, str):
        if PATH_PATTERN.search(value):
            raise PermissionError(f"{label} contains a local path")
        if SECRET_PATTERN.search(value):
            raise PermissionError(f"{label} contains credential-shaped material")


def make_stage_payload(
    stage: str,
    mission_id: str,
    artifacts: dict[str, Any],
    output_schema_id: str,
) -> dict[str, Any]:
    if stage not in STAGE_INPUTS:
        raise ValueError(f"Unsupported model stage: {stage}")
    if set(artifacts) != STAGE_INPUTS[stage]:
        raise ValueError(f"{stage} requires exactly {sorted(STAGE_INPUTS[stage])}")
    assert_public_safe(artifacts, f"{stage}.artifacts")
    artifact_hashes = {name: digest(value) for name, value in sorted(artifacts.items())}
    payload = {
        "schema_version": "0.1",
        "governed_run_marker": MARKER,
        "execution_mode": EXECUTION_MODE,
        "mission_id": mission_id,
        "stage": stage,
        "actor": MODEL_ACTOR[stage],
        "tool_policy": TOOL_POLICY,
        "input_hashes": artifact_hashes,
        "inline_artifacts": artifacts,
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


def factory_floor_event(
    event_number: int,
    stage: str,
    status: str,
    summary: str,
    artifact_hash: str | None = None,
) -> dict[str, Any]:
    if stage not in MODEL_ACTOR and stage not in {"DETERMINISTIC_BUILD", "DRAFT_READY"}:
        raise ValueError("Unknown Factory Floor stage")
    event = {
        "schema_version": "0.1",
        "event_number": event_number,
        "stage": stage,
        "actor": MODEL_ACTOR.get(stage, "FACTORY"),
        "status": status,
        "summary": summary,
        "artifact_hash": artifact_hash,
        "visibility": "OWNER_SAFE_SUMMARY_ONLY",
    }
    assert_public_safe(event, "factory_floor_event")
    return event

