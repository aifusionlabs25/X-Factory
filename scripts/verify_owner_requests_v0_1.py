#!/usr/bin/env python3
"""Isolated proof for owner requests and guarded executor preflight."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import owner_control_v0_1 as owner  # noqa: E402


UNCERTIFIED_MISSION = "draft-desert-home-services-concierge-20260822-031720-aa0017"
CERTIFIED_MISSION = "draft-operational-qa-concierge-20260821-064103-a3e197"


def load_executor():
    path = ROOT / "scripts" / "execute_owner_control_request_v0_1.py"
    spec = importlib.util.spec_from_file_location("owner_executor_test", path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load guarded executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    original_control_root = owner.CONTROL_ROOT
    executor = load_executor()
    isolated = ROOT / "verification" / "owner-request-test-sandbox"
    owner.CONTROL_ROOT = isolated
    try:
        review_plan = owner.prepare_governed_run(UNCERTIFIED_MISSION)
        review_request = owner.request_governed_run(UNCERTIFIED_MISSION)
        assert owner.request_governed_run(UNCERTIFIED_MISSION) == review_request
        executor.verify_bound_object(review_plan, "plan_sha256")
        executor.verify_bound_object(review_request, "request_sha256")
        review_preflight = executor.preflight("governed-review", UNCERTIFIED_MISSION, review_plan, review_request)
        assert review_preflight["status"] == "PREFLIGHT_PASS_INACTIVE"
        assert review_preflight["provider_calls"] == 0
        assert not review_preflight["would_block_duplicate_pass"]

        duplicate_blocked = False
        try:
            owner.request_governed_run(CERTIFIED_MISSION)
        except owner.OwnerControlError:
            duplicate_blocked = True
        assert duplicate_blocked

        promotion_plan = owner.prepare_repo_promotion(CERTIFIED_MISSION)
        promotion_request = owner.request_repo_promotion(CERTIFIED_MISSION)
        assert owner.request_repo_promotion(CERTIFIED_MISSION) == promotion_request
        executor.verify_bound_object(promotion_plan, "plan_sha256")
        executor.verify_bound_object(promotion_request, "request_sha256")
        promotion_preflight = executor.preflight("repo-promotion", CERTIFIED_MISSION, promotion_plan, promotion_request)
        assert promotion_preflight["status"] == "PREFLIGHT_PASS_INACTIVE"
        assert promotion_preflight["external_writes"] == 0

        tampered = dict(promotion_request)
        tampered["plan_sha256"] = "0" * 64
        tamper_blocked = False
        try:
            executor.verify_bound_object(tampered, "request_sha256")
        except PermissionError:
            tamper_blocked = True
        assert tamper_blocked

        result = {
            "schema_version": "0.1",
            "status": "PASS",
            "checks": {
                "review_request_idempotent": True,
                "duplicate_passing_review_blocked": True,
                "promotion_request_idempotent": True,
                "plan_and_request_hashes_verified": True,
                "tampered_request_blocked": True,
                "executor_preflight_inactive": True,
            },
            "provider_calls": 0,
            "official_repo_writes": 0,
            "review_preflight": review_preflight,
            "promotion_preflight": promotion_preflight,
        }
        print(json.dumps(result, indent=2))
    finally:
        owner.CONTROL_ROOT = original_control_root
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
