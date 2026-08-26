#!/usr/bin/env python3
"""Prepare one consolidated, ANAM-aware governed Hermes certification mission."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_payloads import canonical
from x_factory.phase4_payloads_v0_3 import make_stage_payload_v0_3

MISSION_ID = "phase4-governed-draft-002"
PACKET = ROOT / "approvals/pending" / f"{MISSION_ID}-mission"
APPROVED = ROOT / "approvals/approved"
MISSION_ROOT = ROOT / "runs/contained" / MISSION_ID
HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
BASE_OWNER = ROOT / "approvals/pending/phase4-governed-draft-001-bootstrap/starting-inputs/owner_intake.json"
BASE_COMPONENTS = ROOT / "approvals/pending/phase4-governed-draft-001-bootstrap/starting-inputs/component_catalog.json"
RECOVERY = ROOT / "runs/contained/phase4-governed-draft-001-local-recovery-004/artifacts"
CONTROLLER = ROOT / "scripts/phase4_governed_full_mission_v0_1.py"
ACTIVATION_SCHEMA = ROOT / "contracts/phase4/full_mission_activation.v0.1.schema.json"
MANIFEST_SCHEMA = ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json"
DERIVATION_POLICY = ROOT / "contracts/phase4/derived_payload_policy.v0.2.json"
CONTRACTS = ROOT / "contracts/phase1_3"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest_bytes(data: bytes) -> str:
    return sha256_bytes(data)


def file_hash(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="")


def file_state(path: Path) -> dict[str, Any]:
    return {"exists": path.is_file(), "sha256": file_hash(path) if path.is_file() else None}


def main() -> int:
    if PACKET.exists() or MISSION_ROOT.exists():
        raise PermissionError("Fresh packet and mission root are required")

    experience = load(RECOVERY / "experience-shell.v0.1.json")
    Draft202012Validator(load(ROOT / "contracts/phase4/experience_shell.v0.1.schema.json")).validate(experience)

    authorization_root = {
        "schema_version": "0.1",
        "status": "APPROVED_BY_OWNER_PROCEED",
        "mission_id": MISSION_ID,
        "user_instruction": "Proceed.",
        "authorized_objective": "Run one consolidated Hermes certification mission for the corrected X-Agent Core plus ANAM-aware Experience Shell architecture.",
        "provider": "openai-codex",
        "model": "gpt-5.6-luna",
        "maximum_transactions": 5,
        "retry": False,
        "tools": False,
        "external_provider_mutation": False,
        "deployment": False,
        "production": False,
    }
    authorization_path = APPROVED / f"{MISSION_ID}.authorization-root.json"
    write_json(authorization_path, authorization_root)
    authorization_hash = file_hash(authorization_path)

    owner = load(BASE_OWNER)
    owner["run_id"] = MISSION_ID
    owner["purpose"] = "Create a polished local browser-based concierge draft with a separable Hermes X-Agent Core and ANAM-aware Experience Shell, approved FAQ behavior, request qualification, visible session notes, and a structured staff handoff without external actions."
    owner["must_have_capabilities"] = list(dict.fromkeys(owner["must_have_capabilities"] + ["selectable avatar presence", "ANAM-ready experience shell", "stock-image and text fallback", "visible AI disclosure"]))
    owner["raw_owner_text"] += " The Factory must build the agent core separately from a selectable Experience Shell supporting an existing ANAM avatar, a new ANAM creation brief, a stock image, or text-only operation. No ANAM provider mutation is authorized by this mission."
    owner["implementation_inputs"]["experience_shell"] = experience
    owner["implementation_inputs"]["interface_requirements"] = list(dict.fromkeys(owner["implementation_inputs"]["interface_requirements"] + ["Offer existing ANAM, create ANAM, stock image, and text-only presence choices", "Show the avatar or fallback state in the live preview", "Keep the Hermes X-Agent Core usable when the avatar is unavailable"]))

    components = load(BASE_COMPONENTS)
    components["components"].append({
        "component_id": "CMP-ANAM-PRESENCE-SHELL",
        "name": "ANAM-compatible avatar presence shell",
        "category": "experience-layer",
        "status": "COMPATIBILITY_CHECK_REQUIRED",
        "requirements_served": ["existing ANAM avatar", "new ANAM creation brief", "stock-image fallback", "text fallback", "AI disclosure", "separable experience shell"],
        "dependencies": ["X_LINK_ANAM_ADAPTER", "owner-selected or Factory-recommended presence mode", "client-approved visual and voice choices"],
        "constraints": ["No ANAM creation or mutation in this mission", "No credentials in model payloads or build artifacts", "Runtime compatibility remains unproven until a separately authorized canary", "The agent core must remain usable without ANAM"],
        "evidence_refs": ["EVD-ANAM-DESIGN-CONTRACT-V1"],
    })

    disclosure = {
        "schema_version": "0.1", "mission_id": MISSION_ID,
        "classification": "CONTAINED_SYNTHETIC_CERTIFICATION",
        "disclosed_inputs": ["owner intake", "component catalog", "synthetic concierge evidence", "ANAM design contract evidence", "stage predecessor outputs", "exact stage output schemas"],
        "limitations": ["No real customer data", "No ANAM credentials", "No ANAM provider call or mutation", "No deployment, release, production, or live Factory write"],
    }
    disclosure_hash = digest_bytes(canonical(disclosure))

    evidence_index = {
        "schema_version": "0.2", "mission_id": MISSION_ID,
        "records": [
            {
                "evidence_id": "EVD-SYNTHETIC-CONCIERGE-V2", "classification": "SYNTHETIC_FIXTURE_ONLY",
                "artifact_sha256": "sha256:ec29a68c29d4463e0627a67a852af3ebd6eae21770e09f10d4e5a6b6e483db4c",
                "approval_record_sha256": authorization_hash, "approval_status": "APPROVED_FOR_THIS_CONTAINED_CERTIFICATION",
                "approved_scope": MISSION_ID, "capabilities_demonstrated": ["fixed FAQ lookup", "guided form progression", "in-memory live notes", "display-only structured handoff", "local reset"],
                "limitations": ["Synthetic fixture only", "No real customer evidence", "No deployment or production proof"],
            },
            {
                "evidence_id": "EVD-ANAM-DESIGN-CONTRACT-V1", "classification": "OWNER_SPECIFIED_DESIGN_CONTRACT_ONLY",
                "artifact_sha256": file_hash(ROOT / "contracts/phase4/experience_shell.v0.1.schema.json"),
                "approval_record_sha256": authorization_hash, "approval_status": "APPROVED_FOR_THIS_CONTAINED_CERTIFICATION",
                "approved_scope": MISSION_ID, "capabilities_demonstrated": ["presence-mode specification", "fallback specification", "AI disclosure specification", "provider-mutation boundary"],
                "limitations": ["No ANAM runtime compatibility proof", "No provider creation proof", "No avatar-quality claim", "No deployment or production proof"],
            },
        ],
    }
    governance = {
        "schema_version": "0.1", "governed_run_marker": "X_FACTORY_GOVERNED_RUN_V0_1", "mission_id": MISSION_ID,
        "disclosure_manifest_sha256": disclosure_hash, "owner_approval_sha256": authorization_hash,
        "broker_run_record": {
            "schema_version": "0.1", "governed_run_marker": "X_FACTORY_GOVERNED_RUN_V0_1", "execution_mode": "BROKERED_NO_TOOLS",
            "mission_id": MISSION_ID, "disclosure_manifest_sha256": disclosure_hash, "owner_approval_sha256": authorization_hash,
            "broker": "X_FACTORY_DETERMINISTIC_BROKER_V0_8", "lifecycle_authority": "CONTAINED_DRAFT_ONLY",
        },
        "evidence_approvals": [
            {"evidence_id": r["evidence_id"], "artifact_sha256": r["artifact_sha256"], "approval_record_sha256": authorization_hash,
             "approval_status": "APPROVED_FOR_CONTAINED_FIXTURE_ONLY", "scope": MISSION_ID, "limitations": r["limitations"]}
            for r in evidence_index["records"]
        ],
    }

    owner_path = PACKET / "starting-inputs/owner-intake.json"
    components_path = PACKET / "starting-inputs/component-catalog.json"
    evidence_path = PACKET / "starting-inputs/evidence-index.json"
    governance_path = PACKET / "starting-inputs/governance-binding.json"
    disclosure_path = PACKET / "starting-inputs/disclosure-manifest.json"
    for path, value in ((owner_path, owner), (components_path, components), (evidence_path, evidence_index), (governance_path, governance), (disclosure_path, disclosure)):
        write_json(path, value)

    implementation_paths = {
        "bound_stage_executor_v0_2": ROOT / "x_factory/phase4_bound_executor_v0_2.py",
        "deterministic_bundle_generator": ROOT / "x_factory/bundle_generator.py",
        "deterministic_bundle_generator_v0_4": ROOT / "x_factory/bundle_generator_v0_4.py",
        "durable_runner_v0_3": ROOT / "x_factory/phase4_live_runner_v0_3.py",
        "live_mission_runner_v0_4": ROOT / "x_factory/phase4_live_runner_v0_4.py",
        "live_mission_runner_v0_5": ROOT / "x_factory/phase4_live_runner_v0_5.py",
        "live_mission_runner_v0_6": ROOT / "x_factory/phase4_live_runner_v0_6.py",
        "live_mission_runner_v0_7": ROOT / "x_factory/phase4_live_runner_v0_7.py",
        "live_mission_runner_v0_8": ROOT / "x_factory/phase4_live_runner_v0_8.py",
        "mission_control_preview_generator_v0_1": ROOT / "x_factory/mission_control_preview_generator_v0_1.py",
        "phase4_broker": ROOT / "x_factory/phase4_broker.py",
        "phase4_payload_adapter_v0_2": ROOT / "x_factory/phase4_payloads_v0_2.py",
        "phase4_payload_adapter_v0_3": ROOT / "x_factory/phase4_payloads_v0_3.py",
        "runtime_guard_v0_4": ROOT / "x_factory/phase4_transport_guard_v0_4.py",
        "transaction_bound_bridge": ROOT / "scripts/hermes_transaction_bound_bridge_v0_3.py",
    }
    schema_paths = {
        "atlas_intake": ROOT / "contracts/phase4/normalized_intake.v0.2.schema.json",
        "aria_blueprint": ROOT / "contracts/x_agent_blueprint.v0.2.schema.json",
        "vera_specification_review": ROOT / "contracts/evaluation_contract.v0.1.schema.json",
        "mason_implementation_decision": ROOT / "contracts/phase4/implementation_decision.v0.1.schema.json",
        "vera_build_review": ROOT / "contracts/phase4/build_review.v0.1.schema.json",
        "live_mission_manifest": MANIFEST_SCHEMA,
        "experience_shell": ROOT / "contracts/phase4/experience_shell.v0.1.schema.json",
    }
    profile_paths = {
        f"{profile}_{kind}": HERMES / "profiles" / profile / filename
        for profile in ("atlas", "aria", "mason", "vera")
        for kind, filename in (("config", "config.yaml"), ("profile", "profile.yaml"), ("soul", "SOUL.md"))
    }
    runtime_paths = {
        "agent_init": AGENT / "agent/agent_init.py", "agent_runtime_helpers": AGENT / "agent/agent_runtime_helpers.py",
        "chat_completion_helpers": AGENT / "agent/chat_completion_helpers.py", "codex_runtime": AGENT / "agent/codex_runtime.py",
        "conversation_loop": AGENT / "agent/conversation_loop.py", "credential_pool": AGENT / "agent/credential_pool.py",
        "hermes_auth": AGENT / "hermes_cli/auth.py", "hermes_main": AGENT / "hermes_cli/main.py",
        "python_executable": Path(sys.executable), "relay_llm": AGENT / "agent/relay_llm.py", "run_agent": AGENT / "run_agent.py",
        "tool_executor": AGENT / "agent/tool_executor.py",
    }
    for group in (implementation_paths, schema_paths, profile_paths, runtime_paths):
        for path in group.values():
            if not path.is_file():
                raise FileNotFoundError(path)

    generation = CONTRACTS / "deterministic_generation.v0.3.json"
    output_contract = CONTRACTS / "output_bundle_manifest.v0.3.json"
    acceptance = CONTRACTS / "acceptance_fixture.v0.3.json"
    shared_auth = HERMES / "auth.json"
    shared_lock = HERMES / "auth.lock"
    manifest = {
        "schema_version": "0.3", "manifest_id": "PHASE4-CODEX-IMPORT-PROHIBITED-LIVE-MISSION-V3", "mission_id": MISSION_ID,
        "purpose": "Execute one fully governed contained ANAM-aware mission to produce a locally inspectable synthetic Desert Home Services X-Agent Core and Experience Shell draft.",
        "provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low", "maximum_model_transactions": 5,
        "starting_input_hashes": {"owner_intake": file_hash(owner_path), "component_catalog": file_hash(components_path), "evidence_index": file_hash(evidence_path), "governance_binding": file_hash(governance_path), "generation_contract": file_hash(generation), "output_contract": file_hash(output_contract), "acceptance_fixture": file_hash(acceptance)},
        "implementation_hashes": {name: file_hash(path) for name, path in implementation_paths.items()},
        "schema_hashes": {name: file_hash(path) for name, path in schema_paths.items()},
        "profile_hashes": {name: file_hash(path) for name, path in profile_paths.items()},
        "authentication_baseline": {"shared_hermes_auth_json": file_hash(shared_auth), "shared_hermes_auth_lock": file_hash(shared_lock)},
        "codex_cli_auth_policy": {"participates": False, "read_authorized": False, "import_authorized": False, "mutation_authorized": False},
        "profile_authentication_baseline": {f"{profile}_{kind}": file_state(HERMES / "profiles" / profile / filename) for profile in ("atlas", "aria", "mason", "vera") for kind, filename in (("auth_json", "auth.json"), ("auth_lock", "auth.lock"))},
        "hermes_runtime_hashes": {name: file_hash(path) for name, path in runtime_paths.items()},
        "runtime_write_policy": {"shared_auth_mutation_authorized": False, "codex_cli_auth_mutation_authorized": False, "other_profile_mutation_authorized": False, "contained_factory_write_only": True},
        "derivation_policy_sha256": file_hash(DERIVATION_POLICY),
        "authority": {"one_contained_synthetic_mission": True, "conditional_contained_build": True, "tools": False, "oauth_refresh": False, "live_factory_write": False, "installation": False, "deployment": False, "release": False, "production": False},
        "disclosure": {"downstream_bytes_dynamic": True, "derivation_rules_bound": True, "post_derivation_hash_chain_required": True},
    }
    Draft202012Validator(load(MANIFEST_SCHEMA)).validate(manifest)
    manifest_path = PACKET / "live-mission-manifest.v0.3.json"
    write_json(manifest_path, manifest)

    payload = make_stage_payload_v0_3("ATLAS_TRIAGE", MISSION_ID, {"owner_intake": owner}, "normalized_intake.v0.2", governance)
    prompt = "Return only one JSON object that validates against the exact JSON Schema below. Do not wrap it in Markdown. Do not use tools, MCP, memory, delegation, files, or external actions.\nGOVERNED PAYLOAD:\n" + canonical(payload).decode() + "\nEXACT OUTPUT JSON SCHEMA:\n" + canonical(load(schema_paths["atlas_intake"])).decode()
    write_json(PACKET / "atlas-derived-payload.json", payload)
    write_text(PACKET / "atlas-derived-prompt.txt", prompt)

    preflight = {"schema_version": "0.1", "mission_id": MISSION_ID, "status": "PASS", "network_calls": 0, "mission_root_created": False, "experience_shell_valid": True, "owner_authorization_root_sha256": authorization_hash}
    write_json(PACKET / "review-evidence/preflight-results.json", preflight)
    readme = "# Phase 4 ANAM-aware consolidated certification\n\nOne Atlas → Aria → Vera → Mason → deterministic build → Vera mission. Maximum five Luna transactions, no retry, no tools, no ANAM provider mutation, and no deployment or production authority.\n"
    write_text(PACKET / "README.md", readme)

    packet_files = [manifest_path, governance_path, evidence_path, disclosure_path, owner_path, components_path, PACKET / "atlas-derived-payload.json", PACKET / "atlas-derived-prompt.txt", PACKET / "review-evidence/preflight-results.json", PACKET / "README.md"]
    packet_manifest = {
        "schema_version": "0.1", "status": "AUTHORIZED_BY_CONSOLIDATED_OWNER_PROCEED", "mission_id": MISSION_ID,
        "files": {p.relative_to(PACKET).as_posix(): file_hash(p) for p in packet_files},
        "bound_external_files": {p.relative_to(ROOT).as_posix(): file_hash(p) for p in [ACTIVATION_SCHEMA, CONTROLLER, ROOT / "x_factory/phase4_payloads_v0_3.py", ROOT / "x_factory/phase4_live_runner_v0_8.py", ROOT / "x_factory/bundle_generator_v0_4.py", ROOT / "x_factory/mission_control_preview_generator_v0_1.py", ROOT / "contracts/phase4/experience_shell.v0.1.schema.json"]},
        "runtime": {"provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low", "maximum_provider_transactions": 5, "maximum_per_stage": 1, "retry": False, "tools": False},
        "provider_transactions_before_activation": 0, "network_calls_before_activation": 0, "mission_root_created": False,
    }
    packet_manifest_path = PACKET / "packet-manifest.json"
    write_json(packet_manifest_path, packet_manifest)

    authority = {"one_full_contained_mission": True, "provider_transport": True, "maximum_transactions": 5, "conditional_contained_build": True, "deterministic_two_run_build": True, "local_visual_preview": True, "tools": False, "mcp": False, "memory": False, "delegation": False, "oauth_refresh": False, "authentication_mutation": False, "retry": False, "installation": False, "deployment": False, "release": False, "production": False, "live_factory_write": False}
    activation = {
        "schema_version": "0.1", "status": "PENDING_SINGLE_FULL_MISSION_APPROVAL_NOT_ACTIVE", "mission_id": MISSION_ID,
        "activation_schema_sha256": file_hash(ACTIVATION_SCHEMA), "controller_sha256": file_hash(CONTROLLER), "live_manifest_sha256": file_hash(manifest_path), "packet_manifest_sha256": file_hash(packet_manifest_path),
        "owner_intake_sha256": file_hash(owner_path), "component_catalog_sha256": file_hash(components_path), "governance_binding_sha256": file_hash(governance_path), "evidence_index_sha256": file_hash(evidence_path),
        "generation_contract_sha256": file_hash(generation), "output_contract_sha256": file_hash(output_contract), "acceptance_fixture_sha256": file_hash(acceptance),
        "atlas_payload_sha256": digest_bytes(canonical(payload)), "atlas_prompt_sha256": digest_bytes(prompt.encode()),
        "runtime": {"provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning": "low", "maximum_provider_transactions": 5, "maximum_per_stage": 1, "retry": False, "tools": False},
        "write_boundary": {"new_contained_mission_root": str(MISSION_ROOT), "profile_roots": [str(HERMES / "profiles" / p) for p in ("atlas", "aria", "vera", "mason")], "ordinary_profile_runtime_state": True, "authentication_content_mutation": False, "preview_output": f"runs/contained/{MISSION_ID}/preview"},
        "authority": authority,
        "failure_policy": {"pre_transmission_drift": "BLOCK_BEFORE_TRANSMISSION", "stage_failure": "FAIL_TERMINAL_NO_RETRY", "invalid_output": "FAIL_TERMINAL_NO_RETRY", "wrong_verdict": "FAIL_TERMINAL_NO_RETRY", "build_failure": "FAIL_TERMINAL_NO_RETRY"},
    }
    Draft202012Validator(load(ACTIVATION_SCHEMA)).validate(activation)
    activation_path = PACKET / "activation-manifest.json"
    write_json(activation_path, activation)
    approval = {"schema_version": "0.1", "status": "APPROVED_ONE_FULL_CONTAINED_GOVERNED_MISSION", "mission_id": MISSION_ID, "authorization_root_sha256": authorization_hash, "activation_manifest_sha256": file_hash(activation_path), "packet_manifest_sha256": file_hash(packet_manifest_path), "authority": authority}
    write_json(APPROVED / f"{MISSION_ID}.full-mission.approval.json", approval)
    print(json.dumps({"status": "READY", "mission_id": MISSION_ID, "activation_sha256": file_hash(activation_path), "packet_sha256": file_hash(packet_manifest_path), "authorization_root_sha256": authorization_hash, "network_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
