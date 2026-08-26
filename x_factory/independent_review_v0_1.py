"""Provider-free independent review gate between Vera certification and Porter."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import (
    CONTRACT_ROOT,
    INTERACTIVE_ROOT,
    ROOT,
    MissionControlError,
    canonical,
    load_json,
    sha256,
    write_new,
)


REVIEW_ROOT = ROOT / "reviews" / "independent-local"
REVIEW_SCHEMA = ROOT / "contracts" / "independent_local_review.v0.1.schema.json"
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
SECRET_LIKE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|password|secret|token)\s*=\s*[A-Za-z0-9_./+=-]{16,})",
    re.IGNORECASE,
)


class IndependentReviewError(MissionControlError):
    pass


def _record_digest(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _check(checks: list[dict[str, str]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})


def _run_generated_tests(mission_root: Path, fixture_root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["X_FACTORY_BLUEPRINT_PATH"] = str(mission_root / "artifacts/mason-generator-blueprint.v0.1.json")
    environment["X_FACTORY_CONTRACTS_DIR"] = str(CONTRACT_ROOT)
    environment["X_FACTORY_FIXTURE_ROOT"] = str(fixture_root)
    return subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(mission_root / "build/run-1/output/tests"), "-p", "test_*.py"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def review_path(mission_id: str, review_root: Path | None = None) -> Path:
    if not MISSION_ID.fullmatch(mission_id):
        raise IndependentReviewError("Invalid mission ID")
    return (review_root or REVIEW_ROOT) / mission_id / "independent-local-review.v0.1.json"


def find_independent_review(mission_id: str, review_root: Path | None = None) -> dict[str, Any] | None:
    path = review_path(mission_id, review_root)
    if not path.is_file():
        return None
    review = load_json(path)
    Draft202012Validator(load_json(REVIEW_SCHEMA)).validate(review)
    if _record_digest(review, "review_sha256") != review["review_sha256"]:
        raise IndependentReviewError("Independent review record hash validation failed")
    return review


def run_independent_review(mission_id: str, mission_root: Path | None = None, review_root: Path | None = None) -> dict[str, Any]:
    if not MISSION_ID.fullmatch(mission_id):
        raise IndependentReviewError("Invalid mission ID")
    mission_root = mission_root or (INTERACTIVE_ROOT / mission_id)
    active_review_root = review_root or REVIEW_ROOT
    record_path = mission_root / "mission-record.json"
    if not record_path.is_file():
        raise IndependentReviewError("Mission not found")
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes)
    existing = find_independent_review(mission_id, active_review_root)
    mission_sha = sha256(record_bytes)
    if existing:
        if existing["source"]["mission_record_sha256"] != mission_sha:
            raise IndependentReviewError("Mission changed after independent review")
        return existing

    final_root = active_review_root / mission_id
    staging = active_review_root / f".{mission_id}.staging-{secrets.token_hex(3)}"
    checks: list[dict[str, str]] = []
    try:
        staging.mkdir(parents=True)
        required = [
            "artifacts/atlas-normalized-intake.v0.1.json",
            "artifacts/aria-blueprint.v0.2.json",
            "artifacts/vera-spec-review.v0.1.json",
            "build/run-1/output/bundle.manifest.json",
            "certification/vera-final.v0.1.json",
            "governance/hermes-semantic-review-packet.v0.1.json",
        ]
        missing = [relative for relative in required if not (mission_root / relative).is_file()]
        _check(checks, "REQUIRED_ARTIFACTS", not missing, "All required Factory handoff artifacts are present" if not missing else f"Missing: {', '.join(missing)}")

        specialists = record.get("specialists") or []
        build_route = [item.get("specialist") for item in specialists[:7]]
        expected_build_route = ["Atlas", "Aria", "Vera", "Mason", "Knowledge Forge", "Troy", "Vera"]
        _check(checks, "FACTORY_ROUTE", len(specialists) >= 7 and build_route == expected_build_route and all(item.get("status") == "PASS" for item in specialists), "The certified build and Prompt Forge route passed before the independent review and packaging gates")
        certification = load_json(mission_root / "certification/vera-final.v0.1.json") if not missing else {}
        _check(checks, "VERA_CERTIFICATION", certification.get("verdict") == "LOCAL_CANDIDATE_CERTIFIED", "Vera certified the deterministic local candidate")
        _check(checks, "BUILD_REPEATABILITY", record.get("build", {}).get("repeatable") is True and record.get("build", {}).get("unit_tests") == "PASS", "Two Mason outputs matched and generated tests passed")
        _check(checks, "AUTHORITY_BOUNDARY", record.get("authority") == {"deployment_authorized": False, "production_approved": False}, "Deployment and production authority remain absent")
        _check(checks, "PROVIDER_BOUNDARY", record.get("provider", {}).get("calls") == 0, "The Factory mission used zero provider calls")

        declared = record.get("artifacts") or {}
        undeclared_missing = [relative for relative in declared.values() if not (mission_root / relative).is_file()]
        _check(checks, "DECLARED_ARTIFACT_LEDGER", not undeclared_missing, f"All {len(declared)} declared artifacts resolve inside the mission")

        serialized = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in mission_root.rglob("*")
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        _check(checks, "CREDENTIAL_CONTENT_GUARD", not SECRET_LIKE.search(serialized), "No credential-like content was found in the mission artifacts")

        test_result = _run_generated_tests(mission_root, staging / "acceptance-fixture")
        _check(checks, "INDEPENDENT_TEST_RERUN", test_result.returncode == 0, "Independent generated-test rerun passed" if test_result.returncode == 0 else (test_result.stderr or test_result.stdout or "Generated tests failed")[:500])
        verdict = "READY_FOR_PORTER_PACKAGING" if all(item["status"] == "PASS" for item in checks) else "REVISION_REQUIRED"
        review = {
            "schema_version": "0.1",
            "review_id": f"local-review-{sha256(canonical({'mission_id': mission_id, 'mission_sha': mission_sha}))[:16]}",
            "mission_id": mission_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": {"name": "Rook", "mode": "INDEPENDENT_PROVIDER_FREE_REVIEW", "independent_from": ["Atlas", "Aria", "Troy", "Vera", "Mason", "Porter"], "provider_calls": 0},
            "source": {"mission_record_sha256": mission_sha, "build_root_digest": record["build"]["root_digest"]},
            "verdict": verdict,
            "checks": checks,
            "hermes_review": {
                "status": "PREPARED_NOT_INVOKED",
                "command": "/review verify every requirement was completed and look for anything that could break",
                "packet": "governance/hermes-semantic-review-packet.v0.1.json",
                "provider_calls": 0,
            },
            "authority": {"provider_transport": False, "tools": False, "deployment": False, "production": False},
        }
        review["review_sha256"] = _record_digest(review, "review_sha256")
        Draft202012Validator(load_json(REVIEW_SCHEMA)).validate(review)
        write_new(staging / "independent-local-review.v0.1.json", review)
        if verdict != "READY_FOR_PORTER_PACKAGING":
            raise IndependentReviewError("Independent review found a required revision")
        staging.replace(final_root)
        return review
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
