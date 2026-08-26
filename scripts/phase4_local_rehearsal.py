#!/usr/bin/env python3
"""Run one provider-free end-to-end Phase 4 rehearsal with canned cognition."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

FACTORY_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(FACTORY_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORY_MODULE_ROOT))

from x_factory.phase4_broker import Phase4Broker, sha256_bytes
from x_factory.phase4_payloads import digest, factory_floor_event, make_stage_payload


REQUIRED_CANDIDATE_FILES = [
    "agent/AGENT.md",
    "agent/agent.spec.json",
    "bundle.manifest.json",
    "tests/fixtures/smoke.input.json",
    "tests/test_bundle.py",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def copy_frozen(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    return sha256_file(destination)


def file_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def safe_fixture_intake(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "agent_or_client": "Desert Home Services",
        "purpose": "Create a friendly fictional local-service concierge for a contained draft.",
        "role_and_behavior": "Warm, concise, and transparent about uncertainty.",
        "must_have_capabilities": ["approved FAQ responses", "request qualification", "structured handoff"],
        "never_do": ["quote final prices", "book appointments", "send email", "write to a CRM"],
        "sources": ["EVD-SYNTHETIC-BUSINESS-RULES", "EVD-SYNTHETIC-CONCIERGE-PATTERN"],
        "raw_owner_text": "Create a contained fictional concierge draft with no external actions.",
        "default_external_actions": "PROHIBITED_UNLESS_EXPLICITLY_APPROVED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--run-id", default="phase4-local-rehearsal-001")
    args = parser.parse_args()
    root = args.factory_root.resolve()
    run_dir = root / "runs" / "contained" / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Rehearsal run already exists: {run_dir}")

    blueprint_source = root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json"
    spec_verdict_source = root / "runs" / "contained" / "contained-real-card-proof-004" / "vera" / "evaluation.v0.1.json"
    expected_candidate = root / "builds" / "controlled" / "controlled-build-004" / "fixture" / "run-1" / "output"
    contracts = root / "contracts" / "phase1_3"
    for path in (blueprint_source, spec_verdict_source, expected_candidate, contracts):
        if not path.exists():
            raise FileNotFoundError(f"Frozen rehearsal source is missing: {path}")

    intake = safe_fixture_intake(args.run_id)
    payload_catalog = {"components": ["CMP-CONVERSATION-SHELL", "CMP-STRUCTURED-HANDOFF"], "evidence_ids": intake["sources"]}
    evidence_index = {"approved_ids": intake["sources"], "unapproved_items": 0}
    blueprint = load_json(blueprint_source)
    blueprint_summary = {
        "candidate_id": blueprint["candidate_id"],
        "owner_intent": blueprint["owner_intent"],
        "specification_status": blueprint["authority"]["specification_status"],
        "requirement_count": len(blueprint["requirements"]),
        "authority": {"build": False, "deployment": False, "production": False},
    }
    contract_values = {
        "generation_contract": load_json(contracts / "deterministic_generation.v0.3.json"),
        "output_contract": load_json(contracts / "output_bundle_manifest.v0.3.json"),
        "acceptance_fixture": load_json(contracts / "acceptance_fixture.v0.3.json"),
    }
    contract_summaries = {
        name: {"contract_id": value.get("contract_id", value.get("schema_version", name)), "sha256": digest(value)}
        for name, value in contract_values.items()
    }
    owner_approval = {"decision": "APPROVE_LOCAL_REHEARSAL_BUILD", "scope": "SYNTHETIC_CONTAINED_DRAFT_ONLY"}

    payloads = {
        "ATLAS_TRIAGE": make_stage_payload("ATLAS_TRIAGE", args.run_id, {"owner_intake": intake}, "intake.v0.1"),
        "ARIA_BLUEPRINT": make_stage_payload("ARIA_BLUEPRINT", args.run_id, {"normalized_intake": intake, "component_catalog": payload_catalog}, "x_agent_blueprint.v0.1"),
        "VERA_SPEC_REVIEW": make_stage_payload("VERA_SPEC_REVIEW", args.run_id, {"normalized_intake": intake, "frozen_blueprint": blueprint_summary, "evidence_index": evidence_index}, "evaluation_contract.v0.1"),
        "MASON_PLAN": make_stage_payload("MASON_PLAN", args.run_id, {"approved_blueprint": blueprint_summary, **contract_summaries, "owner_build_approval": owner_approval}, "implementation_decision.v0.1"),
    }
    for stage, payload in payloads.items():
        write_json(run_dir / "payloads" / f"{stage.lower()}.json", payload)

    broker = Phase4Broker(args.run_id, digest(intake))
    broker.approve_launch()
    events: list[dict[str, Any]] = []

    atlas_path = run_dir / "atlas" / "normalized_intake.json"
    write_json(atlas_path, intake)
    atlas_hash = sha256_file(atlas_path)
    broker.advance("ATLAS_TRIAGE", "ATLAS", payloads["ATLAS_TRIAGE"]["input_hashes"], atlas_hash, model_transaction=False)
    events.append(factory_floor_event(1, "ATLAS_TRIAGE", "CANNED_COMPLETE", "Atlas normalized the synthetic mission intake.", atlas_hash))

    blueprint_path = run_dir / "aria" / "frozen_blueprint.json"
    blueprint_hash = copy_frozen(blueprint_source, blueprint_path)
    broker.advance("ARIA_BLUEPRINT", "ARIA", payloads["ARIA_BLUEPRINT"]["input_hashes"], blueprint_hash, model_transaction=False)
    events.append(factory_floor_event(2, "ARIA_BLUEPRINT", "CANNED_COMPLETE", "Aria supplied the previously frozen synthetic blueprint.", blueprint_hash))

    spec_path = run_dir / "vera" / "specification_verdict.json"
    spec_hash = copy_frozen(spec_verdict_source, spec_path)
    broker.advance("VERA_SPEC_REVIEW", "VERA", payloads["VERA_SPEC_REVIEW"]["input_hashes"], spec_hash, model_transaction=False)
    events.append(factory_floor_event(3, "VERA_SPEC_REVIEW", "CANNED_COMPLETE", "Vera supplied the previously approved specification verdict.", spec_hash))

    owner_path = run_dir / "owner" / "build_decision.json"
    write_json(owner_path, owner_approval)
    owner_hash = sha256_file(owner_path)
    broker.advance("OWNER_BUILD_DECISION", "ROB", {"specification_verdict": spec_hash}, owner_hash, owner_build_approval=True)

    mason_response = {
        "schema_version": "0.1",
        "mission_id": args.run_id,
        "decision": "IMPLEMENTATION_PLAN_READY",
        "input_hashes": {
            "approved_blueprint": blueprint_hash,
            "generation_contract": sha256_file(contracts / "deterministic_generation.v0.3.json"),
            "output_contract": sha256_file(contracts / "output_bundle_manifest.v0.3.json"),
            "acceptance_fixture": sha256_file(contracts / "acceptance_fixture.v0.3.json"),
        },
        "runtime_target": "CONTAINED_SYNTHETIC_X_AGENT_DRAFT",
        "implementation_steps": ["Generate the five contract-declared candidate files", "Run the deterministic acceptance fixture"],
        "expected_outputs": REQUIRED_CANDIDATE_FILES,
        "acceptance_commands": ["Run the declared standard-library acceptance suite"],
        "blockers": [],
        "authority": {"plan_only": True, "file_access": False, "build_authorized": False, "install_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    mason_schema = load_json(root / "contracts" / "phase4" / "implementation_decision.v0.1.schema.json")
    errors = list(Draft202012Validator(mason_schema).iter_errors(mason_response))
    if errors:
        raise AssertionError("Canned Mason decision is invalid")
    mason_path = run_dir / "mason" / "implementation_decision.json"
    write_json(mason_path, mason_response)
    mason_hash = sha256_file(mason_path)
    broker.advance("MASON_PLAN", "MASON", payloads["MASON_PLAN"]["input_hashes"], mason_hash, model_transaction=False)
    events.append(factory_floor_event(4, "MASON_PLAN", "CANNED_COMPLETE", "Mason supplied a contract-valid contained implementation plan.", mason_hash))

    candidate = run_dir / "build" / "run-1" / "output"
    evidence = run_dir / "build" / "run-1" / "evidence"
    broker.candidate_path(candidate, candidate / "bundle.manifest.json")
    candidate.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment["X_FACTORY_NETWORK_DISABLED"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(root) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    build = subprocess.run(
        [sys.executable, "-m", "x_factory.bundle_generator", "generate", "--blueprint", str(blueprint_path), "--contracts", str(contracts), "--output", str(candidate), "--evidence", str(evidence), "--run-label", "RUN_1"],
        cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
    )
    if build.returncode != 0:
        raise RuntimeError(f"Deterministic build failed: {build.stderr[-2000:]}")
    actual_files = file_map(candidate)
    expected_files = file_map(expected_candidate)
    if sorted(actual_files) != REQUIRED_CANDIDATE_FILES or actual_files != expected_files:
        raise AssertionError("Rehearsal candidate is not byte-identical to controlled build 004")

    fixture_root = run_dir / "acceptance-fixture"
    environment["X_FACTORY_BLUEPRINT_PATH"] = str(blueprint_path)
    environment["X_FACTORY_CONTRACTS_DIR"] = str(contracts)
    environment["X_FACTORY_FIXTURE_ROOT"] = str(fixture_root)
    acceptance = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_bundle", "-v"],
        cwd=candidate, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )
    if acceptance.returncode != 0:
        raise RuntimeError(f"Candidate acceptance failed: {(acceptance.stdout + acceptance.stderr)[-2000:]}")
    build_record = {
        "schema_version": "0.1",
        "status": "CONTAINED_BUILD_COMPLETE",
        "provider_calls": 0,
        "network_attempts": 0,
        "external_actions": 0,
        "candidate_file_hashes": actual_files,
        "candidate_root_digest": load_json(candidate / "bundle.manifest.json")["root_digest"],
        "controlled_build_004_byte_identical": True,
        "acceptance_exit_code": acceptance.returncode,
    }
    build_record_path = run_dir / "build_record.json"
    write_json(build_record_path, build_record)
    build_hash = sha256_file(build_record_path)
    broker.advance("DETERMINISTIC_BUILD", "DETERMINISTIC_BUILDER", {"mason_plan": mason_hash, "blueprint": blueprint_hash}, build_hash)
    events.append(factory_floor_event(5, "DETERMINISTIC_BUILD", "COMPLETE", "The local builder reproduced and tested the frozen candidate byte for byte.", build_hash))

    vera_build_payload = make_stage_payload("VERA_BUILD_REVIEW", args.run_id, {"approved_blueprint": blueprint_summary, "candidate_manifest": {"root_digest": build_record["candidate_root_digest"], "file_count": 5}, "test_evidence": {"status": "PASS", "exit_code": 0}, "build_record": {"sha256": build_hash, "external_actions": 0}}, "build_verification_evaluation.v0.2")
    payloads["VERA_BUILD_REVIEW"] = vera_build_payload
    write_json(run_dir / "payloads" / "vera_build_review.json", vera_build_payload)
    vera_build_verdict = {
        "schema_version": "0.1-rehearsal",
        "verdict": "CONTAINED_DRAFT_READY",
        "candidate_root_digest": build_record["candidate_root_digest"],
        "byte_identical_to_controlled_build_004": True,
        "acceptance": "PASS",
        "authority": "REHEARSAL_ONLY_NO_INSTALL_DEPLOYMENT_OR_PRODUCTION_AUTHORITY",
    }
    vera_build_path = run_dir / "vera" / "build_verdict.json"
    write_json(vera_build_path, vera_build_verdict)
    vera_build_hash = sha256_file(vera_build_path)
    broker.advance("VERA_BUILD_REVIEW", "VERA", vera_build_payload["input_hashes"], vera_build_hash, model_transaction=False)
    events.append(factory_floor_event(6, "VERA_BUILD_REVIEW", "CANNED_COMPLETE", "Vera's canned gate confirmed the deterministic draft evidence.", vera_build_hash))

    final_summary = {"mission_id": args.run_id, "status": "LOCAL_REHEARSAL_DRAFT_READY", "provider_calls": 0, "model_calls": 0, "candidate_root_digest": build_record["candidate_root_digest"]}
    final_hash = digest(final_summary)
    broker.advance("DRAFT_READY", "BROKER", {"vera_build_verdict": vera_build_hash}, final_hash)
    events.append(factory_floor_event(7, "DRAFT_READY", "COMPLETE", "The fully local synthetic rehearsal reached draft ready.", final_hash))

    mission_record = broker.record()
    mission_schema = load_json(root / "contracts" / "phase4" / "factory_mission_record.v0.1.schema.json")
    errors = list(Draft202012Validator(mission_schema).iter_errors(mission_record))
    if errors:
        raise AssertionError("Mission record failed schema: " + "; ".join(error.message for error in errors))
    write_json(run_dir / "factory_mission_record.v0.1.json", mission_record)
    write_json(run_dir / "rehearsal_summary.json", final_summary)
    (run_dir / "factory_floor.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8", newline="\n")
    (run_dir / "acceptance.stdout.txt").write_text(acceptance.stdout, encoding="utf-8", newline="\n")
    (run_dir / "acceptance.stderr.txt").write_text(acceptance.stderr, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "LOCAL_REHEARSAL_DRAFT_READY", "run_dir": str(run_dir), "provider_calls": 0, "model_calls": 0, "candidate_root_digest": build_record["candidate_root_digest"], "mission_record_sha256": sha256_file(run_dir / "factory_mission_record.v0.1.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
