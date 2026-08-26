"""Provider-free regression for the Summit/Ava owner golden path."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mission_control_server import public_record_view
from x_factory.chassis_depot_v0_1 import commission_chassis
from x_factory.grounded_matcher_v0_1 import MATCH_REASONS
from x_factory.mission_control_factory_v0_1 import load_json
from x_factory.mission_control_presence_v0_1 import preview_descriptor
from x_factory.repo_foundry_v0_1 import create_local_repo
from x_factory.runtime_foundry_v0_1 import simulate_turn


MISSION_ID = "draft-ava-operational-qa-concierge-20260823-180816-611907"
MISSION_ROOT = ROOT / "runs" / "interactive" / MISSION_ID
SOURCE_BUILD_MISSION_ID = "draft-ava-home-services-concierge-20260824-003212-48e6ab"

QUESTIONS = {
    "Do you repair water heaters?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0001"]),
    "Can you fix my AC?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0001"]),
    "What time are you open?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0003"]),
    "Can you guarantee someone tonight?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0004"]),
    "How much will it cost to replace my water heater?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0005"]),
    "What is the price?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0005"]),
    "Do you give estimates?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0005"]),
    "What does a repair run?": ("APPROVED_KNOWLEDGE_MATCH", ["K-0005"]),
    "Do you install swimming pool pumps?": ("UNKNOWN_ESCALATED", []),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def rebuild_exact_summit_commission() -> dict:
    source_root = ROOT / "runs" / "interactive" / SOURCE_BUILD_MISSION_ID
    brief = load_json(source_root / "input/owner-brief.v0.1.json")
    commissioning = brief["commissioning"]
    record = commission_chassis(
        commissioning["chassis_id"],
        {
            "purpose": brief["purpose"],
            "x_agent_name": brief["agent_name"],
            "client_name": brief["client_name"],
            "personality": brief["personality"],
            "target_users": "; ".join(brief["target_users"]),
            "client_context": commissioning.get("client_context", ""),
            "additional_requirements": "",
            "additional_boundaries": "",
            "presence_mode": brief["presence_mode"],
            "knowledge_package_id": commissioning["knowledge_package"]["package_id"],
            "optional_module_ids": commissioning["selected_optional_modules"],
        },
    )
    mission_root = ROOT / "runs" / "interactive" / record["mission_id"]
    certification = load_json(mission_root / "runtime-foundry/local-behavior-certification.v0.2.json")
    schema = load_json(ROOT / "contracts/runtime_behavior_certification.v0.2.schema.json")
    Draft202012Validator(schema).validate(certification)
    require(set(schema["$defs"]["match_reason"]["enum"]) == MATCH_REASONS, "Schema and matcher reason vocabularies drifted")
    first_turn = certification["sessions"]["session_a"]["turns"][0]
    require(first_turn["message"].casefold() != "water heater service".casefold(), "Certification reused an exact approved title")
    require(first_turn["match_reason"] != "EXACT_APPROVED_TITLE", "Certification did not exercise natural-language retrieval")
    require(certification["assertions"][0]["assertion"] == "NATURAL_LANGUAGE_KNOWN_QUESTION_GROUNDED_WITH_SOURCE", "Certification assertion did not prove natural-language retrieval")
    invalid_reason = deepcopy(certification)
    invalid_reason["sessions"]["session_a"]["turns"][0]["match_reason"] = "ARBITRARY_FREE_FORM_REASON"
    try:
        Draft202012Validator(schema).validate(invalid_reason)
    except ValidationError:
        pass
    else:
        raise AssertionError("Canonical schema accepted an arbitrary match reason")
    extra_property = deepcopy(certification)
    extra_property["sessions"]["session_a"]["turns"][0]["unexpected"] = True
    try:
        Draft202012Validator(schema).validate(extra_property)
    except ValidationError:
        pass
    else:
        raise AssertionError("Canonical turn schema no longer enforces additionalProperties:false")
    porter = create_local_repo(record["mission_id"])
    require(porter["verification"]["status"] == "PASS", "Porter-generated app tests failed")
    return {
        "mission_id": record["mission_id"],
        "schema_version": certification["schema_version"],
        "paraphrase_turn": first_turn,
        "porter_repo_id": porter["repo_id"],
        "porter_status": porter["verification"]["status"],
    }


def main() -> None:
    require(MISSION_ROOT.is_dir(), f"Missing immutable Summit mission: {MISSION_ROOT}")
    results = {}
    for question, expected in QUESTIONS.items():
        result = simulate_turn(MISSION_ROOT, question)
        require(result["outcome"] == expected[0], f"Wrong outcome for {question}: {result}")
        require(result["supporting_entry_ids"] == expected[1], f"Wrong support for {question}: {result}")
        require(result["provider_calls"] == 0 and result["live_runtime"] is False, "Preview crossed the local-only boundary")
        results[question] = {
            "outcome": result["outcome"],
            "supporting_entry_ids": result["supporting_entry_ids"],
            "match_reason": result["match_reason"],
            "response": result["response"],
        }

    record = load_json(MISSION_ROOT / "mission-record.json")
    public = public_record_view(record)
    presence = preview_descriptor(MISSION_ID)
    require(public["agent"]["display_name"] == "Ava — Home Services Concierge", "Owner API leaked the internal chassis title")
    require(presence["agent"]["display_name"] == "Ava — Home Services Concierge", "Presence preview leaked the internal chassis title")

    html = (ROOT / "apps/mission-control/index.html").read_text(encoding="utf-8")
    js = (ROOT / "apps/mission-control/app.js").read_text(encoding="utf-8")
    require('id="commission-client-name" required placeholder="For example: Summit Home Services"' in html, "Client field must not have a stale value")
    require('id="quick-knowledge-text" rows="6" placeholder=' in html, "Knowledge field must be empty by default")
    require('id="preview-handoff-location"' in html and 'id="preview-handoff-urgency"' in html, "Visible qualification handoff is incomplete")
    require(html.count('class="handoff-primary') == 5 and html.count('class="handoff-wide') == 2 and html.count('class="handoff-half') == 2, "Visible handoff row layout drifted")
    require('Service question outside approved knowledge' in js, "Visible review flag must be humanized")
    require('$("#commission-client-name").value = "";' in js, "Chassis changes must clear stale client identity")
    require('$("#quick-knowledge-text").value = "";' in js, "Chassis changes must clear stale knowledge")
    require("FINISH PREVIEW CHECKS FIRST" in js and "!previewReady()" in js, "Porter must remain gated on preview acceptance")
    require("ANSWERED FROM APPROVED KNOWLEDGE" in js and "NEEDS HUMAN REVIEW" in js, "Preview outcomes must use human-facing labels")

    rebuilt = rebuild_exact_summit_commission() if "--rebuild-exact" in sys.argv else None
    print(json.dumps({
        "status": "PASS",
        "mission_id": MISSION_ID,
        "identity": public["agent"]["display_name"],
        "semantic_results": results,
        "preview_checks": 7,
        "provider_calls": 0,
        "source_mission_repo_created": False,
        "exact_rebuild": rebuilt,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
