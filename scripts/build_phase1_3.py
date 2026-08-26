#!/usr/bin/env python3
"""Controlled local builder for the frozen Phase 1.3 specification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CREDENTIAL_KEYS = (
    "ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY",
    "OPENAI_API_KEY", "OPENROUTER_API_KEY",
)
CONTRACT_HASHES = {
    "output_bundle_manifest": "737ce9dc75f49a0a463f6fc50495caa73703812b3b635ec9fcb6d2451b56f20d",
    "deterministic_generation": "1f72d796d40b0310e81775b6588c598a37d3c93386ed805d4c4ff02e8fe7f62c",
    "acceptance_fixture": "34537cda455215b9f3e61e8d6c0bed0d9cd017b6ac05b386c24a5fca7ac67d49",
}
BLUEPRINT_HASH = "3d2302ae05794d06d6a527a43fcf1515cc3e2a87f094afa2398d84c0c07e908a"
EVALUATION_HASH = "f80c28f2465a22cb26524ec46136f8692cd871ced0636e06ebd4acaee8cef78f"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--build-id", default="controlled-build-001")
    args = parser.parse_args()
    root = args.factory_root.resolve()
    blueprint = root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json"
    evaluation = root / "runs" / "contained" / "contained-real-card-proof-004" / "vera" / "evaluation.v0.1.json"
    contracts = root / "contracts" / "phase1_3"
    if digest(blueprint) != BLUEPRINT_HASH or digest(evaluation) != EVALUATION_HASH:
        raise PermissionError("Frozen blueprint or Vera evaluation hash mismatch")
    evaluation_json = load(evaluation)
    if evaluation_json.get("verdict") != "SPECIFICATION_READY_FOR_BUILD" or evaluation_json.get("defects") != [] or any(value != "PASS" for value in evaluation_json.get("gates", {}).values()):
        raise PermissionError("Vera did not provide an all-pass build-ready verdict")
    contract_paths = {
        "output_bundle_manifest": contracts / "output_bundle_manifest.v0.3.json",
        "deterministic_generation": contracts / "deterministic_generation.v0.3.json",
        "acceptance_fixture": contracts / "acceptance_fixture.v0.3.json",
    }
    for name, path in contract_paths.items():
        if digest(path) != CONTRACT_HASHES[name]:
            raise PermissionError(f"Approved contract hash mismatch: {name}")

    build_root = root / "builds" / "controlled" / args.build_id
    if build_root.exists():
        raise FileExistsError(f"Build root already exists: {build_root}")
    seed_output = build_root / "seed" / "run-1" / "output"
    seed_evidence = build_root / "seed" / "run-1" / "evidence"
    seed_output.mkdir(parents=True)
    seed_evidence.mkdir(parents=True)
    fixture_root = build_root / "fixture"
    logs = build_root / "logs"
    logs.mkdir(parents=True)

    runtime_env = os.environ.copy()
    for key in CREDENTIAL_KEYS:
        runtime_env.pop(key, None)
    runtime_env["X_FACTORY_NETWORK_DISABLED"] = "1"
    runtime_env["X_FACTORY_BLUEPRINT_PATH"] = str(blueprint)
    runtime_env["X_FACTORY_CONTRACTS_DIR"] = str(contracts)
    runtime_env["X_FACTORY_FIXTURE_ROOT"] = str(fixture_root)
    runtime_env["PYTHONDONTWRITEBYTECODE"] = "1"
    runtime_env["PYTHONPATH"] = str(root) + (os.pathsep + runtime_env["PYTHONPATH"] if runtime_env.get("PYTHONPATH") else "")
    seed_command = [
        "python", "-m", "x_factory.bundle_generator", "generate",
        "--blueprint", str(blueprint), "--contracts", str(contracts),
        "--output", str(seed_output), "--evidence", str(seed_evidence), "--run-label", "RUN_1",
    ]
    seed = subprocess.run(seed_command, cwd=root, env=runtime_env, capture_output=True, text=True, timeout=120, check=False)
    (logs / "seed.stdout.txt").write_text(seed.stdout, encoding="utf-8")
    (logs / "seed.stderr.txt").write_text(seed.stderr, encoding="utf-8")
    if seed.returncode != 0:
        raise RuntimeError(f"Seed generation failed with exit code {seed.returncode}")

    test_command = ["python", "-m", "unittest", "tests.test_bundle", "-v"]
    tests = subprocess.run(test_command, cwd=seed_output, env=runtime_env, capture_output=True, text=True, timeout=300, check=False)
    (logs / "acceptance.stdout.txt").write_text(tests.stdout, encoding="utf-8")
    (logs / "acceptance.stderr.txt").write_text(tests.stderr, encoding="utf-8")
    if tests.returncode != 0:
        raise RuntimeError(f"Acceptance suite failed with exit code {tests.returncode}: {tests.stderr[-2000:]}")
    seed_paths = sorted(path.relative_to(seed_output).as_posix() for path in seed_output.rglob("*") if path.is_file())
    expected_seed_paths = ["agent/AGENT.md", "agent/agent.spec.json", "bundle.manifest.json", "tests/fixtures/smoke.input.json", "tests/test_bundle.py"]
    if seed_paths != expected_seed_paths:
        raise RuntimeError(f"Seed bundle gained undeclared files during testing: {seed_paths}")

    test_results = load(fixture_root / "fixture-evidence" / "test-results.json")
    repeatability = load(fixture_root / "fixture-evidence" / "repeatability-report.json")
    if test_results.get("status") != "PASS" or test_results.get("exit_code") != 0:
        raise RuntimeError("Acceptance evidence is not PASS")
    if not all(item.get("status") == "PASS" for item in test_results.get("assertions", [])):
        raise RuntimeError("An acceptance assertion did not pass")
    evidence_files = sorted(path for path in fixture_root.rglob("*") if path.is_file())
    record = {
        "schema_version": "0.1",
        "build_id": args.build_id,
        "source": {
            "blueprint_sha256": "sha256:" + digest(blueprint),
            "vera_evaluation_sha256": "sha256:" + digest(evaluation),
            "vera_verdict": evaluation_json["verdict"],
            "contract_hashes": {name: "sha256:" + digest(path) for name, path in contract_paths.items()},
        },
        "implementation": {
            "module": "x_factory.bundle_generator", "acceptance_module": "x_factory.acceptance",
            "source_hashes": {
                "x_factory/bundle_generator.py": "sha256:" + digest(root / "x_factory" / "bundle_generator.py"),
                "x_factory/acceptance.py": "sha256:" + digest(root / "x_factory" / "acceptance.py"),
                "scripts/build_phase1_3.py": "sha256:" + digest(root / "scripts" / "build_phase1_3.py"),
            },
            "provider_calls": 0, "network_attempts": 0, "external_actions": 0
        },
        "seed": {
            "command": seed_command, "exit_code": seed.returncode,
            "output_files": {path.relative_to(seed_output).as_posix(): "sha256:" + digest(path) for path in sorted(seed_output.rglob("*")) if path.is_file()},
            "evidence_files": {path.relative_to(seed_evidence).as_posix(): "sha256:" + digest(path) for path in sorted(seed_evidence.rglob("*")) if path.is_file()},
        },
        "acceptance": {
            "command": "python -m unittest tests.test_bundle -v", "exit_code": tests.returncode,
            "status": test_results["status"], "assertions": test_results["assertions"],
            "root_digest": "sha256:" + repeatability["run_1_root_digest"],
            "evidence_files": {path.relative_to(fixture_root).as_posix(): "sha256:" + digest(path) for path in evidence_files},
        },
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "authority": {"install_to_live_factory_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    write_json(build_root / "controlled_build_record.v0.1.json", record)
    print(json.dumps({"status": "BUILD_AND_ACCEPTANCE_COMPLETE", "build_root": str(build_root), "record": record}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
