#!/usr/bin/env python3
"""Validate canned Phase 4 payloads and public Factory Floor events locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator

FACTORY_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(FACTORY_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORY_MODULE_ROOT))

from x_factory.phase4_payloads import digest, factory_floor_event, make_stage_payload


def expect_blocked(test_id: str, action: Callable[[], None]) -> dict[str, str]:
    try:
        action()
    except (PermissionError, ValueError) as error:
        return {"id": test_id, "status": "PASS", "observed": type(error).__name__}
    raise AssertionError(f"{test_id} did not fail closed")


def canned_artifacts() -> dict[str, dict]:
    intake = {
        "schema_version": "0.1",
        "run_id": "phase4-synthetic-mission-001",
        "agent_or_client": "Desert Home Services",
        "purpose": "Create a friendly fictional local-service concierge for a contained draft.",
        "role_and_behavior": "Warm, concise, and transparent about uncertainty.",
        "must_have_capabilities": ["approved FAQ responses", "request qualification", "structured handoff"],
        "never_do": ["quote final prices", "book appointments", "send email", "write to a CRM"],
        "sources": ["EVD-SYNTHETIC-BUSINESS-RULES", "EVD-SYNTHETIC-CONCIERGE-PATTERN"],
        "raw_owner_text": "Create a contained fictional concierge draft with no external actions.",
        "default_external_actions": "PROHIBITED_UNLESS_EXPLICITLY_APPROVED",
    }
    blueprint = {
        "candidate_id": "CANDIDATE-PHASE4-SYNTHETIC-001",
        "owner_intent": intake["purpose"],
        "required_capabilities": intake["must_have_capabilities"],
        "excluded_actions": intake["never_do"],
        "specification_status": "SPECIFICATION_READY_FOR_BUILD",
        "authority": {"build": False, "installation": False, "deployment": False, "production": False},
    }
    return {
        "intake": intake,
        "catalog": {"components": ["CMP-CONVERSATION-SHELL", "CMP-STRUCTURED-HANDOFF"], "evidence_ids": intake["sources"]},
        "blueprint": blueprint,
        "evidence": {"approved_ids": intake["sources"], "unapproved_items": 0},
        "approval": {"decision": "APPROVE_CONTAINED_BUILD", "scope": "SYNTHETIC_DRAFT_ONLY"},
        "generation": {"contract_id": "PHASE1_3_DETERMINISTIC_GENERATION_V0_3", "network": False},
        "output": {"contract_id": "PHASE1_3_OUTPUT_BUNDLE_V0_3", "required_file_count": 5},
        "acceptance": {"contract_id": "PHASE1_3_ACCEPTANCE_V0_3", "assertion_count": 6},
        "candidate_manifest": {"candidate_id": blueprint["candidate_id"], "file_count": 5, "root_digest": digest(blueprint)},
        "test_evidence": {"status": "PASS", "assertions_passed": 6, "network_attempts": 0, "tool_calls": 0},
        "build_record": {"status": "CONTAINED_BUILD_COMPLETE", "external_actions": 0, "provider_calls": 0},
    }


def run(factory_root: Path) -> tuple[dict, list[dict]]:
    values = canned_artifacts()
    mission_id = values["intake"]["run_id"]
    payloads = [
        make_stage_payload("ATLAS_TRIAGE", mission_id, {"owner_intake": values["intake"]}, "intake.v0.1"),
        make_stage_payload("ARIA_BLUEPRINT", mission_id, {"normalized_intake": values["intake"], "component_catalog": values["catalog"]}, "x_agent_blueprint.v0.1"),
        make_stage_payload("VERA_SPEC_REVIEW", mission_id, {"normalized_intake": values["intake"], "frozen_blueprint": values["blueprint"], "evidence_index": values["evidence"]}, "evaluation_contract.v0.1"),
        make_stage_payload("MASON_PLAN", mission_id, {"approved_blueprint": values["blueprint"], "generation_contract": values["generation"], "output_contract": values["output"], "acceptance_fixture": values["acceptance"], "owner_build_approval": values["approval"]}, "implementation_decision.v0.1"),
        make_stage_payload("VERA_BUILD_REVIEW", mission_id, {"approved_blueprint": values["blueprint"], "candidate_manifest": values["candidate_manifest"], "test_evidence": values["test_evidence"], "build_record": values["build_record"]}, "build_verification_evaluation.v0.2"),
    ]
    if len({digest(payload) for payload in payloads}) != 5:
        raise AssertionError("Stage payload hashes are not distinct")
    if any(payload["authority"][key] for payload in payloads for key in ("file_access", "tools", "installation", "deployment", "production")):
        raise AssertionError("A canned payload expanded authority")

    mason_schema = json.loads((factory_root / "contracts" / "phase4" / "implementation_decision.v0.1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(mason_schema)
    mason_response = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "decision": "IMPLEMENTATION_PLAN_READY",
        "input_hashes": {
            "approved_blueprint": digest(values["blueprint"]),
            "generation_contract": digest(values["generation"]),
            "output_contract": digest(values["output"]),
            "acceptance_fixture": digest(values["acceptance"]),
        },
        "runtime_target": "CONTAINED_SYNTHETIC_X_AGENT_DRAFT",
        "implementation_steps": ["Generate the five contract-declared candidate files", "Run the deterministic acceptance fixture"],
        "expected_outputs": ["Agent instructions", "Agent specification", "Bundle manifest", "Smoke fixture", "Acceptance test"],
        "acceptance_commands": ["Run the declared standard-library acceptance suite"],
        "blockers": [],
        "authority": {"plan_only": True, "file_access": False, "build_authorized": False, "install_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    errors = list(Draft202012Validator(mason_schema).iter_errors(mason_response))
    if errors:
        raise AssertionError("Canned Mason response failed schema")

    events = [
        factory_floor_event(1, "ATLAS_TRIAGE", "COMPLETE", "Atlas normalized the synthetic mission intake.", digest(payloads[0])),
        factory_floor_event(2, "ARIA_BLUEPRINT", "COMPLETE", "Aria froze the smallest complete synthetic blueprint.", digest(payloads[1])),
        factory_floor_event(3, "VERA_SPEC_REVIEW", "COMPLETE", "Vera cleared the specification for the owner build gate.", digest(payloads[2])),
        factory_floor_event(4, "MASON_PLAN", "COMPLETE", "Mason returned a contract-valid contained implementation plan.", digest(payloads[3])),
        factory_floor_event(5, "DETERMINISTIC_BUILD", "COMPLETE", "The local builder produced and tested the contained candidate.", digest(values["candidate_manifest"])),
        factory_floor_event(6, "VERA_BUILD_REVIEW", "COMPLETE", "Vera independently verified the contained draft evidence.", digest(payloads[4])),
        factory_floor_event(7, "DRAFT_READY", "COMPLETE", "The synthetic X-Agent draft is ready for owner review.", digest(values["build_record"])),
    ]
    if any("inline_artifacts" in event or "input_hashes" in event for event in events):
        raise AssertionError("Factory Floor event leaked private payload structure")

    negatives = [
        expect_blocked("NEG-PAYLOAD-001-LOCAL-PATH", lambda: make_stage_payload("ATLAS_TRIAGE", mission_id, {"owner_intake": {"source": "C:\\private\\client.json"}}, "intake.v0.1")),
        expect_blocked("NEG-PAYLOAD-002-CREDENTIAL", lambda: make_stage_payload("ATLAS_TRIAGE", mission_id, {"owner_intake": {"authorization": "Bearer secret-token-value"}}, "intake.v0.1")),
        expect_blocked("NEG-PAYLOAD-003-WRONG-INPUT-SET", lambda: make_stage_payload("ARIA_BLUEPRINT", mission_id, {"normalized_intake": values["intake"]}, "x_agent_blueprint.v0.1")),
        expect_blocked("NEG-EVENT-004-PATH-IN-SUMMARY", lambda: factory_floor_event(8, "MASON_PLAN", "BLOCKED", "Read C:\\private\\source.txt")),
        expect_blocked("NEG-EVENT-005-SECRET-IN-SUMMARY", lambda: factory_floor_event(8, "MASON_PLAN", "BLOCKED", "API key=secret-value")),
    ]
    report = {
        "schema_version": "0.1",
        "status": "PASS",
        "provider_calls": 0,
        "model_calls": 0,
        "payload_count": len(payloads),
        "factory_floor_event_count": len(events),
        "payload_hashes": {payload["stage"]: digest(payload) for payload in payloads},
        "canned_mason_response": {"status": "PASS", "sha256": digest(mason_response)},
        "negative_tests": negatives,
    }
    return report, events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    root = args.factory_root.resolve()
    report_path = args.report.resolve()
    events_path = args.events.resolve()
    for path in (report_path, events_path):
        try:
            path.relative_to(root)
        except ValueError as error:
            raise PermissionError("Phase 4 validation outputs must remain inside the Factory root") from error
    report, events = run(root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    events_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "payloads": report["payload_count"], "events": report["factory_floor_event_count"], "negative_tests": len(report["negative_tests"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
