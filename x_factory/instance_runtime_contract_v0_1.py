"""Compile and validate the immutable named-instance runtime identity gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256, slugify


SCHEMA = ROOT / "contracts/instance_runtime_contract.v0.1.schema.json"


class InstanceRuntimeContractError(RuntimeError):
    pass


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise InstanceRuntimeContractError(f"Required lock input is missing: {path.name}")
    return sha256(path.read_bytes())


def _digest_without_contract(value: dict[str, Any]) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != "contract_sha256"}))


def compile_runtime_contract(
    mission_root: Path,
    mission_id: str,
    brief: dict[str, Any],
    runtime_plan: dict[str, Any],
    activation_payload: dict[str, Any],
) -> dict[str, Any]:
    commissioning = load_json(mission_root / "input/commissioning-record.v0.1.json")
    blueprint_path = mission_root / "artifacts/aria-blueprint.v0.2.json"
    blueprint = load_json(blueprint_path)
    final_vera_path = mission_root / "certification/vera-final.v0.1.json"
    final_vera = load_json(final_vera_path)
    knowledge_ref = load_json(mission_root / "input/knowledge-package-reference.v0.1.json")
    knowledge_bundle = load_json(mission_root / "instance/knowledge/approved-knowledge.v0.1.json")
    persona_path = mission_root / "experience/persona-binding.v0.1.json"
    persona = load_json(persona_path)

    expected_identity = (brief["agent_name"], brief["client_name"], commissioning["chassis_id"])
    actual_identity = (blueprint["identity"]["agent_name"], blueprint["identity"]["client"], commissioning["chassis_id"])
    if expected_identity != actual_identity:
        raise InstanceRuntimeContractError("Commissioning, brief, and blueprint identity do not agree")
    if commissioning.get("x_agent_name") != brief["agent_name"] or commissioning.get("client_name") != brief["client_name"]:
        raise InstanceRuntimeContractError("Commissioning identity drifted before runtime lock")
    if final_vera.get("verdict") != "LOCAL_CANDIDATE_CERTIFIED":
        raise InstanceRuntimeContractError("Final Vera certification is not accepted")
    if knowledge_ref.get("status") != "OWNER_APPROVED_FOR_COMMISSIONING":
        raise InstanceRuntimeContractError("Knowledge package is not owner approved")
    if knowledge_ref.get("manifest_sha256") != commissioning["knowledge_package"].get("manifest_sha256"):
        raise InstanceRuntimeContractError("Knowledge package identity changed after commissioning")
    presence_modes = {"EXISTING_ANAM", "CREATE_NEW_ANAM", "STOCK_IMAGE", "TEXT_ONLY"}
    if persona.get("presence_mode") not in presence_modes:
        raise InstanceRuntimeContractError("Presence binding does not resolve to one approved mode")

    agent_slug = slugify(brief["agent_name"])
    client_id = slugify(brief["client_name"])
    instance_id = f"xi-{slugify(brief['display_name'])[:62].rstrip('-')}-{mission_id[-6:]}"
    profile_name = runtime_plan["profile_blueprint"]["profile_id"]
    target_profile_path = f"profiles/{profile_name}"
    baseline = {"target_profile_path": target_profile_path, "expected_state": "ABSENT"}
    rollback = {"target_profile_path": target_profile_path, "rollback_action": "REMOVE_NEW_PROFILE_ONLY", "baseline_sha256": sha256(canonical(baseline))}
    expected_first_run = {
        "agent_name": brief["agent_name"],
        "question": runtime_plan["canary"]["question"],
        "expected_entry_id": runtime_plan["canary"]["expected_entry_id"],
        "tools": 0,
        "unknown_behavior": "ESCALATE",
    }
    contract = {
        "schema_version": "0.1",
        "status": "INSTANCE_RUNTIME_CONTRACT_LOCKED",
        "mission_id": mission_id,
        "instance_id": instance_id,
        "revision": 1,
        "identity": {
            "agent_name": brief["agent_name"],
            "agent_slug": agent_slug,
            "client_id": client_id,
            "client_name": brief["client_name"],
            "chassis_id": commissioning["chassis_id"],
            "chassis_version": commissioning["chassis_version"],
            "chassis_sha256": commissioning["chassis_sha256"],
        },
        "content": {
            "knowledge_package_sha256": knowledge_ref["manifest_sha256"],
            "knowledge_review_sha256": knowledge_ref["review_sha256"],
            "system_prompt_sha256": runtime_plan["source_binding"]["system_prompt_sha256"],
            "module_set_sha256": sha256(canonical(blueprint["components"]["selected"])),
            "presence_binding_sha256": _file_sha256(persona_path),
        },
        "runtime": {
            "profile_name": profile_name,
            "provider": runtime_plan["route"]["provider"],
            "model": runtime_plan["route"]["model"],
            "reasoning": runtime_plan["route"]["reasoning"],
            "memory": "disabled",
            "tools": "disabled",
            "delegation": "disabled",
            "retries": "disabled",
            "external_actions": "disabled",
        },
        "behavior": {
            "knowledge_gated": True,
            "unknown_behavior": "ESCALATE",
            "activation_contract_sha256": sha256(canonical(activation_payload)),
            "expected_first_run_sha256": sha256(canonical(expected_first_run)),
        },
        "installation": {
            "target_profile_path": target_profile_path,
            "rollback_contract_sha256": sha256(canonical(rollback)),
            "baseline_sha256": baseline["baseline_sha256"] if "baseline_sha256" in baseline else sha256(canonical(baseline)),
        },
        "provenance": {
            "commissioning_sha256": commissioning["commissioning_sha256"],
            "blueprint_sha256": _file_sha256(blueprint_path),
            "final_vera_sha256": _file_sha256(final_vera_path),
            "runtime_foundry_input_sha256": runtime_plan["plan_sha256"],
        },
        "authority": {
            "install_authorized": False,
            "runtime_authorized": False,
            "deployment_authorized": False,
            "production_authorized": False,
        },
    }
    contract["contract_sha256"] = _digest_without_contract(contract)
    validate_runtime_contract_value(contract)
    return contract


def validate_runtime_contract_value(contract: dict[str, Any]) -> None:
    Draft202012Validator(load_json(SCHEMA)).validate(contract)
    if _digest_without_contract(contract) != contract["contract_sha256"]:
        raise InstanceRuntimeContractError("Runtime contract hash validation failed")
    if any(contract["authority"].values()):
        raise InstanceRuntimeContractError("Runtime lock cannot grant installation, runtime, deployment, or production authority")


def validate_runtime_contract(mission_root: Path) -> dict[str, Any]:
    contract = load_json(mission_root / "runtime-foundry/instance-runtime-contract.v0.1.json")
    validate_runtime_contract_value(contract)
    return contract
