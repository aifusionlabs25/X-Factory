#!/usr/bin/env python3
"""Validate and, only with --activate, execute one exact Owner Control request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.mission_control_factory_v0_1 import canonical, load_json  # noqa: E402
from x_factory.owner_control_v0_1 import (  # noqa: E402
    CONTROL_ROOT,
    OFFICIAL_REPOS_ROOT,
    governed_run_request_status,
    governed_run_status,
    latest_semantic_result,
    promotion_status,
    repo_promotion_request_status,
)


REVIEW_RUNNER = ROOT / "scripts" / "interactive_hermes_review_v0_1.py"


def digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def verify_bound_object(value: dict[str, Any], hash_key: str) -> None:
    expected = value[hash_key]
    payload = {key: item for key, item in value.items() if key != hash_key}
    if digest(payload) != expected:
        raise PermissionError(f"{hash_key} validation failed")


def file_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.relative_to(root).as_posix() != "repo-record.json"
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical(value))


def load_bound(kind: str, mission_id: str, request_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if kind == "governed-review":
        plan = governed_run_status(mission_id)
        request = governed_run_request_status(mission_id)
    else:
        plan = promotion_status(mission_id)
        request = repo_promotion_request_status(mission_id)
    if not plan or not request:
        raise PermissionError("Both a prepared plan and an owner request are required")
    verify_bound_object(plan, "plan_sha256")
    verify_bound_object(request, "request_sha256")
    if request["request_sha256"] != request_sha256:
        raise PermissionError("Owner request hash mismatch")
    if request["plan_sha256"] != plan["plan_sha256"]:
        raise PermissionError("Owner request is not bound to the active plan")
    if request["status"] != "OWNER_REQUESTED_AWAITING_GUARDED_EXECUTOR":
        raise PermissionError("Owner request is not executable")
    return plan, request


def preflight(kind: str, mission_id: str, plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    result = {
        "schema_version": "0.1",
        "status": "PREFLIGHT_PASS_INACTIVE",
        "kind": kind,
        "mission_id": mission_id,
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": request["request_sha256"],
        "provider_calls": 0,
        "external_writes": 0,
        "activation_required": True,
    }
    if kind == "governed-review":
        previous = latest_semantic_result(mission_id)
        result["previous_semantic_result"] = previous["status"] if previous else None
        result["would_block_duplicate_pass"] = bool(previous and previous.get("status") == "HERMES_SEMANTIC_REVIEW_PASS")
    else:
        target = Path(plan["target"]["path"])
        target.resolve(strict=False).relative_to(OFFICIAL_REPOS_ROOT.resolve(strict=False))
        result["target"] = str(target)
        result["target_exists"] = target.exists()
        result["would_block_existing_target"] = target.exists()
    return result


def execute_review(mission_id: str, plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    previous = latest_semantic_result(mission_id)
    if previous and previous.get("status") == "HERMES_SEMANTIC_REVIEW_PASS":
        raise PermissionError("A passing semantic review already exists; duplicate provider calls are blocked")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [sys.executable, "-B", str(REVIEW_RUNNER), "--mission-id", mission_id],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=1000,
        check=False,
    )
    if process.returncode:
        raise RuntimeError("Hermes semantic review failed terminally; inspect the sealed review evidence")
    summary = json.loads(process.stdout)
    execution = {
        "schema_version": "0.1",
        "kind": "governed-review",
        "status": summary["status"],
        "mission_id": mission_id,
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": request["request_sha256"],
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "result": summary,
    }
    execution["execution_sha256"] = digest(execution)
    write_new(CONTROL_ROOT / mission_id / "governed-review-execution.v0.1.json", execution)
    return execution


def execute_promotion(mission_id: str, plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    source = Path(plan["source"]["path"]).resolve(strict=True)
    target = Path(plan["target"]["path"]).resolve(strict=False)
    official_root = OFFICIAL_REPOS_ROOT.resolve(strict=True)
    target.relative_to(official_root)
    if target.exists():
        raise PermissionError("Official target exists; overwrite is prohibited")
    repo_record = load_json(source / "repo-record.json")
    source_files = file_map(source)
    if source_files != repo_record["files"] or digest(source_files) != repo_record["root_digest"]:
        raise PermissionError("Source repo hashes drifted after Porter certification")
    staging = target.with_name(f".{target.name}.x-factory-staging-{secrets.token_hex(3)}")
    if staging.exists():
        raise PermissionError("Generated staging path already exists")
    try:
        shutil.copytree(source, staging)
        if (staging / ".env").exists():
            raise PermissionError("Populated .env appeared in promotion staging")
        if file_map(staging) != source_files:
            raise PermissionError("Promotion copy hash mismatch")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        tests = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            cwd=staging,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if tests.returncode:
            raise RuntimeError("Promoted repo tests failed in staging")
        staging.replace(target)
        execution = {
            "schema_version": "0.1",
            "kind": "repo-promotion",
            "status": "OFFICIAL_LOCAL_REPO_CREATED",
            "mission_id": mission_id,
            "plan_sha256": plan["plan_sha256"],
            "request_sha256": request["request_sha256"],
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "source_root_digest": repo_record["root_digest"],
            "target": str(target),
            "verified_files": len(source_files) + 1,
            "tests": "PASS",
            "credentials_copied": False,
            "existing_repo_mutation": False,
            "x_link_installation": False,
            "deployment": False,
            "production": False,
        }
        execution["execution_sha256"] = digest(execution)
        write_new(CONTROL_ROOT / mission_id / "repo-promotion-execution.v0.1.json", execution)
        return execution
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("governed-review", "repo-promotion"), required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    plan, request = load_bound(args.kind, args.mission_id, args.request_sha256)
    if not args.activate:
        print(json.dumps(preflight(args.kind, args.mission_id, plan, request), indent=2))
        return 0
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required")
    result = execute_review(args.mission_id, plan, request) if args.kind == "governed-review" else execute_promotion(args.mission_id, plan, request)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
