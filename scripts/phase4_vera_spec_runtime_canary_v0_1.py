#!/usr/bin/env python3
"""One-transaction Vera specification-review continuation controller.

The default execution path is blocked until the exact activation manifest is
approved. ``--verify-only`` is read-only and performs no Hermes launch.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.phase4_bound_executor_v0_2 import BoundStageExecutorV02
from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_live_runner_v0_7 import DerivationBoundRunnerV07
from x_factory.phase4_payloads import canonical


ACTIVATION_ID = "phase4-vera-spec-canary-001"
MISSION_ID = "phase4-atlas-canary-003"
STAGE = "VERA_SPEC_REVIEW"
PACKET = ROOT / "approvals/pending" / ACTIVATION_ID
ACTIVATION_MANIFEST = PACKET / "activation-manifest.json"
BASE_MANIFEST = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-007/live-mission-manifest.v0.3.json"
APPROVAL_RECORD = ROOT / "approvals/approved/phase4-vera-spec-canary-001.activation.approval.json"
MISSION_ROOT = ROOT / "runs/contained" / MISSION_ID
LEDGER = MISSION_ROOT / "control/transaction-ledger.json"
ATLAS_EVIDENCE = MISSION_ROOT / "control/transaction-01.bridge-evidence.json"
ARIA_EVIDENCE = MISSION_ROOT / "control/transaction-02.bridge-evidence.json"
OWNER = ROOT / "approvals/pending/phase4-atlas-canary-003/starting-inputs/owner_intake.json"
COMPONENTS = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-001/starting-inputs/component_catalog.json"
EVIDENCE_INDEX = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-001/starting-inputs/evidence_index.json"
HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_approval(activation: dict) -> None:
    if not APPROVAL_RECORD.is_file():
        raise PermissionError("Exact Vera specification-review approval record is absent")
    approval = load(APPROVAL_RECORD)
    if (
        approval.get("status") != "APPROVED_ONE_VERA_SPEC_CONTINUATION"
        or approval.get("activation_id") != ACTIVATION_ID
        or approval.get("mission_id") != MISSION_ID
        or approval.get("activation_manifest_sha256") != file_hash(ACTIVATION_MANIFEST)
        or approval.get("approved_revision_disclosure_sha256") != activation["approved_revision_disclosure_sha256"]
    ):
        raise PermissionError("Vera continuation approval record mismatch")
    if approval.get("authority") != activation.get("authority"):
        raise PermissionError("Vera continuation authority mismatch")


def build_bound_runner(activation: dict) -> DerivationBoundRunnerV07:
    schema_path = ROOT / "contracts/phase4/vera_spec_runtime_continuation_activation.v0.1.schema.json"
    if file_hash(schema_path) != activation["activation_schema_sha256"]:
        raise PermissionError("Vera activation schema drift")
    Draft202012Validator(load(schema_path)).validate(activation)
    if file_hash(BASE_MANIFEST) != activation["base_live_manifest_sha256"]:
        raise PermissionError("Base live manifest drift")
    if file_hash(Path(__file__).resolve()) != activation["controller_sha256"]:
        raise PermissionError("Vera controller drift")
    if file_hash(LEDGER) != activation["accepted_ledger_sha256"]:
        raise PermissionError("Accepted transaction ledger drift")
    if file_hash(ATLAS_EVIDENCE) != activation["atlas_execution_evidence_sha256"]:
        raise PermissionError("Atlas execution evidence drift")
    if file_hash(ARIA_EVIDENCE) != activation["aria_execution_evidence_sha256"]:
        raise PermissionError("Aria execution evidence drift")
    if file_hash(OWNER) != activation["owner_intake_file_sha256"]:
        raise PermissionError("Owner intake drift")
    if file_hash(COMPONENTS) != activation["component_catalog_file_sha256"]:
        raise PermissionError("Component catalog drift")
    if file_hash(EVIDENCE_INDEX) != activation["evidence_index_file_sha256"]:
        raise PermissionError("Evidence index drift")

    ledger_document = load(LEDGER)
    entries = ledger_document.get("entries")
    if ledger_document.get("mission_id") != MISSION_ID or not isinstance(entries, list) or len(entries) != 2:
        raise PermissionError("Exactly two accepted ledger-prefix entries are required")
    expected_prefix = [(1, "ATLAS_TRIAGE"), (2, "ARIA_BLUEPRINT")]
    if [(entry.get("transaction"), entry.get("stage")) for entry in entries] != expected_prefix or any(entry.get("status") != "ACCEPTED" for entry in entries):
        raise PermissionError("Accepted Atlas and Aria ledger prefix is invalid")

    manifest = load(BASE_MANIFEST)
    manifest["mission_id"] = MISSION_ID
    manifest["purpose"] = "Continue accepted Atlas and Aria results through exactly one contained Vera specification-review transaction."
    manifest["starting_input_hashes"] = {
        "owner_intake": file_hash(OWNER),
        "component_catalog": file_hash(COMPONENTS),
        "evidence_index": file_hash(EVIDENCE_INDEX),
    }
    manifest_schema_path = ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json"
    manifest_schema = load(manifest_schema_path)
    Draft202012Validator(manifest_schema).validate(manifest)

    boundary = activation["write_boundary"]
    if Path(boundary["existing_contained_mission_root"]).resolve() != MISSION_ROOT.resolve():
        raise PermissionError("Declared contained mission root mismatch")
    if Path(boundary["vera_profile_root"]).resolve() != (HERMES / "profiles/vera").resolve():
        raise PermissionError("Declared Vera profile root mismatch")

    runner = DerivationBoundRunnerV07(
        ROOT, MISSION_ID, manifest,
        load(ROOT / "contracts/phase4/derived_payload_policy.v0.1.json"),
        manifest_schema,
        ledger_path=LEDGER,
    )
    runner.bind_runtime(
        implementation_paths={
            "bound_stage_executor_v0_2": ROOT / "x_factory/phase4_bound_executor_v0_2.py",
            "deterministic_bundle_generator": ROOT / "x_factory/bundle_generator.py",
            "durable_runner_v0_3": ROOT / "x_factory/phase4_live_runner_v0_3.py",
            "live_mission_runner_v0_4": ROOT / "x_factory/phase4_live_runner_v0_4.py",
            "live_mission_runner_v0_5": ROOT / "x_factory/phase4_live_runner_v0_5.py",
            "live_mission_runner_v0_6": ROOT / "x_factory/phase4_live_runner_v0_6.py",
            "live_mission_runner_v0_7": ROOT / "x_factory/phase4_live_runner_v0_7.py",
            "phase4_broker": ROOT / "x_factory/phase4_broker.py",
            "phase4_payload_adapter_v0_2": ROOT / "x_factory/phase4_payloads_v0_2.py",
            "runtime_guard_v0_4": ROOT / "x_factory/phase4_transport_guard_v0_4.py",
            "transaction_bound_bridge": ROOT / "scripts/hermes_transaction_bound_bridge_v0_3.py",
        },
        schema_paths={
            "ATLAS_TRIAGE": ROOT / "contracts/phase4/normalized_intake.v0.1.schema.json",
            "ARIA_BLUEPRINT": ROOT / "contracts/x_agent_blueprint.v0.1.schema.json",
            "VERA_SPEC_REVIEW": ROOT / "contracts/evaluation_contract.v0.1.schema.json",
            "MASON_PLAN": ROOT / "contracts/phase4/implementation_decision.v0.1.schema.json",
            "VERA_BUILD_REVIEW": ROOT / "contracts/phase4/build_review.v0.1.schema.json",
        },
        profile_paths={
            f"{profile}_{kind}": HERMES / "profiles" / profile / filename
            for profile in ("atlas", "aria", "mason", "vera")
            for kind, filename in (("config", "config.yaml"), ("profile", "profile.yaml"), ("soul", "SOUL.md"))
        },
        authentication_paths={
            "shared_hermes_auth_json": HERMES / "auth.json",
            "shared_hermes_auth_lock": HERMES / "auth.lock",
        },
        derivation_policy_path=ROOT / "contracts/phase4/derived_payload_policy.v0.1.json",
        hermes_runtime_paths={
            "agent_init": AGENT / "agent/agent_init.py", "agent_runtime_helpers": AGENT / "agent/agent_runtime_helpers.py",
            "chat_completion_helpers": AGENT / "agent/chat_completion_helpers.py", "codex_runtime": AGENT / "agent/codex_runtime.py",
            "conversation_loop": AGENT / "agent/conversation_loop.py", "credential_pool": AGENT / "agent/credential_pool.py",
            "hermes_auth": AGENT / "hermes_cli/auth.py", "hermes_main": AGENT / "hermes_cli/main.py",
            "python_executable": Path(sys.executable), "relay_llm": AGENT / "agent/relay_llm.py",
            "run_agent": AGENT / "run_agent.py", "tool_executor": AGENT / "agent/tool_executor.py",
        },
        profile_authentication_paths={
            f"{profile}_{kind}": HERMES / "profiles" / profile / filename
            for profile in ("atlas", "aria", "mason", "vera")
            for kind, filename in (("auth_json", "auth.json"), ("auth_lock", "auth.lock"))
        },
    )
    runner.seed_starting_artifact("owner_intake", OWNER)
    runner.seed_starting_artifact("component_catalog", COMPONENTS)
    runner.seed_starting_artifact("evidence_index", EVIDENCE_INDEX)
    execution = load(ATLAS_EVIDENCE)
    atlas_output = json.loads(base64.b64decode(execution["response_base64"], validate=True).decode("utf-8"))
    runner.restore_accepted_output("ATLAS_TRIAGE", atlas_output, ATLAS_EVIDENCE)
    execution = load(ARIA_EVIDENCE)
    aria_output = json.loads(base64.b64decode(execution["response_base64"], validate=True).decode("utf-8"))
    runner.restore_accepted_output("ARIA_BLUEPRINT", aria_output, ARIA_EVIDENCE)
    payload, prompt = runner.compose_transmission(STAGE)
    if sha256_bytes(canonical(payload)) != activation["payload_sha256"]:
        raise PermissionError("Derived Vera payload mismatch")
    if sha256_bytes(prompt.encode("utf-8")) != activation["prompt_sha256"]:
        raise PermissionError("Derived Vera prompt mismatch")
    if file_hash(ROOT / "contracts/evaluation_contract.v0.1.schema.json") != activation["output_schema_sha256"]:
        raise PermissionError("Vera output schema drift")
    return runner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    activation = load(ACTIVATION_MANIFEST)
    runner = build_bound_runner(activation)

    if args.verify_only:
        print(json.dumps({
            "result": "PASS_READ_ONLY",
            "activation_id": ACTIVATION_ID,
            "mission_id": MISSION_ID,
            "accepted_prefix_transactions": len(runner.chain),
            "next_transaction": 3,
            "payload_sha256": activation["payload_sha256"],
            "prompt_sha256": activation["prompt_sha256"],
            "ledger_writes": 0,
            "provider_transactions": 0,
            "network_calls": 0,
        }, indent=2))
        return

    verify_approval(activation)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required for the canary and child bridge")
    if file_hash(LEDGER) != activation["accepted_ledger_sha256"]:
        raise PermissionError("Ledger changed after approval; transmission blocked")
    runner._verify_baseline()
    executor = BoundStageExecutorV02(runner, ROOT / "scripts/hermes_transaction_bound_bridge_v0_3.py")
    output = executor.execute_stage(STAGE)
    print(json.dumps({"result": "VERA_SPEC_CANARY_ACCEPTED", "mission_id": MISSION_ID, "output": output}, indent=2))


if __name__ == "__main__":
    main()
