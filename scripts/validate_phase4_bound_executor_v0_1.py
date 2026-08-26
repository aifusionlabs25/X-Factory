#!/usr/bin/env python3
"""Offline proof of the transaction-bound executor; no Hermes/provider call."""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.phase4_bound_executor_v0_1 import BoundStageExecutorV01
from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_live_runner_v0_4 import DerivationBoundRunnerV04
from x_factory.phase4_transport_guard_v0_2 import GovernedRuntimeGuard


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rejected(name, action, results):
    try:
        action()
    except PermissionError:
        results.append({"name": name, "result": "PASS_REJECTED"})
        return
    raise AssertionError(f"{name} was not rejected")


def value_after(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def main() -> None:
    fixture_root = ROOT / "verification/phase4/live-runner-v0.3-fixture/factory"
    number = 1
    while (fixture_root / "runs/contained" / f"phase4-v04-offline-{number:03d}").exists():
        number += 1
    mission_id = f"phase4-v04-offline-{number:03d}"
    mission_root = fixture_root / "runs/contained" / mission_id
    (mission_root / "control").mkdir(parents=True)

    schema_path = ROOT / "contracts/phase4/live_mission_manifest.v0.1.schema.json"
    policy_path = ROOT / "contracts/phase4/derived_payload_policy.v0.1.json"
    intake_schema = ROOT / "contracts/intake.v0.1.schema.json"
    owner_source = ROOT / "fixtures/good/phase4-live-synthetic-001.intake.json"
    bridge_path = ROOT / "scripts/hermes_transaction_bound_bridge.py"
    implementation_paths = {
        "transaction_bound_bridge": bridge_path,
        "runner_v04": ROOT / "x_factory/phase4_live_runner_v0_4.py",
        "bound_executor": ROOT / "x_factory/phase4_bound_executor_v0_1.py",
        "runtime_guard": ROOT / "x_factory/phase4_transport_guard_v0_2.py",
    }
    schema_paths = {
        "ATLAS_TRIAGE": intake_schema,
        "ARIA_BLUEPRINT": ROOT / "contracts/x_agent_blueprint.v0.1.schema.json",
        "VERA_SPEC_REVIEW": ROOT / "contracts/evaluation_contract.v0.1.schema.json",
        "MASON_PLAN": ROOT / "contracts/phase4/implementation_decision.v0.1.schema.json",
        "VERA_BUILD_REVIEW": ROOT / "contracts/phase4/build_review.v0.1.schema.json",
    }
    profile_paths = {"offline_profile": owner_source}
    auth_paths = {
        "shared_hermes_auth_json": schema_path,
        "shared_hermes_auth_lock": schema_path,
        "codex_cli_auth_json": schema_path,
    }
    manifest = json.loads((ROOT / "approvals/pending/phase4-live-synthetic-001-revision-001/live-mission-manifest.v0.1.json").read_text(encoding="utf-8"))
    manifest["mission_id"] = mission_id
    manifest["implementation_hashes"] = {name: file_hash(path) for name, path in implementation_paths.items()}
    manifest["schema_hashes"] = {
        "atlas_intake": file_hash(schema_paths["ATLAS_TRIAGE"]),
        "aria_blueprint": file_hash(schema_paths["ARIA_BLUEPRINT"]),
        "vera_specification_review": file_hash(schema_paths["VERA_SPEC_REVIEW"]),
        "mason_implementation_decision": file_hash(schema_paths["MASON_PLAN"]),
        "vera_build_review": file_hash(schema_paths["VERA_BUILD_REVIEW"]),
    }
    manifest["profile_hashes"] = {"offline_profile": file_hash(owner_source)}
    manifest["authentication_baseline"] = {name: file_hash(path) for name, path in auth_paths.items()}
    manifest["derivation_policy_sha256"] = file_hash(policy_path)

    owner = json.loads(owner_source.read_text(encoding="utf-8"))
    owner["run_id"] = mission_id
    owner_path = mission_root / "control/owner-intake.json"
    owner_path.write_text(json.dumps(owner, indent=2) + "\n", encoding="utf-8")
    manifest["starting_input_hashes"] = {"owner_intake": file_hash(owner_path)}

    runner = DerivationBoundRunnerV04(
        fixture_root, mission_id, manifest,
        json.loads(policy_path.read_text(encoding="utf-8")),
        json.loads(schema_path.read_text(encoding="utf-8")),
        ledger_path=mission_root / "control/transaction-ledger.json",
    )
    runner.bind_runtime(
        implementation_paths=implementation_paths,
        schema_paths=schema_paths,
        profile_paths=profile_paths,
        authentication_paths=auth_paths,
        derivation_policy_path=policy_path,
    )
    runner.seed_starting_artifact("owner_intake", owner_path)

    launcher_calls = []

    def fake_launcher(command, cwd):
        launcher_calls.append({"command": command, "cwd": str(cwd)})
        prompt_path = Path(value_after(command, "--prompt-file"))
        evidence_path = Path(value_after(command, "--evidence-file"))
        stdout = json.dumps(owner, separators=(",", ":")).encode()
        stderr = b""
        evidence = {
            "schema_version": "0.1",
            "mission_id": value_after(command, "--mission-id"),
            "transaction": int(value_after(command, "--transaction")),
            "stage": value_after(command, "--stage"),
            "profile": value_after(command, "--profile"),
            "prompt_sha256": value_after(command, "--prompt-sha256"),
            "payload_sha256": value_after(command, "--payload-sha256"),
            "bridge_sha256": value_after(command, "--bridge-sha256"),
            "exit_code": 0,
            "physical_requests": 1,
            "tool_attempts": 0,
            "oauth_refresh_attempts": 0,
            "auth_write_attempts": 0,
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_sha256": sha256_bytes(stderr),
            "stdout_base64": base64.b64encode(stdout).decode(),
            "stderr_base64": base64.b64encode(stderr).decode(),
            "error_type": None,
            "error_message": None,
        }
        assert file_hash(prompt_path) == evidence["prompt_sha256"]
        evidence_path.write_text(json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    executor = BoundStageExecutorV01(runner, bridge_path, offline_launcher=fake_launcher)
    output = executor.execute_stage("ATLAS_TRIAGE")
    assert output == owner
    assert runner.chain[-1]["status"] == "ACCEPTED"
    assert len(launcher_calls) == 1
    assert Path(launcher_calls[0]["cwd"]) == mission_root

    negatives = []
    rejected("direct_acceptance", lambda: runner.accept_captured_response("ATLAS_TRIAGE", owner), negatives)
    rejected(
        "invalid_executor_capability",
        lambda: runner._accept_bound_execution(
            "ATLAS_TRIAGE", owner, execution={}, execution_sha256="sha256:" + "0" * 64, capability=object()
        ),
        negatives,
    )

    guard = GovernedRuntimeGuard()
    rejected("oauth_refresh", guard.blocked_refresh, negatives)
    rejected("auth_write", guard.blocked_auth_write, negatives)
    rejected("tool_dispatch", guard.blocked_tool, negatives)
    assert guard.oauth_refresh_attempts == guard.auth_write_attempts == guard.tool_attempts == 1

    calls = []
    wrapped = guard.request_wrapper(lambda: calls.append("physical") or "ok")
    assert wrapped() == "ok"
    rejected("second_physical_request", wrapped, negatives)
    assert calls == ["physical"]

    print(json.dumps({
        "result": "PASS",
        "revision": "0.4",
        "mission_fixture": mission_id,
        "findings_targeted": ["P4R-009", "P4R-012", "P4R-014", "P4R-015"],
        "negative_tests": negatives,
        "bound_executor_launches": len(launcher_calls),
        "real_subprocess_launches": 0,
        "provider_transactions": 0,
        "network_calls": 0,
        "external_actions": 0
    }, indent=2))


if __name__ == "__main__":
    main()
