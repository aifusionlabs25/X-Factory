#!/usr/bin/env python3
"""Offline validation for the Phase 4.5 Revision 005 packet."""

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from scripts.hermes_transaction_bound_bridge_v0_3 import extract_single_json_suffix
from x_factory.phase4_live_runner_v0_6 import DerivationBoundRunnerV06
from x_factory.phase4_transport_guard_v0_3 import GovernedRuntimeViolation
from x_factory.phase4_transport_guard_v0_4 import install_into_hermes

HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
PACKET = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-005"
MANIFEST = json.loads((PACKET / "live-mission-manifest.v0.3.json").read_text(encoding="utf-8"))
MANIFEST_SCHEMA = json.loads((ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json").read_text(encoding="utf-8"))
ATLAS_SCHEMA = json.loads((ROOT / "contracts/phase4/normalized_intake.v0.1.schema.json").read_text(encoding="utf-8"))
OWNER = ROOT / "approvals/pending/phase4-live-synthetic-001-revision-001/starting-inputs/owner_intake.json"

Draft202012Validator(MANIFEST_SCHEMA).validate(MANIFEST)
owner_value = json.loads(OWNER.read_text(encoding="utf-8"))
Draft202012Validator(ATLAS_SCHEMA).validate(owner_value)

# Prove strict extraction against the exact consumed canary terminal bytes.
failed_evidence = json.loads((ROOT / "runs/contained/phase4-atlas-canary-002/control/transaction-01.bridge-evidence.json").read_text(encoding="utf-8"))
terminal_bytes = base64.b64decode(failed_evidence["stdout_base64"], validate=True)
response_bytes, response_offset = extract_single_json_suffix(terminal_bytes)
extracted = json.loads(response_bytes)
assert response_offset == 189
assert extracted["mission_id"] == "phase4-atlas-canary-002"
for rejected in (b"no json", b'{}\n{}', b'{} trailing'):
    try:
        extract_single_json_suffix(rejected)
    except PermissionError:
        pass
    else:
        raise AssertionError("Ambiguous or contaminated machine response was accepted")

factory = ROOT / "verification/phase4/revision005-readonly-fixture"
control = factory / "runs/contained/phase4-live-synthetic-001/control"
if True:
    runner = DerivationBoundRunnerV06(
        factory, "phase4-live-synthetic-001", MANIFEST,
        json.loads((ROOT / "contracts/phase4/derived_payload_policy.v0.1.json").read_text(encoding="utf-8")),
        MANIFEST_SCHEMA,
        ledger_path=control / "transaction-ledger.json",
    )
    runner.bind_runtime(
        implementation_paths={
            "bound_stage_executor_v0_2": ROOT / "x_factory/phase4_bound_executor_v0_2.py",
            "deterministic_bundle_generator": ROOT / "x_factory/bundle_generator.py",
            "durable_runner_v0_3": ROOT / "x_factory/phase4_live_runner_v0_3.py",
            "live_mission_runner_v0_4": ROOT / "x_factory/phase4_live_runner_v0_4.py",
            "live_mission_runner_v0_5": ROOT / "x_factory/phase4_live_runner_v0_5.py",
            "live_mission_runner_v0_6": ROOT / "x_factory/phase4_live_runner_v0_6.py",
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
    payload, prompt = runner.compose_transmission("ATLAS_TRIAGE")
    assert payload["required_output_schema_id"] == "normalized_intake.v0.1"
    assert "EXACT OUTPUT JSON SCHEMA:\n" in prompt
    assert '"additionalProperties":false' in prompt

guard_source = (ROOT / "x_factory/phase4_transport_guard_v0_4.py").read_text(encoding="utf-8")
for line in ("agent.show_reasoning = False", "agent.quiet_mode = True", "agent.suppress_status_output = True"):
    assert line in guard_source
executor_source = (ROOT / "x_factory/phase4_bound_executor_v0_2.py").read_text(encoding="utf-8")
assert 'execution["response_base64"]' in executor_source
assert 'execution.get("response_sha256")' in executor_source
assert 'json.loads(response_bytes.decode("utf-8"))' in executor_source
assert 'json.loads(stdout_bytes.decode("utf-8").strip())' not in executor_source
guard = install_into_hermes()
from hermes_cli import auth
for blocked in (auth._import_codex_cli_tokens, lambda: auth._recover_codex_tokens_from_cli("offline")):
    try:
        blocked()
    except GovernedRuntimeViolation:
        pass
    else:
        raise AssertionError("Codex CLI import guard failed")

print(json.dumps({
    "result": "PASS",
    "atlas_normalized_intake_schema": "PASS",
    "exact_schema_embedded_in_prompt": "PASS",
    "captured_canary_machine_extraction": "PASS",
    "ambiguous_response_rejection": "PASS",
    "reasoning_presentation_suppression": "PASS",
    "executor_machine_response_binding": "PASS",
    "codex_cli_import_guards": "PASS",
    "provider_transactions": 0,
    "network_calls": 0
}, indent=2))
