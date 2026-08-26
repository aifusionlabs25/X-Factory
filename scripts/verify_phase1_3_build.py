#!/usr/bin/env python3
"""Independent read-back and negative-path verification of a controlled build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


FIVE_PATHS = ["agent/AGENT.md", "agent/agent.spec.json", "bundle.manifest.json", "tests/fixtures/smoke.input.json", "tests/test_bundle.py"]
FOUR_PATHS = ["agent/AGENT.md", "agent/agent.spec.json", "tests/fixtures/smoke.input.json", "tests/test_bundle.py"]
CREDENTIAL_KEYS = ["ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path_or_bytes: Path | bytes) -> str:
    data = path_or_bytes.read_bytes() if isinstance(path_or_bytes, Path) else path_or_bytes
    return hashlib.sha256(data).hexdigest()


def files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def root_digest(output_files: dict[str, bytes]) -> str:
    records = [path.encode() + b"\0" + digest(output_files[path]).encode() + b"\n" for path in FOUR_PATHS]
    return digest(b"".join(records))


def sanitized_env(factory_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in CREDENTIAL_KEYS:
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(factory_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def generator_command(root: Path, contracts: Path, output: Path, evidence: Path) -> list[str]:
    return ["python", "-m", "x_factory.bundle_generator", "generate", "--blueprint", str(root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json"), "--contracts", str(contracts), "--output", str(output), "--evidence", str(evidence), "--run-label", "RUN_1"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    root = args.factory_root.resolve()
    build = root / "builds" / "controlled" / args.build_id
    record_path = build / "controlled_build_record.v0.1.json"
    record = load(record_path)
    seed_root = build / "seed" / "run-1" / "output"
    seed_evidence_root = build / "seed" / "run-1" / "evidence"
    fixture_root = build / "fixture"
    seed_files = files(seed_root)
    run_1_files = files(fixture_root / "run-1" / "output")
    run_2_files = files(fixture_root / "run-2" / "output")
    expected_evidence_paths = {
        "run-1/evidence/execution-audit.json", "run-1/evidence/file-hashes.json",
        "run-2/evidence/execution-audit.json", "run-2/evidence/file-hashes.json",
        "fixture-evidence/repeatability-report.json", "fixture-evidence/test-results.json",
    }
    actual_evidence_paths = {path.relative_to(fixture_root).as_posix() for path in fixture_root.rglob("*") if path.is_file() and "/output/" not in "/" + path.relative_to(fixture_root).as_posix()}
    checks: dict[str, bool] = {
        "record_build_id": record.get("build_id") == args.build_id,
        "source_blueprint_bound": record["source"]["blueprint_sha256"] == "sha256:" + digest(root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json"),
        "vera_evaluation_bound": record["source"]["vera_evaluation_sha256"] == "sha256:" + digest(root / "runs" / "contained" / "contained-real-card-proof-004" / "vera" / "evaluation.v0.1.json") and record["source"]["vera_verdict"] == "SPECIFICATION_READY_FOR_BUILD",
        "implementation_sources_bound": all(record["implementation"]["source_hashes"].get(relative) == "sha256:" + digest(root / relative) for relative in ("x_factory/bundle_generator.py", "x_factory/acceptance.py", "scripts/build_phase1_3.py")),
        "seed_exact_five_paths": sorted(seed_files) == FIVE_PATHS,
        "fixture_run_1_exact_five_paths": sorted(run_1_files) == FIVE_PATHS,
        "fixture_run_2_exact_five_paths": sorted(run_2_files) == FIVE_PATHS,
        "two_runs_byte_identical": run_1_files == run_2_files,
        "seed_matches_fixture": seed_files == run_1_files,
        "evidence_path_set_exact": actual_evidence_paths == expected_evidence_paths,
        "root_digest_bound": record["acceptance"]["root_digest"] == "sha256:" + root_digest(run_1_files),
        "authority_remains_false": record["authority"] == {"install_to_live_factory_authorized": False, "deployment_authorized": False, "production_approved": False},
        "zero_external_activity_recorded": record["implementation"]["provider_calls"] == record["implementation"]["network_attempts"] == record["implementation"]["external_actions"] == 0,
    }
    for prefix, output_files, evidence_dir in (("seed", seed_files, seed_evidence_root), ("run_1", run_1_files, fixture_root / "run-1" / "evidence"), ("run_2", run_2_files, fixture_root / "run-2" / "evidence")):
        hashes = load(evidence_dir / "file-hashes.json")
        expected = [{"path": path, "sha256": digest(output_files[path])} for path in FIVE_PATHS]
        checks[f"{prefix}_file_hashes_match"] = hashes["files"] == expected
        checks[f"{prefix}_manifest_self_hash_matches"] = hashes["manifest_self_hash"] == digest(output_files["bundle.manifest.json"])
        checks[f"{prefix}_root_digest_matches"] = hashes["root_digest"] == root_digest(output_files)
        audit = load(evidence_dir / "execution-audit.json")
        checks[f"{prefix}_audit_clean"] = audit["credential_keys_present"] == [] and audit["network_attempt_count"] == audit["external_action_count"] == 0 and audit["output_paths"] == FIVE_PATHS
    results = load(fixture_root / "fixture-evidence" / "test-results.json")
    checks["all_six_assertions_pass"] = results["status"] == "PASS" and results["exit_code"] == 0 and [item["id"] for item in results["assertions"]] == [f"ASSERT-{index:03d}" for index in range(1, 7)] and all(item["status"] == "PASS" for item in results["assertions"])

    temp = root / "verification" / f"{args.build_id}-attempt-{args.attempt}"
    if temp.exists():
        raise FileExistsError(f"Verification evidence root already exists: {temp}")
    temp.mkdir(parents=True)
    temp.resolve().relative_to(root.resolve())
    env = sanitized_env(root)
    rerun_env = env.copy()
    rerun_env["X_FACTORY_BLUEPRINT_PATH"] = str(root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json")
    rerun_env["X_FACTORY_CONTRACTS_DIR"] = str(root / "contracts" / "phase1_3")
    rerun_env["X_FACTORY_FIXTURE_ROOT"] = str(temp / "independent-rerun-fixture")
    rerun = subprocess.run(["python", "-m", "unittest", "tests.test_bundle", "-v"], cwd=seed_root, env=rerun_env, capture_output=True, text=True, timeout=300, check=False)
    checks["independent_acceptance_rerun_passes"] = rerun.returncode == 0 and "OK" in (rerun.stdout + rerun.stderr)

    negative: dict[str, bool] = {}
    if True:
        contracts = root / "contracts" / "phase1_3"
        for case, configure in (("credential_rejected", "credential"), ("network_marker_required", "network"), ("nonempty_output_rejected", "nonempty")):
            case_root = temp / case / "run-1"
            output, evidence = case_root / "output", case_root / "evidence"
            output.mkdir(parents=True)
            evidence.mkdir()
            case_env = env.copy()
            if configure != "network":
                case_env["X_FACTORY_NETWORK_DISABLED"] = "1"
            if configure == "credential":
                case_env["OPENAI_API_KEY"] = "synthetic-rejection-canary"
            if configure == "nonempty":
                (output / "unexpected.txt").write_text("synthetic", encoding="utf-8")
            completed = subprocess.run(generator_command(root, contracts, output, evidence), cwd=root, env=case_env, capture_output=True, text=True, timeout=120, check=False)
            negative[case] = completed.returncode == 3 and not any(evidence.iterdir())
        tampered_contracts = temp / "tampered-contracts"
        tampered_contracts.mkdir()
        for filename in ("output_bundle_manifest.v0.3.json", "deterministic_generation.v0.3.json", "acceptance_fixture.v0.3.json"):
            data = (contracts / filename).read_bytes()
            (tampered_contracts / filename).write_bytes(data + (b" " if filename.startswith("output") else b""))
        output, evidence = temp / "tampered" / "run-1" / "output", temp / "tampered" / "run-1" / "evidence"
        output.mkdir(parents=True)
        evidence.mkdir()
        tamper_env = env.copy()
        tamper_env["X_FACTORY_NETWORK_DISABLED"] = "1"
        tampered = subprocess.run(generator_command(root, tampered_contracts, output, evidence), cwd=root, env=tamper_env, capture_output=True, text=True, timeout=120, check=False)
        negative["tampered_contract_rejected"] = tampered.returncode == 2 and not any(output.iterdir()) and not any(evidence.iterdir())
    guard_env = env.copy()
    guard_env["X_FACTORY_NETWORK_DISABLED"] = "1"
    guard = subprocess.run(["python", "-c", "from x_factory.bundle_generator import _install_runtime_guard; _install_runtime_guard(); import socket; socket.socket()"], cwd=root, env=guard_env, capture_output=True, text=True, timeout=30, check=False)
    negative["network_runtime_guard_blocks_socket"] = guard.returncode != 0 and "Blocked runtime action" in guard.stderr

    report = {
        "schema_version": "0.1", "verification": "CONTROLLED_BUILD_INDEPENDENT_READBACK",
        "build_id": args.build_id, "build_record_sha256": "sha256:" + digest(record_path),
        "checks": checks, "negative_tests": negative,
        "status": "PASS" if all(checks.values()) and all(negative.values()) else "FAIL",
        "authority": {"install_to_live_factory_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    report_path = temp / "verification-report.v0.1.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
