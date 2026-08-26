"""Create one fresh immutable Ava/Summit build using grounded matcher v0.2."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.chassis_depot_v0_1 import commission_chassis
from x_factory.completion_pipeline_v0_1 import complete_local_draft
from x_factory.mission_control_factory_v0_1 import load_json
from x_factory.runtime_foundry_v0_1 import simulate_turn


SOURCE_MISSION = "draft-ava-home-services-concierge-20260826-001523-0612cc"


def main() -> None:
    brief = load_json(ROOT / "runs" / "interactive" / SOURCE_MISSION / "input/owner-brief.v0.1.json")
    commission = brief["commissioning"]
    record = commission_chassis(
        commission["chassis_id"],
        {
            "purpose": brief["purpose"],
            "x_agent_name": brief["agent_name"],
            "client_name": brief["client_name"],
            "personality": brief["personality"],
            "target_users": "; ".join(brief["target_users"]),
            "client_context": commission.get("client_context", ""),
            "additional_requirements": "",
            "additional_boundaries": "",
            "presence_mode": brief["presence_mode"],
            "knowledge_package_id": commission["knowledge_package"]["package_id"],
            "optional_module_ids": commission["selected_optional_modules"],
            "owner_active_input_ms": 0,
        },
    )
    mission_id = record["mission_id"]
    mission_root = ROOT / "runs" / "interactive" / mission_id
    cases = [
        "What home repair services do you offer?",
        "Can you install a ceiling fan?",
        "Can you repair my kitchen cabinets?",
        "Do you work in Jackson?",
        "Do you install swimming pool pumps?",
        "My AC isn't cooling. I'm in Mesa and it's urgent.",
    ]
    observations = [{key: value for key, value in simulate_turn(mission_root, question).items() if key in {"message", "outcome", "match_reason", "matched_title", "supporting_entry_ids"}} for question in cases]
    expected = ["APPROVED_KNOWLEDGE_MATCH"] * 4 + ["UNKNOWN_ESCALATED"] * 2
    assert [item["outcome"] for item in observations] == expected
    completion = complete_local_draft(mission_id)
    print(json.dumps({"status": "PASS", "mission_id": mission_id, "repo": completion["repo"], "observations": observations}, indent=2))


if __name__ == "__main__":
    main()
