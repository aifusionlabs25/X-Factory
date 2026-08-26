#!/usr/bin/env python3
"""Run one fully authorized, contained Phase 4 governed draft mission."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.mission_control_preview_generator_v0_1 import generate as generate_preview
from x_factory.phase4_bound_executor_v0_2 import BoundStageExecutorV02
from x_factory.phase4_broker import require_within, sha256_bytes
from x_factory.phase4_live_runner_v0_8 import GovernanceBoundRunnerV08
from x_factory.phase4_payloads import canonical


MISSION_ID = os.environ.get("X_FACTORY_MISSION_ID", "phase4-governed-draft-001")
PACKET = ROOT / "approvals/pending" / f"{MISSION_ID}-mission"
ACTIVATION = PACKET / "activation-manifest.json"
LIVE_MANIFEST = PACKET / "live-mission-manifest.v0.3.json"
APPROVAL = ROOT / "approvals/approved" / f"{MISSION_ID}.full-mission.approval.json"
MISSION_ROOT = ROOT / "runs/contained" / MISSION_ID
HERMES = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes")
AGENT = HERMES / "hermes-agent"
OWNER = PACKET / "starting-inputs/owner-intake.json"
COMPONENTS = PACKET / "starting-inputs/component-catalog.json"
GOVERNANCE = PACKET / "starting-inputs/governance-binding.json"
EVIDENCE_INDEX = PACKET / "starting-inputs/evidence-index.json"
CONTRACTS = ROOT / "contracts/phase1_3"
GENERATION = CONTRACTS / "deterministic_generation.v0.3.json"
OUTPUT_CONTRACT = CONTRACTS / "output_bundle_manifest.v0.3.json"
ACCEPTANCE = CONTRACTS / "acceptance_fixture.v0.3.json"


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path = require_within(path, MISSION_ROOT, "mission artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".next")
    if path.exists() or temporary.exists():
        raise PermissionError(f"Mission artifact must be new: {path.name}")
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def verify_approval(activation: dict[str, Any]) -> None:
    if not APPROVAL.is_file():
        raise PermissionError("Exact full-mission approval record is absent")
    value = load(APPROVAL)
    if (
        value.get("status") != "APPROVED_ONE_FULL_CONTAINED_GOVERNED_MISSION"
        or value.get("mission_id") != MISSION_ID
        or value.get("activation_manifest_sha256") != file_hash(ACTIVATION)
        or value.get("packet_manifest_sha256") != activation["packet_manifest_sha256"]
    ):
        raise PermissionError("Full-mission approval record mismatch")
    if value.get("authority") != activation.get("authority"):
        raise PermissionError("Full-mission authority mismatch")


def build_runner(activation: dict[str, Any]) -> GovernanceBoundRunnerV08:
    schema_path = ROOT / "contracts/phase4/full_mission_activation.v0.1.schema.json"
    if file_hash(schema_path) != activation["activation_schema_sha256"]:
        raise PermissionError("Activation schema drift")
    Draft202012Validator(load(schema_path)).validate(activation)
    if file_hash(Path(__file__).resolve()) != activation["controller_sha256"]:
        raise PermissionError("Full-mission controller drift")
    if file_hash(LIVE_MANIFEST) != activation["live_manifest_sha256"]:
        raise PermissionError("Live mission manifest drift")
    declared = {
        "owner_intake_sha256": OWNER,
        "component_catalog_sha256": COMPONENTS,
        "governance_binding_sha256": GOVERNANCE,
        "evidence_index_sha256": EVIDENCE_INDEX,
        "generation_contract_sha256": GENERATION,
        "output_contract_sha256": OUTPUT_CONTRACT,
        "acceptance_fixture_sha256": ACCEPTANCE,
    }
    for field, path in declared.items():
        if file_hash(path) != activation[field]:
            raise PermissionError(f"Bound mission input drift: {field}")

    manifest = load(LIVE_MANIFEST)
    manifest_schema_path = ROOT / "contracts/phase4/live_mission_manifest.v0.3.schema.json"
    manifest_schema = load(manifest_schema_path)
    Draft202012Validator(manifest_schema).validate(manifest)
    runner = GovernanceBoundRunnerV08(
        ROOT, MISSION_ID, manifest,
        load(ROOT / "contracts/phase4/derived_payload_policy.v0.2.json"),
        manifest_schema,
        ledger_path=MISSION_ROOT / "control/transaction-ledger.json",
    )
    runner.bind_runtime(
        implementation_paths={
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
        },
        schema_paths={
            "ATLAS_TRIAGE": ROOT / "contracts/phase4/normalized_intake.v0.2.schema.json",
            "ARIA_BLUEPRINT": ROOT / "contracts/x_agent_blueprint.v0.2.schema.json",
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
        derivation_policy_path=ROOT / "contracts/phase4/derived_payload_policy.v0.2.json",
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
    runner.bind_governance(GOVERNANCE)
    runner.seed_starting_artifact("owner_intake", OWNER)
    runner.seed_starting_artifact("component_catalog", COMPONENTS)
    runner.seed_starting_artifact("evidence_index", EVIDENCE_INDEX)
    runner.seed_starting_artifact("generation_contract", GENERATION)
    runner.seed_starting_artifact("output_contract", OUTPUT_CONTRACT)
    runner.seed_starting_artifact("acceptance_fixture", ACCEPTANCE)
    payload, prompt = runner.compose_transmission("ATLAS_TRIAGE")
    if sha256_bytes(canonical(payload)) != activation["atlas_payload_sha256"]:
        raise PermissionError("Exact Atlas payload drift")
    if sha256_bytes(prompt.encode()) != activation["atlas_prompt_sha256"]:
        raise PermissionError("Exact Atlas prompt drift")
    return runner


def file_map(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): file_hash(path) for path in sorted(root.rglob("*")) if path.is_file()}


def run_acceptance(candidate: Path, blueprint: Path, fixture_root: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["X_FACTORY_NETWORK_DISABLED"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["X_FACTORY_BLUEPRINT_PATH"] = str(blueprint)
    environment["X_FACTORY_CONTRACTS_DIR"] = str(CONTRACTS)
    environment["X_FACTORY_FIXTURE_ROOT"] = str(fixture_root)
    environment["PYTHONPATH"] = str(ROOT)
    for key in ("ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        environment.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_bundle", "-v"],
        cwd=candidate, env=environment, capture_output=True, text=True, timeout=180, check=False,
    )
    return {"exit_code": result.returncode, "stdout_sha256": sha256_bytes(result.stdout.encode()), "stderr_sha256": sha256_bytes(result.stderr.encode())}


def deterministic_build(runner: GovernanceBoundRunnerV08) -> None:
    blueprint = runner.artifacts["approved_blueprint"]
    blueprint_path = MISSION_ROOT / "artifacts/aria-blueprint.v0.2.json"
    atomic_json(blueprint_path, blueprint)
    builds: list[dict[str, Any]] = []
    for number, label in ((1, "RUN_1"), (2, "RUN_2")):
        base = MISSION_ROOT / "build" / f"run-{number}"
        output = base / "output"
        evidence = base / "evidence"
        output.mkdir(parents=True, exist_ok=False)
        evidence.mkdir(parents=True, exist_ok=False)
        environment = os.environ.copy()
        environment["X_FACTORY_NETWORK_DISABLED"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(ROOT)
        for key in ("ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
            environment.pop(key, None)
        process = subprocess.run(
            [sys.executable, "-m", "x_factory.bundle_generator_v0_4", "generate", "--blueprint", str(blueprint_path), "--contracts", str(CONTRACTS), "--output", str(output), "--evidence", str(evidence), "--run-label", label],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120, check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(f"Deterministic build {label} failed")
        acceptance = run_acceptance(output, blueprint_path, MISSION_ROOT / "acceptance-fixture" / f"run-{number}")
        if acceptance["exit_code"] != 0:
            raise RuntimeError(f"Acceptance {label} failed")
        builds.append({"label": label, "files": file_map(output), "acceptance": acceptance, "manifest": load(output / "bundle.manifest.json")})
    if builds[0]["files"] != builds[1]["files"]:
        raise PermissionError("Deterministic build outputs differ")

    preview = MISSION_ROOT / "preview"
    preview.mkdir(parents=True, exist_ok=False)
    previous = os.environ.get("X_FACTORY_NETWORK_DISABLED")
    os.environ["X_FACTORY_NETWORK_DISABLED"] = "1"
    try:
        generate_preview(OWNER, blueprint_path, preview)
    finally:
        if previous is None:
            os.environ.pop("X_FACTORY_NETWORK_DISABLED", None)
        else:
            os.environ["X_FACTORY_NETWORK_DISABLED"] = previous
    preview_hashes = file_map(preview)
    root_digest = "sha256:" + builds[0]["manifest"]["root_digest"]
    candidate_manifest = {"schema_version": "0.1", "mission_id": MISSION_ID, "candidate_root_digest": root_digest, "candidate_files": builds[0]["files"], "preview_files": preview_hashes}
    test_evidence = {"schema_version": "0.1", "mission_id": MISSION_ID, "status": "PASS", "repeatable": True, "run_1": builds[0]["acceptance"], "run_2": builds[1]["acceptance"], "network_attempts": 0, "external_actions": 0}
    build_record = {"schema_version": "0.1", "mission_id": MISSION_ID, "status": "CONTAINED_BUILD_COMPLETE", "candidate_root_digest": root_digest, "provider_calls": 0, "network_attempts": 0, "external_actions": 0, "preview_generated": True}
    paths = {
        "candidate_manifest": MISSION_ROOT / "artifacts/deterministic/candidate-manifest.json",
        "test_evidence": MISSION_ROOT / "artifacts/deterministic/test-evidence.json",
        "build_record": MISSION_ROOT / "artifacts/deterministic/build-record.json",
    }
    for name, value in (("candidate_manifest", candidate_manifest), ("test_evidence", test_evidence), ("build_record", build_record)):
        atomic_json(paths[name], value)
        runner.register_deterministic_artifact(name, value, paths[name])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    activation = load(ACTIVATION)
    runner = build_runner(activation)
    if args.verify_only:
        print(json.dumps({"result": "PASS_READ_ONLY", "mission_id": MISSION_ID, "atlas_payload_sha256": activation["atlas_payload_sha256"], "atlas_prompt_sha256": activation["atlas_prompt_sha256"], "maximum_provider_transactions": 5, "network_calls": 0, "mission_root_created": False}, indent=2))
        return

    verify_approval(activation)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required")
    if MISSION_ROOT.exists():
        raise PermissionError("Fresh mission root already exists; retry prohibited")
    (MISSION_ROOT / "control").mkdir(parents=True)
    executor = BoundStageExecutorV02(runner, ROOT / "scripts/hermes_transaction_bound_bridge_v0_3.py")
    executor.execute_stage("ATLAS_TRIAGE")
    executor.execute_stage("ARIA_BLUEPRINT")
    executor.execute_stage("VERA_SPEC_REVIEW")
    runner.authorize_conditional_build()
    executor.execute_stage("MASON_PLAN")
    deterministic_build(runner)
    final_output = executor.execute_stage("VERA_BUILD_REVIEW")
    summary = {"schema_version": "0.1", "mission_id": MISSION_ID, "status": "DRAFT_READY", "model_transactions": 5, "preview": "preview/index.html", "verdict": final_output.get("verdict")}
    atomic_json(MISSION_ROOT / "draft-ready-summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
