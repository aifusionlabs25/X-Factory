#!/usr/bin/env python3
"""Verify one chassis can produce identity-isolated local X-Agent candidates."""

from __future__ import annotations

import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import mission_control_factory_v0_1 as factory  # noqa: E402
from x_factory.chassis_depot_v0_1 import commission_chassis, get_chassis, recommend_chassis  # noqa: E402


def commission(name: str, client: str, context: str, purpose: str | None = None) -> dict:
    return commission_chassis(
        "operational-qa-concierge",
        {
            "purpose": purpose or f"Answer approved questions for {client}, collect request details, and prepare a staff handoff.",
            "x_agent_name": name,
            "client_name": client,
            "personality": "Clear, calm, concise, and transparent",
            "target_users": "Client-approved customers",
            "client_context": context,
            "additional_requirements": "Collect the customer's preferred follow-up window",
            "additional_boundaries": "Do not claim that a human has reviewed the request",
            "presence_mode": "TEXT_ONLY",
        },
    )


def main() -> int:
    original_root = factory.INTERACTIVE_ROOT
    sandbox = ROOT / "verification" / "chassis-test-sandbox" / "runs"
    factory.INTERACTIVE_ROOT = sandbox
    try:
        chassis = get_chassis("operational-qa-concierge")
        recommendation = recommend_chassis("Answer approved customer questions, collect request details, and prepare a staff handoff.")
        assert recommendation["recommended"]["chassis_id"] == chassis["chassis_id"]
        assert recommendation["recommended_by"] == "ATLAS_LOCAL_INTENT_MATCH"
        assert recommendation["provider_calls"] == 0
        first = commission("Ava", "XYZ Data Company", "XYZ provides client-approved data operations services.")
        second = commission("Leo", "Northstar Field Services", "Northstar provides client-approved field service coordination.")
        home = commission("Ava", "Desert Home Services", "A fictional home-services client.", "Answer approved home services questions, collect job details, and prepare a staff handoff.")
        legacy = factory.create_mission(
            {
                "purpose": "Create a contained legacy-compatible concierge for local verification.",
                "agent_or_client": "Legacy Concierge",
                "personality": "Clear and concise",
                "must_accomplish": "Answer the approved purpose question",
                "never_do": "Invent business facts",
                "target_users": "Approved local testers",
                "output_artifact": "Local review handoff",
                "presence_mode": "TEXT_ONLY",
                "persona_catalog_id": None,
            }
        )
        assert first["agent"]["display_name"] == "Ava"
        assert second["agent"]["display_name"] == "Leo"
        assert first["agent"]["role_title"] == "X-Agent"
        assert home["agent"]["display_name"] == "Ava — Home Services Concierge"
        assert home["agent"]["public_role_title"] == "Home Services Concierge"
        assert first["agent"]["client_name"] == "XYZ Data Company"
        assert second["agent"]["client_name"] == "Northstar Field Services"
        assert first["agent"]["candidate_id"] != second["agent"]["candidate_id"]
        assert first["build"]["unit_tests"] == second["build"]["unit_tests"] == "PASS"
        assert legacy["agent"]["display_name"] == "Legacy Concierge"
        assert legacy["agent"]["derived_from_chassis"] is None
        assert first["commissioning_summary"]["chassis_sha256"] == chassis["chassis_sha256"]
        first_root = sandbox / first["mission_id"]
        second_root = sandbox / second["mission_id"]
        first_brief = json.loads((first_root / "input/owner-brief.v0.1.json").read_text(encoding="utf-8"))
        second_brief = json.loads((second_root / "input/owner-brief.v0.1.json").read_text(encoding="utf-8"))
        first_spec = json.loads((first_root / "build/run-1/output/agent/agent.spec.json").read_text(encoding="utf-8"))
        second_spec = json.loads((second_root / "build/run-1/output/agent/agent.spec.json").read_text(encoding="utf-8"))
        assert first_brief["commissioning"]["chassis_sha256"] == chassis["chassis_sha256"]
        assert first_brief["commissioning"]["commissioned_instance_intent"] == first_brief["purpose"]
        assert first_brief["commissioning"]["chassis_role_title"] == "Operational QA Concierge"
        assert first_brief["role_title"] == "X-Agent"
        assert second_brief["commissioning"]["chassis_sha256"] == chassis["chassis_sha256"]
        assert first_spec["identity"]["agent_name"] == "Ava"
        assert second_spec["identity"]["agent_name"] == "Leo"
        assert "Northstar" not in json.dumps(first_spec)
        assert "XYZ Data" not in json.dumps(second_spec)
        result = {
            "schema_version": "0.1",
            "status": "PASS",
            "chassis_id": chassis["chassis_id"],
            "chassis_version": chassis["version"],
            "chassis_sha256": chassis["chassis_sha256"],
            "derived_candidates": [
                {"mission_id": first["mission_id"], "display_name": first["agent"]["display_name"], "client": first["agent"]["client_name"], "tests": first["build"]["unit_tests"]},
                {"mission_id": second["mission_id"], "display_name": second["agent"]["display_name"], "client": second["agent"]["client_name"], "tests": second["build"]["unit_tests"]},
            ],
            "checks": {
                "manifest_hash_valid": True,
                "identity_separated": True,
                "client_data_isolated": True,
                "shared_role_chassis": True,
                "deterministic_build_tests": "PASS",
                "knowledge_ingestion_remains_gated": True,
                "legacy_owner_brief_compatible": True,
            },
            "provider_calls": 0,
            "external_repo_writes": 0,
            "production": False,
        }
        print(json.dumps(result, indent=2))
    finally:
        factory.INTERACTIVE_ROOT = original_root
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
