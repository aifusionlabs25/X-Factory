"""Runner-owned payload adapter for Phase 4.1 derivation-bound missions."""

from __future__ import annotations

from typing import Any

from .phase4_payloads import (
    EXECUTION_MODE,
    MARKER,
    MODEL_ACTOR,
    TOOL_POLICY,
    assert_public_safe,
    digest,
)


STAGE_INPUTS_V0_2 = {
    "ATLAS_TRIAGE": ("owner_intake",),
    "ARIA_BLUEPRINT": ("normalized_intake", "component_catalog"),
    "VERA_SPEC_REVIEW": ("normalized_intake", "frozen_blueprint", "evidence_index"),
    "MASON_PLAN": (
        "approved_blueprint", "generation_contract", "output_contract",
        "acceptance_fixture", "owner_build_approval",
    ),
    "VERA_BUILD_REVIEW": (
        "approved_blueprint", "mason_plan", "candidate_manifest",
        "test_evidence", "build_record",
    ),
}


def make_stage_payload_v0_2(
    stage: str,
    mission_id: str,
    artifacts: dict[str, Any],
    output_schema_id: str,
) -> dict[str, Any]:
    expected = STAGE_INPUTS_V0_2.get(stage)
    if expected is None:
        raise ValueError(f"Unsupported model stage: {stage}")
    if set(artifacts) != set(expected):
        raise PermissionError(f"{stage} requires exactly {list(expected)}")
    assert_public_safe(artifacts, f"{stage}.artifacts")
    payload = {
        "schema_version": "0.2",
        "governed_run_marker": MARKER,
        "execution_mode": EXECUTION_MODE,
        "mission_id": mission_id,
        "stage": stage,
        "actor": MODEL_ACTOR[stage],
        "tool_policy": TOOL_POLICY,
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

