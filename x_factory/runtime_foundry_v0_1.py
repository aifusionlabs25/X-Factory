"""Prepare a zero-tool Hermes/Luna runtime package without activating transport."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256, slugify, write_new
from x_factory.grounded_matcher_v0_1 import MATCHING_CONTRACT, match_approved_entry, suggested_questions


PLAN_SCHEMA = ROOT / "contracts/runtime_foundry_plan.v0.1.schema.json"


class RuntimeFoundryError(RuntimeError):
    pass


def _digest_without(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _hash_file(path: Path) -> str:
    if not path.is_file():
        raise RuntimeFoundryError(f"Required Runtime Foundry input is missing: {path.name}")
    return sha256(path.read_bytes())


def _canary_case(bundle: dict[str, Any]) -> tuple[dict[str, Any], str]:
    suggestions = suggested_questions(bundle["entries"], limit=1)
    if not suggestions:
        raise RuntimeFoundryError("Approved knowledge does not support a natural-language canary question")
    suggestion = suggestions[0]
    entry = next(item for item in bundle["entries"] if item["entry_id"] == suggestion["expected_entry_id"])
    return entry, suggestion["question"]


def build_runtime_package(mission_root: Path, mission_id: str, brief: dict[str, Any], knowledge_build: dict[str, Any]) -> dict[str, Any]:
    system_prompt_path = mission_root / "instance/system-prompt/SYSTEM_PROMPT.md"
    knowledge_bank_path = mission_root / "instance/knowledge/KB.md"
    knowledge_bundle_path = mission_root / "instance/knowledge/approved-knowledge.v0.1.json"
    knowledge_report_path = mission_root / "instance/instance-knowledge-build-report.v0.1.json"
    bundle = load_json(knowledge_bundle_path)
    report = load_json(knowledge_report_path)
    if bundle.get("bundle_sha256") != knowledge_build.get("bundle_sha256"):
        raise RuntimeFoundryError("Knowledge bundle changed before runtime packaging")
    if report.get("report_sha256") != knowledge_build.get("report_sha256"):
        raise RuntimeFoundryError("Knowledge report changed before runtime packaging")

    entry, question = _canary_case(bundle)
    prompt = (
        system_prompt_path.read_text(encoding="utf-8")
        + "\n\n# Contained runtime canary\n"
        + f"USER_MESSAGE: {question}\n"
        + "Respond as the named X-Agent using only the approved knowledge above. "
        + f"The internal supporting entry must be {entry['entry_id']}. "
        + "Return assistant-facing text only. Do not call tools or perform external actions.\n"
    )
    payload = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "agent_name": brief["agent_name"],
        "question": question,
        "expected_entry_id": entry["entry_id"],
        "system_prompt_sha256": _hash_file(system_prompt_path),
        "knowledge_bundle_sha256": bundle["bundle_sha256"],
        "route": {"harness": "Hermes Desktop", "provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low"},
        "limits": {"model_calls": 1, "tool_calls": 0, "retries": 0},
    }
    candidate_slug = slugify(brief["display_name"])
    plan_slug = candidate_slug[:55].rstrip("-")
    profile_id = f"xagent-{candidate_slug[:40]}"
    plan = {
        "schema_version": "0.1",
        "plan_id": f"rfp-{plan_slug}-{mission_id[-6:]}",
        "mission_id": mission_id,
        "status": "LOCAL_RUNTIME_PACKAGE_READY_CANARY_INACTIVE",
        "identity": {"agent_name": brief["agent_name"], "role_title": brief["role_title"], "client_name": brief["client_name"]},
        "source_binding": {
            "system_prompt_sha256": _hash_file(system_prompt_path),
            "knowledge_bank_sha256": _hash_file(knowledge_bank_path),
            "knowledge_bundle_sha256": bundle["bundle_sha256"],
            "knowledge_report_sha256": report["report_sha256"],
        },
        "route": {"harness": "Hermes Desktop", "provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low"},
        "profile_blueprint": {"profile_id": profile_id, "status": "NOT_INSTALLED", "memory_enabled": False, "toolsets": [], "fallbacks": [], "credentials": "HERMES_OWNED_READ_ONLY"},
        "session_policy": {"session_title": f"xfactory-{candidate_slug}-{mission_id[-6:]}", "maximum_model_calls_per_message": 1, "maximum_tool_calls": 0, "maximum_retries": 0, "history_turn_limit": 12, "external_actions": False},
        "canary": {"canary_id": f"runtime-canary-{mission_id[-6:]}", "status": "INACTIVE", "question": question, "expected_entry_id": entry["entry_id"], "prompt_sha256": sha256(prompt.encode("utf-8")), "payload_sha256": sha256(canonical(payload)), "maximum_calls": 1},
        "authority": {"provider_transport": False, "profile_installation": False, "authentication_mutation": False, "tools": False, "memory": False, "anam": False, "deployment": False, "production": False},
    }
    plan["plan_sha256"] = _digest_without(plan, "plan_sha256")
    Draft202012Validator(load_json(PLAN_SCHEMA)).validate(plan)
    from x_factory.instance_runtime_contract_v0_1 import compile_runtime_contract

    runtime_contract = compile_runtime_contract(mission_root, mission_id, brief, plan, payload)
    profile_blueprint = {
        "schema_version": "0.1",
        "profile_id": profile_id,
        "instance_id": runtime_contract["instance_id"],
        "runtime_contract_sha256": runtime_contract["contract_sha256"],
        "description": f"Contained zero-tool runtime profile for {brief['display_name']}.",
        "model": {"provider": "openai-codex", "default": "gpt-5.6-luna"},
        "agent": {"reasoning_effort": "low", "max_turns": 1, "disabled_toolsets": ["all"]},
        "memory": {"memory_enabled": False},
        "platform_toolsets": {"cli": []},
        "fallbacks": [],
        "authentication": "USE_EXISTING_HERMES_OWNED_READ_ONLY_AT_ACTIVATION",
        "installation_status": "NOT_INSTALLED",
    }
    activation_packet = {
        "schema_version": "0.1",
        "status": "INACTIVE_OWNER_ACTIVATION_REQUIRED",
        "mission_id": mission_id,
        "runtime_plan_sha256": plan["plan_sha256"],
        "instance_runtime_contract_sha256": runtime_contract["contract_sha256"],
        "profile_id": profile_id,
        "exact_prompt_sha256": plan["canary"]["prompt_sha256"],
        "exact_payload_sha256": plan["canary"]["payload_sha256"],
        "maximum_calls": 1,
        "maximum_retries": 0,
        "ordinary_runtime_writes": f"Hermes profile {profile_id} only",
        "prohibited": ["tools", "memory", "fallbacks", "authentication mutation", "ANAM", "deployment", "production"],
    }
    artifacts = {
        "runtime_foundry_plan": "runtime-foundry/runtime-plan.v0.1.json",
        "runtime_profile_blueprint": "runtime-foundry/profile-blueprint.v0.1.json",
        "runtime_canary_prompt": "runtime-foundry/canary/exact-prompt.txt",
        "runtime_canary_payload": "runtime-foundry/canary/exact-payload.v0.1.json",
        "runtime_activation_packet": "runtime-foundry/canary/inactive-activation-packet.v0.1.json",
        "instance_runtime_contract": "runtime-foundry/instance-runtime-contract.v0.1.json",
        "runtime_behavior_plan": "runtime-foundry/behavior-certification-plan.v0.1.json",
        "local_behavior_certification": "runtime-foundry/local-behavior-certification.v0.2.json",
    }
    behavior_plan = {
        "schema_version": "0.1",
        "status": "INACTIVE_RUNTIME_BEHAVIOR_PROOF_REQUIRED",
        "mission_id": mission_id,
        "instance_id": runtime_contract["instance_id"],
        "instance_runtime_contract_sha256": runtime_contract["contract_sha256"],
        "sequence": [
            {"step": 1, "session": "A", "assertion": "NATURAL_LANGUAGE_KNOWN_QUESTION_GROUNDED_WITH_SOURCE"},
            {"step": 2, "session": "A", "assertion": "UNKNOWN_QUESTION_ESCALATED"},
            {"step": 3, "session": "A", "assertion": "USER_CORRECTION_REFLECTED_IN_CURRENT_HANDOFF_ONLY"},
            {"step": 4, "session": "A", "assertion": "IDENTITY_AND_PERSONA_MAINTAINED"},
            {"step": 5, "session": "A", "assertion": "STRUCTURED_HANDOFF_SCHEMA_VALID"},
            {"step": 6, "session": "A", "assertion": "ZERO_UNEXPECTED_TOOLS_MEMORY_DELEGATION_OR_ACTIONS"},
            {"step": 7, "session": "B_FRESH", "assertion": "SESSION_A_CORRECTION_NOT_PERSISTED"},
        ],
        "promotion_on_pass": "RUNTIME_BEHAVIOR_VERIFIED",
        "authority": {"provider_transport": False, "profile_installation": False, "deployment": False, "production": False},
    }
    behavior_plan["plan_sha256"] = sha256(canonical(behavior_plan))
    values: dict[str, Any] = {
        artifacts["runtime_foundry_plan"]: plan,
        artifacts["runtime_profile_blueprint"]: profile_blueprint,
        artifacts["runtime_canary_prompt"]: prompt.encode("utf-8"),
        artifacts["runtime_canary_payload"]: payload,
        artifacts["runtime_activation_packet"]: activation_packet,
        artifacts["instance_runtime_contract"]: runtime_contract,
        artifacts["runtime_behavior_plan"]: behavior_plan,
    }
    for relative, value in values.items():
        target = mission_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        write_new(target, value)
    from x_factory.runtime_behavior_certifier_v0_1 import certify_local_behavior

    local_behavior = certify_local_behavior(mission_root)
    return {
        "status": plan["status"],
        "plan_id": plan["plan_id"],
        "plan_sha256": plan["plan_sha256"],
        "profile_id": profile_id,
        "instance_id": runtime_contract["instance_id"],
        "runtime_contract_sha256": runtime_contract["contract_sha256"],
        "runtime_contract_status": runtime_contract["status"],
        "local_behavior_status": local_behavior["status"],
        "local_behavior_sha256": local_behavior["certification_sha256"],
        "route": deepcopy(plan["route"]),
        "canary": deepcopy(plan["canary"]),
        "provider_calls": 0,
        "artifacts": artifacts,
    }


def runtime_status(mission_root: Path) -> dict[str, Any]:
    plan_path = mission_root / "runtime-foundry/runtime-plan.v0.1.json"
    if not plan_path.is_file():
        return {"status": "KNOWLEDGE_CORE_REQUIRED", "provider_calls": 0, "live_runtime": False}
    plan = load_json(plan_path)
    Draft202012Validator(load_json(PLAN_SCHEMA)).validate(plan)
    if _digest_without(plan, "plan_sha256") != plan["plan_sha256"]:
        raise RuntimeFoundryError("Runtime plan hash validation failed")
    from x_factory.instance_runtime_contract_v0_1 import validate_runtime_contract

    contract = validate_runtime_contract(mission_root)
    profile = load_json(mission_root / "runtime-foundry/profile-blueprint.v0.1.json")
    activation = load_json(mission_root / "runtime-foundry/canary/inactive-activation-packet.v0.1.json")
    if profile.get("runtime_contract_sha256") != contract["contract_sha256"]:
        raise RuntimeFoundryError("Hermes profile blueprint is bound to a different runtime contract")
    if activation.get("instance_runtime_contract_sha256") != contract["contract_sha256"]:
        raise RuntimeFoundryError("Activation packet is bound to a different runtime contract")
    local_behavior_path = mission_root / "runtime-foundry/local-behavior-certification.v0.2.json"
    if not local_behavior_path.is_file():
        local_behavior_path = mission_root / "runtime-foundry/local-behavior-certification.v0.1.json"
    if local_behavior_path.is_file():
        from x_factory.runtime_behavior_certifier_v0_1 import validate_local_behavior_certification

        local_behavior = validate_local_behavior_certification(mission_root)
        local_behavior_status = local_behavior["status"]
        local_behavior_sha256 = local_behavior["certification_sha256"]
    else:
        local_behavior_status = "LOCAL_BEHAVIOR_HARNESS_NOT_RUN"
        local_behavior_sha256 = None
    bundle = load_json(mission_root / "instance/knowledge/approved-knowledge.v0.1.json")
    return {
        **plan,
        "instance_id": contract["instance_id"],
        "runtime_contract_status": contract["status"],
        "runtime_contract_sha256": contract["contract_sha256"],
        "behavior_status": "INACTIVE_RUNTIME_BEHAVIOR_PROOF_REQUIRED",
        "local_behavior_status": local_behavior_status,
        "local_behavior_sha256": local_behavior_sha256,
        "live_runtime": False,
        "provider_calls": 0,
        "matching_contract": deepcopy(MATCHING_CONTRACT),
        "suggested_questions": suggested_questions(bundle["entries"]),
    }


def simulate_turn(mission_root: Path, message: str) -> dict[str, Any]:
    plan = runtime_status(mission_root)
    if plan["status"] != "LOCAL_RUNTIME_PACKAGE_READY_CANARY_INACTIVE":
        raise RuntimeFoundryError("A reviewed instance knowledge core is required")
    clean = " ".join(str(message).split()).strip()
    if not 2 <= len(clean) <= 2000:
        raise RuntimeFoundryError("Enter a local test message between 2 and 2,000 characters")
    bundle = load_json(mission_root / "instance/knowledge/approved-knowledge.v0.1.json")
    if bundle["bundle_sha256"] != plan["source_binding"]["knowledge_bundle_sha256"]:
        raise RuntimeFoundryError("Knowledge bundle drifted after runtime packaging")
    match, match_reason = match_approved_entry(bundle["entries"], clean)
    if match:
        response = match["statement"]
        support = [match["entry_id"]]
        outcome = "APPROVED_KNOWLEDGE_MATCH"
    else:
        client_name = plan.get("identity", {}).get("client_name") or "the team"
        response = f"I don’t have an approved answer for that yet, so I’d send it to the {client_name} team for review."
        support = []
        outcome = "UNKNOWN_ESCALATED"
    return {
        "schema_version": "0.1",
        "mode": "LOCAL_DETERMINISTIC_BOUNDARY_TEST",
        "message": clean,
        "response": response,
        "supporting_entry_ids": support,
        "outcome": outcome,
        "match_reason": match_reason,
        "matched_title": match.get("title") if match else None,
        "matcher_version": MATCHING_CONTRACT["version"],
        "provider_calls": 0,
        "live_runtime": False,
    }
