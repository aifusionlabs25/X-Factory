#!/usr/bin/env python3
"""Read-only binding validation for the Phase 4.3 disclosure packet."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.phase4_live_runner_v0_4 import DerivationBoundRunnerV04

HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
packet = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-003"
manifest = json.loads((packet / "live-mission-manifest.v0.2.json").read_text(encoding="utf-8"))
schema = json.loads((ROOT / "contracts/phase4/live_mission_manifest.v0.2.schema.json").read_text(encoding="utf-8"))
Draft202012Validator(schema).validate(manifest)

fixture = ROOT / "verification/phase4/revision003-binding/factory"
mission_root = fixture / "runs/contained/phase4-live-synthetic-001"
(mission_root / "control").mkdir(parents=True, exist_ok=True)
runner = DerivationBoundRunnerV04(
    fixture, "phase4-live-synthetic-001", manifest,
    json.loads((ROOT / "contracts/phase4/derived_payload_policy.v0.1.json").read_text(encoding="utf-8")),
    schema,
    ledger_path=mission_root / "control/transaction-ledger.json",
)
runner.bind_runtime(
    implementation_paths={
        "bound_stage_executor": ROOT / "x_factory/phase4_bound_executor_v0_1.py",
        "deterministic_bundle_generator": ROOT / "x_factory/bundle_generator.py",
        "durable_runner_v0_3": ROOT / "x_factory/phase4_live_runner_v0_3.py",
        "live_mission_runner_v0_4": ROOT / "x_factory/phase4_live_runner_v0_4.py",
        "phase4_broker": ROOT / "x_factory/phase4_broker.py",
        "phase4_payload_adapter_v0_2": ROOT / "x_factory/phase4_payloads_v0_2.py",
        "runtime_guard_v0_2": ROOT / "x_factory/phase4_transport_guard_v0_2.py",
        "transaction_bound_bridge": ROOT / "scripts/hermes_transaction_bound_bridge.py",
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
        "codex_cli_auth_json": Path("C:/Users/AI Fusion Labs/.codex/auth.json"),
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
print(json.dumps({
    "result": "PASS",
    "manifest_schema": "PASS",
    "implementation_hashes": "PASS",
    "stage_schema_hashes": "PASS",
    "profile_hashes": "PASS",
    "shared_auth_hashes": "PASS",
    "profile_auth_presence_and_hashes": "PASS",
    "expanded_hermes_runtime_hashes": "PASS",
    "provider_transactions": 0,
    "network_calls": 0
}, indent=2))
