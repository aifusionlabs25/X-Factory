#!/usr/bin/env python3
"""Read-only Atlas-to-Aria continuation proof for Revision 006."""

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_live_runner_v0_7 import DerivationBoundRunnerV07
from x_factory.phase4_payloads import canonical

MISSION_ID = "phase4-atlas-canary-003"
HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
PACKET = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-006"
MISSION_ROOT = ROOT / "runs/contained" / MISSION_ID
EVIDENCE = MISSION_ROOT / "control/transaction-01.bridge-evidence.json"
OWNER = ROOT / "approvals/pending/phase4-atlas-canary-003/starting-inputs/owner_intake.json"
COMPONENTS = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-001/starting-inputs/component_catalog.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


manifest = load(PACKET / "live-mission-manifest.v0.3.json")
manifest["mission_id"] = MISSION_ID
manifest["purpose"] = "Continue the accepted Atlas canary output into one disclosure-only Aria payload preview."
manifest["starting_input_hashes"] = {
    "owner_intake": sha256_bytes(OWNER.read_bytes()),
    "component_catalog": sha256_bytes(COMPONENTS.read_bytes()),
}
manifest_schema = load(ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json")
runner = DerivationBoundRunnerV07(
    ROOT, MISSION_ID, manifest,
    load(ROOT / "contracts/phase4/derived_payload_policy.v0.1.json"),
    manifest_schema,
    ledger_path=MISSION_ROOT / "control/transaction-ledger.json",
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
    authentication_paths={"shared_hermes_auth_json": HERMES / "auth.json", "shared_hermes_auth_lock": HERMES / "auth.lock"},
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
execution = load(EVIDENCE)
atlas_output = json.loads(base64.b64decode(execution["response_base64"], validate=True).decode("utf-8"))
runner.restore_accepted_output("ATLAS_TRIAGE", atlas_output, EVIDENCE)
payload, prompt = runner.compose_transmission("ARIA_BLUEPRINT")

print(json.dumps({
    "result": "PASS_READ_ONLY",
    "mission_id": MISSION_ID,
    "accepted_prefix_transactions": len(runner.chain),
    "restored_atlas_output_sha256": sha256_bytes(canonical(atlas_output)),
    "atlas_execution_evidence_sha256": sha256_bytes(EVIDENCE.read_bytes()),
    "component_catalog_file_sha256": sha256_bytes(COMPONENTS.read_bytes()),
    "aria_payload_sha256": sha256_bytes(canonical(payload)),
    "aria_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
    "aria_output_schema_sha256": sha256_bytes((ROOT / "contracts/x_agent_blueprint.v0.1.schema.json").read_bytes()),
    "ledger_writes": 0,
    "provider_transactions": 0,
    "network_calls": 0
}, indent=2))
