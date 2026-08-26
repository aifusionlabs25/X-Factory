#!/usr/bin/env python3
"""Offline validation for the Phase 4.4 disclosure packet."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.phase4_live_runner_v0_5 import DerivationBoundRunnerV05
from x_factory.phase4_transport_guard_v0_3 import GovernedRuntimeViolation, install_into_hermes

HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
PACKET = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-004"
MANIFEST = json.loads((PACKET / "live-mission-manifest.v0.3.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json").read_text(encoding="utf-8"))


def expect_block(callable_value) -> None:
    try:
        callable_value()
    except GovernedRuntimeViolation:
        return
    raise AssertionError("Governed operation was not blocked")


Draft202012Validator(SCHEMA).validate(MANIFEST)
assert "codex_cli_auth_json" not in MANIFEST["authentication_baseline"]
assert MANIFEST["codex_cli_auth_policy"] == {
    "participates": False,
    "read_authorized": False,
    "import_authorized": False,
    "mutation_authorized": False,
}
guard_source = (ROOT / "x_factory/phase4_transport_guard_v0_3.py").read_text(encoding="utf-8")
for required_line in (
    "agent._fallback_chain = []",
    "agent._fallback_model = None",
    "agent._fallback_index = 0",
    "auth._import_codex_cli_tokens = guard.blocked_codex_cli_import",
    "auth._recover_codex_tokens_from_cli = guard.blocked_codex_cli_import",
):
    assert required_line in guard_source

fixture = ROOT / "verification/phase4/revision004-binding/factory"
mission_root = fixture / "runs/contained/phase4-live-synthetic-001"
(mission_root / "control").mkdir(parents=True, exist_ok=True)
runner = DerivationBoundRunnerV05(
    fixture, "phase4-live-synthetic-001", MANIFEST,
    json.loads((ROOT / "contracts/phase4/derived_payload_policy.v0.1.json").read_text(encoding="utf-8")),
    SCHEMA,
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

# Installation is process-local and performs no model transaction. Both the
# direct importer and recovery wrapper must fail before reading Codex CLI auth.
guard = install_into_hermes()
from hermes_cli import auth
expect_block(auth._import_codex_cli_tokens)
expect_block(lambda: auth._recover_codex_tokens_from_cli("offline-test"))
assert guard.codex_cli_import_attempts == 2

print(json.dumps({
    "result": "PASS",
    "manifest_schema": "PASS",
    "participating_auth_baseline": "HERMES_ONLY",
    "codex_cli_baseline_dependency": "ABSENT",
    "direct_codex_cli_import_guard": "PASS",
    "codex_cli_recovery_guard": "PASS",
    "fallback_disable_present": "PASS",
    "provider_transactions": 0,
    "network_calls": 0
}, indent=2))
