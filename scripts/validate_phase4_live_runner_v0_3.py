#!/usr/bin/env python3
"""Offline negative/positive proof for the inert Phase 4.2 candidates."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_live_runner_v0_3 import DerivationBoundRunnerV03
from x_factory.phase4_transport_guard_v0_1 import (
    PhysicalRequestBudgetExceeded,
    SinglePhysicalRequestGuard,
)


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def expect_rejected(name: str, action, results: list[dict[str, str]]) -> None:
    try:
        action()
    except PermissionError:
        results.append({"name": name, "result": "PASS_REJECTED"})
        return
    raise AssertionError(f"{name} was not rejected")


def main() -> None:
    fixture_root = ROOT / "verification" / "phase4" / "live-runner-v0.3-fixture" / "factory"
    sequence = 1
    while (fixture_root / "runs" / "contained" / f"phase4-v03-offline-{sequence:03d}").exists():
        sequence += 1
    mission_id = f"phase4-v03-offline-{sequence:03d}"
    mission_root = fixture_root / "runs" / "contained" / mission_id
    control_root = mission_root / "control"
    control_root.mkdir(parents=True)

    manifest_schema_path = ROOT / "contracts" / "phase4" / "live_mission_manifest.v0.1.schema.json"
    policy_path = ROOT / "contracts" / "phase4" / "derived_payload_policy.v0.1.json"
    owner_intake_path = ROOT / "fixtures" / "good" / "phase4-live-synthetic-001.intake.json"
    schema_paths = {
        "ATLAS_TRIAGE": ROOT / "contracts" / "intake.v0.1.schema.json",
        "ARIA_BLUEPRINT": ROOT / "contracts" / "x_agent_blueprint.v0.1.schema.json",
        "VERA_SPEC_REVIEW": ROOT / "contracts" / "evaluation_contract.v0.1.schema.json",
        "MASON_PLAN": ROOT / "contracts" / "phase4" / "implementation_decision.v0.1.schema.json",
        "VERA_BUILD_REVIEW": ROOT / "contracts" / "phase4" / "build_review.v0.1.schema.json",
    }
    implementation_paths = {
        "runner_v03": ROOT / "x_factory" / "phase4_live_runner_v0_3.py",
        "request_guard": ROOT / "x_factory" / "phase4_transport_guard_v0_1.py",
        "guarded_bridge": ROOT / "scripts" / "hermes_guarded_single_request_bridge.py",
    }
    profile_paths = {"offline_profile_fixture": owner_intake_path}
    authentication_paths = {"offline_auth_fixture": manifest_schema_path}

    base = json.loads(
        (ROOT / "approvals" / "pending" / "phase4-live-synthetic-001-revision-001" / "live-mission-manifest.v0.1.json").read_text(encoding="utf-8")
    )
    manifest = copy.deepcopy(base)
    manifest["mission_id"] = mission_id
    manifest["starting_input_hashes"] = {"owner_intake": file_hash(owner_intake_path)}
    manifest["implementation_hashes"] = {name: file_hash(path) for name, path in implementation_paths.items()}
    manifest["schema_hashes"] = {
        "atlas_intake": file_hash(schema_paths["ATLAS_TRIAGE"]),
        "aria_blueprint": file_hash(schema_paths["ARIA_BLUEPRINT"]),
        "vera_specification_review": file_hash(schema_paths["VERA_SPEC_REVIEW"]),
        "mason_implementation_decision": file_hash(schema_paths["MASON_PLAN"]),
        "vera_build_review": file_hash(schema_paths["VERA_BUILD_REVIEW"]),
    }
    manifest["profile_hashes"] = {name: file_hash(path) for name, path in profile_paths.items()}
    manifest["authentication_baseline"] = {
        "shared_hermes_auth_json": file_hash(manifest_schema_path),
        "shared_hermes_auth_lock": file_hash(manifest_schema_path),
        "codex_cli_auth_json": file_hash(manifest_schema_path),
    }
    authentication_paths = {
        "shared_hermes_auth_json": manifest_schema_path,
        "shared_hermes_auth_lock": manifest_schema_path,
        "codex_cli_auth_json": manifest_schema_path,
    }
    manifest["derivation_policy_sha256"] = file_hash(policy_path)

    runner = DerivationBoundRunnerV03(
        factory_root=fixture_root,
        mission_id=mission_id,
        manifest=manifest,
        policy=json.loads(policy_path.read_text(encoding="utf-8")),
        manifest_schema=json.loads(manifest_schema_path.read_text(encoding="utf-8")),
        ledger_path=control_root / "transaction-ledger.json",
    )
    runner.bind_runtime(
        implementation_paths=implementation_paths,
        schema_paths=schema_paths,
        profile_paths=profile_paths,
        authentication_paths=authentication_paths,
        derivation_policy_path=policy_path,
    )

    owner_intake = json.loads(owner_intake_path.read_text(encoding="utf-8"))
    owner_intake["run_id"] = mission_id
    owner_fixture = control_root / "owner-intake.json"
    owner_fixture.write_text(json.dumps(owner_intake, indent=2) + "\n", encoding="utf-8")
    runner.manifest["starting_input_hashes"]["owner_intake"] = file_hash(owner_fixture)
    runner.seed_starting_artifact("owner_intake", owner_fixture)

    envelope = runner.prepare_transmission("ATLAS_TRIAGE")
    ledger_after_reserve = json.loads((control_root / "transaction-ledger.json").read_text(encoding="utf-8"))
    assert ledger_after_reserve["entries"][0]["status"] == "RESERVED_BEFORE_TRANSMISSION"

    fake_calls: list[str] = []
    guard = SinglePhysicalRequestGuard()

    def fake_stream(value: str) -> str:
        fake_calls.append(value)
        return value

    wrapped = guard.wrap(fake_stream)
    assert wrapped("first") == "first"
    negative: list[dict[str, str]] = []
    expect_rejected("second_physical_request", lambda: wrapped("second"), negative)
    assert fake_calls == ["first"]

    evidence = {
        "stdout_sha256": sha256_bytes(json.dumps(owner_intake).encode()),
        "stderr_sha256": sha256_bytes(b""),
        "execution_sha256": sha256_bytes(b"offline-fake-transport"),
    }
    runner.accept_captured_response(
        "ATLAS_TRIAGE",
        owner_intake,
        raw_evidence=evidence,
        physical_requests=guard.calls_started,
        tool_calls=0,
    )
    expect_rejected("caller_asserted_evidence", lambda: runner.accept_response("ATLAS_TRIAGE", owner_intake), negative)
    expect_rejected("retry_after_acceptance", lambda: runner.prepare_transmission("ATLAS_TRIAGE"), negative)

    # A crash/restart after reservation must fail closed, without another request.
    crash_id = mission_id + "-crash"
    crash_root = fixture_root / "runs" / "contained" / crash_id / "control"
    crash_root.mkdir(parents=True)
    crash_manifest = copy.deepcopy(manifest)
    crash_manifest["mission_id"] = crash_id
    crash_runner = DerivationBoundRunnerV03(
        fixture_root, crash_id, crash_manifest,
        json.loads(policy_path.read_text(encoding="utf-8")),
        json.loads(manifest_schema_path.read_text(encoding="utf-8")),
        ledger_path=crash_root / "transaction-ledger.json",
    )
    crash_runner.bind_runtime(
        implementation_paths=implementation_paths, schema_paths=schema_paths,
        profile_paths=profile_paths, authentication_paths=authentication_paths,
        derivation_policy_path=policy_path,
    )
    crash_input = copy.deepcopy(owner_intake)
    crash_input["run_id"] = crash_id
    crash_file = crash_root / "owner-intake.json"
    crash_file.write_text(json.dumps(crash_input, indent=2) + "\n", encoding="utf-8")
    crash_runner.manifest["starting_input_hashes"]["owner_intake"] = file_hash(crash_file)
    crash_runner.seed_starting_artifact("owner_intake", crash_file)
    crash_runner.prepare_transmission("ATLAS_TRIAGE")
    expect_rejected(
        "restart_with_unfinished_reservation",
        lambda: DerivationBoundRunnerV03(
            fixture_root, crash_id, crash_manifest,
            json.loads(policy_path.read_text(encoding="utf-8")),
            json.loads(manifest_schema_path.read_text(encoding="utf-8")),
            ledger_path=crash_root / "transaction-ledger.json",
        ),
        negative,
    )

    report = {
        "result": "PASS",
        "revision": "0.3",
        "mission_fixture": mission_id,
        "findings_targeted": ["P4R-007", "P4R-008", "P4R-009", "P4R-011", "P4R-012"],
        "negative_tests": negative,
        "durable_reservation_observed_before_transport": True,
        "fake_transport_physical_calls": len(fake_calls),
        "provider_transport_present": False,
        "provider_transactions": 0,
        "network_calls": 0,
        "external_actions": 0,
        "envelope_prompt_sha256": sha256_bytes(envelope["prompt"].encode()),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
