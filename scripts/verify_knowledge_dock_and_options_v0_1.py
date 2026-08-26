#!/usr/bin/env python3
"""Verify the v1.1 knowledge and Runtime Foundry pipeline locally."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_factory.knowledge_loading_v0_1 as knowledge  # noqa: E402
import x_factory.knowledge_compiler_v0_1 as compiler  # noqa: E402
import x_factory.mission_control_factory_v0_1 as factory  # noqa: E402
import x_factory.repo_foundry_v0_1 as repo_foundry  # noqa: E402
import x_factory.runtime_foundry_v0_1 as runtime_foundry  # noqa: E402
from x_factory.chassis_depot_v0_1 import (  # noqa: E402
    ChassisDepotError,
    commission_chassis,
    list_module_options,
)


SANDBOX = (ROOT / "verification/knowledge-pipeline-v1.1-sandbox").resolve()


def expect_failure(action, expected: str) -> None:
    try:
        action()
    except (knowledge.KnowledgeLoadingError, ChassisDepotError) as error:
        if expected.casefold() not in str(error).casefold():
            raise AssertionError(f"Expected {expected!r} in {error!r}") from error
    else:
        raise AssertionError(f"Expected controlled failure containing {expected!r}")


def main() -> int:
    verification_root = (ROOT / "verification").resolve()
    SANDBOX.relative_to(verification_root)
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)
    knowledge.KNOWLEDGE_ROOT = SANDBOX / "knowledge-packages"
    factory.INTERACTIVE_ROOT = SANDBOX / "runs"
    repo_foundry.INTERACTIVE_ROOT = factory.INTERACTIVE_ROOT
    repo_foundry.LOCAL_REPO_ROOT = SANDBOX / "repos"

    package = knowledge.ingest_knowledge_package(
        {
            "label": "XYZ Data approved materials",
            "files": [
                {"name": "company-overview.md", "content": "# XYZ Data\nApproved capability: local QA request review.\n\nQ: What is supported?\nA: Local QA request review only.\n"},
                {"name": "faq.json", "content": json.dumps({"question": "What is supported?", "answer": "Local QA request review."})},
            ],
        }
    )
    assert package["effective_status"] == "INGESTED_PENDING_OWNER_APPROVAL"
    assert package["authority"]["runtime_truth"] is False
    assert all((knowledge.KNOWLEDGE_ROOT / package["package_id"] / "files" / item["stored_name"]).is_file() for item in package["files"])

    approved = knowledge.approve_knowledge_package(package["package_id"])
    assert approved["effective_status"] == "OWNER_APPROVED_FOR_COMMISSIONING"
    assert approved["approval"]["authority"]["runtime_compilation"] is False

    compilation = compiler.compile_package(package["package_id"])
    assert compilation["status"] == "COMPILED_PENDING_OWNER_REVIEW"
    assert compilation["authority"]["semantic_inference"] is False
    assert compilation["conflicts"]
    all_approved = [{"entry_id": item["entry_id"], "decision": "APPROVE"} for item in compilation["entries"]]
    expect_failure(
        lambda: compiler.review_compilation(package["package_id"], {"compilation_id": compilation["compilation_id"], "decisions": all_approved}),
        "at most one",
    )
    rejected_conflict_entry = compilation["conflicts"][0]["entry_ids"][1]
    resolved_decisions = [
        {"entry_id": item["entry_id"], "decision": "REJECT" if item["entry_id"] == rejected_conflict_entry else "APPROVE"}
        for item in compilation["entries"]
    ]
    reviewed = compiler.review_compilation(package["package_id"], {"compilation_id": compilation["compilation_id"], "decisions": resolved_decisions})
    assert reviewed["latest_review"]["status"] == "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD"
    assert reviewed["latest_review"]["approved_count"] == len(compilation["entries"]) - 1

    options = list_module_options("operational-qa-concierge")
    option_ids = {item["module_id"] for item in options["optional"]}
    assert {"CMP-CLIENT-KNOWLEDGE-PACK", "CMP-APPOINTMENT-REQUEST-PACKET", "CMP-LEAD-QUALIFICATION-SCORECARD"}.issubset(option_ids)
    assert options["locked"][0]["module_id"] == "CMP-EXTERNAL-ACTION-RUNTIME"

    first = commission_chassis(
        "operational-qa-concierge",
        {
            "purpose": "Answer approved XYZ Data questions, qualify inquiries, and prepare a structured staff handoff.",
            "x_agent_name": "Ava",
            "client_name": "XYZ Data Company",
            "personality": "Clear, capable, and reassuring",
            "target_users": "XYZ Data customers",
            "client_context": "A fictional client used only for local verification.",
            "additional_requirements": "",
            "additional_boundaries": "",
            "presence_mode": "TEXT_ONLY",
            "knowledge_package_id": package["package_id"],
            "optional_module_ids": ["CMP-APPOINTMENT-REQUEST-PACKET"],
        },
    )
    first_root = factory.INTERACTIVE_ROOT / first["mission_id"]
    first_record = json.loads((first_root / "mission-record.json").read_text(encoding="utf-8"))
    first_brief = json.loads((first_root / "input/owner-brief.v0.1.json").read_text(encoding="utf-8"))
    reference = json.loads((first_root / "input/knowledge-package-reference.v0.1.json").read_text(encoding="utf-8"))
    first_module_ids = {item["component_id"] for item in first_record["modules"]}
    assert reference["package_id"] == package["package_id"]
    assert reference["attachment_status"] == "OWNER_REVIEWED_FOR_INSTANCE_KNOWLEDGE_BUILD_NOT_RUNTIME"
    assert reference["runtime_truth"] is False
    assert reference["compilation_sha256"] == compilation["compilation_sha256"]
    assert reference["review_sha256"] == reviewed["latest_review"]["review_sha256"]
    assert first_brief["commissioning"]["client_name"] == "XYZ Data Company"
    assert {"CMP-CLIENT-KNOWLEDGE-PACK", "CMP-APPOINTMENT-REQUEST-PACKET"}.issubset(first_module_ids)
    assert first_record["knowledge"]["status"] == "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED"
    assert first_record["knowledge"]["runtime_candidate"] is True
    assert first_record["knowledge"]["runtime_installed"] is False
    assert first_record["knowledge"]["entry_count"] == reviewed["latest_review"]["approved_count"]
    instance_paths = {
        "bundle": first_root / "instance/knowledge/approved-knowledge.v0.1.json",
        "kb": first_root / "instance/knowledge/KB.md",
        "prompt": first_root / "instance/system-prompt/SYSTEM_PROMPT.md",
        "traceability": first_root / "instance/traceability/knowledge-traceability.v0.1.json",
        "tests": first_root / "instance/tests/knowledge-tests.v0.1.json",
        "report": first_root / "instance/instance-knowledge-build-report.v0.1.json",
    }
    assert all(path.is_file() for path in instance_paths.values())
    bundle = json.loads(instance_paths["bundle"].read_text(encoding="utf-8"))
    test_pack = json.loads(instance_paths["tests"].read_text(encoding="utf-8"))
    report_record = json.loads(instance_paths["report"].read_text(encoding="utf-8"))
    system_prompt = instance_paths["prompt"].read_text(encoding="utf-8")
    assert bundle["identity"] == {"agent_name": "Ava", "role_title": "X-Agent", "client_name": "XYZ Data Company"}
    assert bundle["source_binding"]["review_sha256"] == reviewed["latest_review"]["review_sha256"]
    assert test_pack["status"] == "PASS"
    assert report_record["status"] == "INSTANCE_KNOWLEDGE_BUILD_PASS"
    assert "You are Ava" in system_prompt and "XYZ Data Company" in system_prompt
    assert all(f"[{entry['entry_id']}]" in system_prompt for entry in bundle["entries"])

    runtime_paths = {
        "plan": first_root / "runtime-foundry/runtime-plan.v0.1.json",
        "profile": first_root / "runtime-foundry/profile-blueprint.v0.1.json",
        "prompt": first_root / "runtime-foundry/canary/exact-prompt.txt",
        "payload": first_root / "runtime-foundry/canary/exact-payload.v0.1.json",
        "activation": first_root / "runtime-foundry/canary/inactive-activation-packet.v0.1.json",
        "contract": first_root / "runtime-foundry/instance-runtime-contract.v0.1.json",
        "behavior": first_root / "runtime-foundry/behavior-certification-plan.v0.1.json",
        "local_behavior": first_root / "runtime-foundry/local-behavior-certification.v0.2.json",
    }
    assert all(path.is_file() for path in runtime_paths.values())
    runtime_plan = runtime_foundry.runtime_status(first_root)
    assert runtime_plan["status"] == "LOCAL_RUNTIME_PACKAGE_READY_CANARY_INACTIVE"
    assert runtime_plan["route"] == {"harness": "Hermes Desktop", "provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low"}
    assert runtime_plan["profile_blueprint"]["status"] == "NOT_INSTALLED"
    assert runtime_plan["profile_blueprint"]["toolsets"] == []
    assert runtime_plan["profile_blueprint"]["memory_enabled"] is False
    assert runtime_plan["canary"]["status"] == "INACTIVE"
    assert runtime_plan["runtime_contract_status"] == "INSTANCE_RUNTIME_CONTRACT_LOCKED"
    assert len(runtime_plan["runtime_contract_sha256"]) == 64
    assert runtime_plan["behavior_status"] == "INACTIVE_RUNTIME_BEHAVIOR_PROOF_REQUIRED"
    assert runtime_plan["local_behavior_status"] == "LOCAL_BEHAVIOR_HARNESS_PASS"
    local_behavior = json.loads(runtime_paths["local_behavior"].read_text(encoding="utf-8"))
    assert local_behavior["schema_version"] == "0.2"
    assert local_behavior["sessions"]["session_a"]["turns"][0]["match_reason"] != "EXACT_APPROVED_TITLE"
    assert local_behavior["assertions"][0]["assertion"] == "NATURAL_LANGUAGE_KNOWN_QUESTION_GROUNDED_WITH_SOURCE"
    assert local_behavior["sessions"]["session_a"]["turns"][1]["match_reason"] == "NO_APPROVED_MATCH"
    assert local_behavior["sessions"]["session_a"]["turns"][2]["match_reason"] == "SESSION_CORRECTION_CAPTURED"
    assert local_behavior["summary"] == {"passed": 7, "failed": 0, "live_runtime_verified": False, "next_gate": "CONTAINED_HERMES_MULTI_TURN_PROOF"}
    assert local_behavior["sessions"]["session_a"]["handoff"]["session_corrections"]
    assert local_behavior["sessions"]["session_b_fresh"]["handoff"]["session_corrections"] == []
    assert local_behavior["sessions"]["session_a"]["session_id"] != local_behavior["sessions"]["session_b_fresh"]["session_id"]
    assert local_behavior["sessions"]["session_a"]["runtime_identity"] == local_behavior["sessions"]["session_b_fresh"]["runtime_identity"]
    assert local_behavior["sessions"]["session_b_fresh"]["previous_session_transcript_loaded"] is False
    assert local_behavior["sessions"]["session_b_fresh"]["memory_artifacts_loaded"] == []
    assert local_behavior["vera"]["verdict"] == "LOCAL_BEHAVIOR_CERTIFIED"
    assert local_behavior["vera"]["fresh_session_state_leakage"] is False
    assert all(item["status"] == "PASS" for item in local_behavior["assertions"])
    assert all(value is False for value in runtime_plan["authority"].values())
    assert first_record["runtime_foundry"]["provider_calls"] == 0
    local_answer = runtime_foundry.simulate_turn(first_root, runtime_plan["canary"]["question"])
    assert local_answer["outcome"] == "APPROVED_KNOWLEDGE_MATCH"
    assert local_answer["supporting_entry_ids"] == [runtime_plan["canary"]["expected_entry_id"]]
    unknown_answer = runtime_foundry.simulate_turn(first_root, "Can you launch a rocket for me?")
    assert unknown_answer["outcome"] == "UNKNOWN_ESCALATED"
    assert unknown_answer["provider_calls"] == 0

    local_repo = repo_foundry.create_local_repo(first["mission_id"])
    local_repo_root = repo_foundry.LOCAL_REPO_ROOT / local_repo["repo_id"]
    repo_agent = json.loads((local_repo_root / "web/agent.json").read_text(encoding="utf-8"))
    assert local_repo["verification"]["status"] == "PASS"
    assert local_repo["status"] == "LOCAL_REPO_READY"
    assert local_repo["independent_review"]["verdict"] == "READY_FOR_PORTER_PACKAGING"
    assert (local_repo_root / "factory-record/independent-local-review.json").is_file()
    assert local_repo["repo_tier"] == "STAGING"
    assert local_repo["authority"]["runtime_approved"] is False
    assert (local_repo_root / "knowledge/KB.md").is_file()
    assert (local_repo_root / "config/SYSTEM_PROMPT.md").is_file()
    assert (local_repo_root / "runtime/runtime-plan.json").is_file()
    assert (local_repo_root / "runtime/profile-blueprint.json").is_file()
    assert (local_repo_root / "runtime/canary/inactive-activation-packet.json").is_file()
    assert (local_repo_root / "runtime/instance-runtime-contract.json").is_file()
    assert (local_repo_root / "runtime/behavior-certification-plan.json").is_file()
    assert (local_repo_root / "runtime/local-behavior-certification.json").is_file()
    assert repo_agent["knowledge_status"] == "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED"
    assert repo_agent["display_name"] == "Ava"
    assert "Operational QA Concierge" not in repo_agent["display_name"]
    assert len(repo_agent["knowledge_entries"]) == len(bundle["entries"])

    second = commission_chassis(
        "operational-qa-concierge",
        {
            "purpose": "Answer approved Northstar questions and prepare requests for staff review.",
            "x_agent_name": "Leo",
            "client_name": "Northstar Field Services",
            "personality": "Direct and professional",
            "target_users": "Northstar customers",
            "client_context": "A separate fictional client.",
            "additional_requirements": "",
            "additional_boundaries": "",
            "presence_mode": "TEXT_ONLY",
            "knowledge_package_id": None,
            "optional_module_ids": [],
        },
    )
    second_root = factory.INTERACTIVE_ROOT / second["mission_id"]
    second_record = json.loads((second_root / "mission-record.json").read_text(encoding="utf-8"))
    assert not (second_root / "input/knowledge-package-reference.v0.1.json").exists()
    assert not (second_root / "instance").exists()
    assert not (second_root / "runtime-foundry").exists()
    assert second_record["knowledge"]["package"] is None
    assert second_record["runtime_foundry"]["status"] == "KNOWLEDGE_CORE_REQUIRED"
    assert second_record["runtime_foundry"]["live_runtime"] is False
    assert "XYZ Data" not in json.dumps(second_record)

    expect_failure(
        lambda: knowledge.ingest_knowledge_package({"label": "Unsafe", "files": [{"name": "secrets.txt", "content": "api_key=sk-not-a-real-but-long-secret-12345"}]}),
        "credential",
    )
    expect_failure(
        lambda: commission_chassis(
            "operational-qa-concierge",
            {
                "purpose": "Test that unavailable external actions remain safely blocked.",
                "x_agent_name": "Blocked",
                "client_name": "Blocked Client",
                "personality": "Plain",
                "target_users": "Test users",
                "client_context": "",
                "additional_requirements": "",
                "additional_boundaries": "",
                "presence_mode": "TEXT_ONLY",
                "knowledge_package_id": None,
                "optional_module_ids": ["CMP-EXTERNAL-ACTION-RUNTIME"],
            },
        ),
        "not available",
    )
    expect_failure(
        lambda: commission_chassis(
            "operational-qa-concierge",
            {
                "purpose": "Test that client knowledge cannot be used before owner approval.",
                "x_agent_name": "Blocked",
                "client_name": "Blocked Client",
                "personality": "Plain",
                "target_users": "Test users",
                "client_context": "",
                "additional_requirements": "",
                "additional_boundaries": "",
                "presence_mode": "TEXT_ONLY",
                "knowledge_package_id": None,
                "optional_module_ids": ["CMP-CLIENT-KNOWLEDGE-PACK"],
            },
        ),
        "requires an owner-approved package",
    )

    report = {
        "schema_version": "0.1",
        "status": "PASS",
        "factory_version": "1.3",
        "knowledge_package": {
            "package_id": package["package_id"],
            "manifest_sha256": package["manifest_sha256"],
            "approval_sha256": approved["approval"]["approval_sha256"],
            "compilation_sha256": compilation["compilation_sha256"],
            "review_sha256": reviewed["latest_review"]["review_sha256"],
            "files": len(package["files"]),
            "runtime_truth": False,
        },
        "commissioned_candidate": {
            "mission_id": first["mission_id"],
            "agent": first["agent"]["display_name"],
            "client": first["agent"]["client_name"],
            "unit_tests": first["build"]["unit_tests"],
        },
        "checks": {
            "immutable_file_hashes": True,
            "owner_approval_hash_bound": True,
            "source_linked_compilation": True,
            "conflict_resolution_required": True,
            "owner_review_hash_bound": True,
            "knowledge_requires_approval": True,
            "runtime_truth_remains_false": True,
            "instance_knowledge_bundle_hash_bound": True,
            "personalized_system_prompt_created": True,
            "source_traceability_preserved": True,
            "instance_knowledge_tests": test_pack["status"],
            "runtime_installation_remains_false": first_record["knowledge"]["runtime_installed"] is False,
            "runtime_plan_hash_bound": True,
            "hermes_profile_blueprint_not_installed": runtime_plan["profile_blueprint"]["status"] == "NOT_INSTALLED",
            "runtime_canary_inactive": runtime_plan["canary"]["status"] == "INACTIVE",
            "provider_free_multi_turn_behavior": runtime_plan["local_behavior_status"],
            "fresh_session_non_persistence": local_behavior["assertions"][6]["status"],
            "local_boundary_test_supported_answer": local_answer["outcome"],
            "local_boundary_test_unknown_escalation": unknown_answer["outcome"],
            "porter_repo_inherits_reviewed_knowledge": local_repo["verification"]["status"] == "PASS",
            "porter_repo_inherits_runtime_package": (local_repo_root / "runtime/runtime-plan.json").is_file(),
            "allowlisted_options_only": True,
            "external_action_module_prohibited": True,
            "client_isolation": True,
            "candidate_tests": first["build"]["unit_tests"],
        },
        "provider_calls": 0,
        "external_repo_writes": 0,
        "production": False,
    }
    report_path = SANDBOX / "verification-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
