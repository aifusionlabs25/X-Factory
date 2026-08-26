#!/usr/bin/env python3
"""Phase 4.4 Revision 004 single-transaction Atlas canary controller.

Default execution remains blocked until an exact approval record is present.
Use --verify-only for a read-only preflight that performs no Hermes launch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.phase4_bound_executor_v0_1 import BoundStageExecutorV01
from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_live_runner_v0_5 import DerivationBoundRunnerV05
from x_factory.phase4_payloads import canonical


MISSION_ID = "phase4-atlas-canary-002"
STAGE = "ATLAS_TRIAGE"
PACKET = ROOT / "approvals/pending/phase4-atlas-canary-002"
ACTIVATION_MANIFEST = PACKET / "activation-manifest.json"
BASE_MANIFEST = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-004/live-mission-manifest.v0.3.json"
APPROVAL_RECORD = ROOT / "approvals/approved/phase4-atlas-canary-002.activation.approval.json"
HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_approval(activation: dict) -> None:
    if not APPROVAL_RECORD.is_file():
        raise PermissionError("Exact Atlas canary approval record is absent")
    approval = load(APPROVAL_RECORD)
    if (
        approval.get("status") != "APPROVED_ONE_ATLAS_CANARY"
        or approval.get("mission_id") != MISSION_ID
        or approval.get("activation_manifest_sha256") != file_hash(ACTIVATION_MANIFEST)
        or approval.get("approved_revision_disclosure_sha256") != activation["approved_revision_disclosure_sha256"]
    ):
        raise PermissionError("Atlas canary approval record mismatch")
    if approval.get("authority") != activation.get("authority"):
        raise PermissionError("Atlas canary authority mismatch")


def build_bound_runner(activation: dict) -> tuple[DerivationBoundRunnerV05, Path]:
    activation_schema_path = ROOT / "contracts/phase4/atlas_runtime_canary_activation.v0.2.schema.json"
    if file_hash(activation_schema_path) != activation["activation_schema_sha256"]:
        raise PermissionError("Canary activation schema drift")
    activation_schema = load(activation_schema_path)
    Draft202012Validator(activation_schema).validate(activation)
    if file_hash(BASE_MANIFEST) != activation["base_live_manifest_sha256"]:
        raise PermissionError("Base live manifest drift")
    if file_hash(Path(__file__).resolve()) != activation["controller_sha256"]:
        raise PermissionError("Canary controller drift")

    owner_path = PACKET / "starting-inputs/owner_intake.json"
    if file_hash(owner_path) != activation["owner_intake_file_sha256"]:
        raise PermissionError("Canary owner intake drift")
    live_manifest = load(BASE_MANIFEST)
    live_manifest["mission_id"] = MISSION_ID
    live_manifest["purpose"] = "Execute one contained Atlas-only runtime canary; no later Factory stage is authorized."
    live_manifest["starting_input_hashes"] = {"owner_intake": file_hash(owner_path)}

    manifest_schema_path = ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json"
    manifest_schema = load(manifest_schema_path)
    Draft202012Validator(manifest_schema).validate(live_manifest)
    mission_root = ROOT / "runs/contained" / MISSION_ID
    boundary = activation["write_boundary"]
    if Path(boundary["new_contained_mission_root"]).resolve() != mission_root.resolve():
        raise PermissionError("Declared contained mission write root mismatch")
    if Path(boundary["atlas_profile_root"]).resolve() != (HERMES / "profiles/atlas").resolve():
        raise PermissionError("Declared Atlas profile write root mismatch")
    runner = DerivationBoundRunnerV05(
        ROOT, MISSION_ID, live_manifest,
        load(ROOT / "contracts/phase4/derived_payload_policy.v0.1.json"),
        manifest_schema,
        ledger_path=mission_root / "control/transaction-ledger.json",
    )
    runner.bind_runtime(
        implementation_paths={
            "bound_stage_executor": ROOT / "x_factory/phase4_bound_executor_v0_1.py",
            "deterministic_bundle_generator": ROOT / "x_factory/bundle_generator.py",
            "durable_runner_v0_3": ROOT / "x_factory/phase4_live_runner_v0_3.py",
            "live_mission_runner_v0_4": ROOT / "x_factory/phase4_live_runner_v0_4.py",
            "live_mission_runner_v0_5": ROOT / "x_factory/phase4_live_runner_v0_5.py",
            "phase4_broker": ROOT / "x_factory/phase4_broker.py",
            "phase4_payload_adapter_v0_2": ROOT / "x_factory/phase4_payloads_v0_2.py",
            "runtime_guard_v0_3": ROOT / "x_factory/phase4_transport_guard_v0_3.py",
            "transaction_bound_bridge": ROOT / "scripts/hermes_transaction_bound_bridge_v0_2.py",
        },
        schema_paths={
            "ATLAS_TRIAGE": ROOT / "contracts/intake.v0.1.schema.json",
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
            "agent_init": AGENT / "agent/agent_init.py",
            "agent_runtime_helpers": AGENT / "agent/agent_runtime_helpers.py",
            "chat_completion_helpers": AGENT / "agent/chat_completion_helpers.py",
            "codex_runtime": AGENT / "agent/codex_runtime.py",
            "conversation_loop": AGENT / "agent/conversation_loop.py",
            "credential_pool": AGENT / "agent/credential_pool.py",
            "hermes_auth": AGENT / "hermes_cli/auth.py",
            "hermes_main": AGENT / "hermes_cli/main.py",
            "python_executable": Path(sys.executable),
            "relay_llm": AGENT / "agent/relay_llm.py",
            "run_agent": AGENT / "run_agent.py",
            "tool_executor": AGENT / "agent/tool_executor.py",
        },
        profile_authentication_paths={
            f"{profile}_{kind}": HERMES / "profiles" / profile / filename
            for profile in ("atlas", "aria", "mason", "vera")
            for kind, filename in (("auth_json", "auth.json"), ("auth_lock", "auth.lock"))
        },
    )
    runner.seed_starting_artifact("owner_intake", owner_path)
    payload = runner.derive_payload(STAGE)
    prompt = (
        "Return only one JSON object that validates against the required output schema. "
        "Do not use tools, MCP, memory, delegation, files, or external actions.\n"
        + canonical(payload).decode("utf-8")
    )
    if sha256_bytes(canonical(payload)) != activation["payload_sha256"]:
        raise PermissionError("Derived Atlas payload mismatch")
    if sha256_bytes(prompt.encode("utf-8")) != activation["prompt_sha256"]:
        raise PermissionError("Derived Atlas prompt mismatch")
    if file_hash(ROOT / "contracts/intake.v0.1.schema.json") != activation["output_schema_sha256"]:
        raise PermissionError("Atlas output schema drift")
    return runner, mission_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    activation = load(ACTIVATION_MANIFEST)
    runner, mission_root = build_bound_runner(activation)

    if args.verify_only:
        print(json.dumps({
            "result": "PASS_READ_ONLY",
            "mission_id": MISSION_ID,
            "payload_sha256": activation["payload_sha256"],
            "prompt_sha256": activation["prompt_sha256"],
            "provider_transactions": 0,
            "network_calls": 0
        }, indent=2))
        return

    verify_approval(activation)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required for the canary and child bridge")
    if mission_root.exists():
        raise PermissionError("Canary mission root already exists; retry prohibited")
    runner._verify_baseline()
    (mission_root / "control").mkdir(parents=True)
    executor = BoundStageExecutorV01(runner, ROOT / "scripts/hermes_transaction_bound_bridge_v0_2.py")
    output = executor.execute_stage(STAGE)
    print(json.dumps({"result": "ATLAS_CANARY_ACCEPTED", "mission_id": MISSION_ID, "output": output}, indent=2))


if __name__ == "__main__":
    main()
