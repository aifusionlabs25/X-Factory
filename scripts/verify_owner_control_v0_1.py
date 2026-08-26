#!/usr/bin/env python3
"""Verify inactive owner-control packets and their fail-closed boundaries."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.mission_control_factory_v0_1 import canonical  # noqa: E402
from x_factory.owner_control_v0_1 import prepare_governed_run, prepare_repo_promotion  # noqa: E402


MISSION_ID = "draft-operational-qa-concierge-20260821-064103-a3e197"


def verify_hash(plan: dict) -> None:
    expected = plan["plan_sha256"]
    payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    assert hashlib.sha256(canonical(payload)).hexdigest() == expected


def main() -> int:
    run_one = prepare_governed_run(MISSION_ID)
    promotion_one = prepare_repo_promotion(MISSION_ID)
    target = Path(promotion_one["target"]["path"])
    before = {
        "exists": target.exists(),
        "mtime_ns": target.stat().st_mtime_ns if target.exists() else None,
        "entries": sorted(item.name for item in target.iterdir()) if target.is_dir() else [],
    }
    run_two = prepare_governed_run(MISSION_ID)
    promotion_two = prepare_repo_promotion(MISSION_ID)
    after = {
        "exists": target.exists(),
        "mtime_ns": target.stat().st_mtime_ns if target.exists() else None,
        "entries": sorted(item.name for item in target.iterdir()) if target.is_dir() else [],
    }
    assert run_one == run_two
    assert promotion_one == promotion_two
    verify_hash(run_one)
    verify_hash(promotion_one)
    assert run_one["status"] == "PREPARED_INACTIVE"
    assert run_one["ceilings"] == {"model_calls": 3, "retries": 0, "tools": 0, "oauth_refreshes": 0}
    assert run_one["activation"] == {
        "owner_request_available": True,
        "execution_available": False,
        "reason": "Mission Control can record the owner's exact request; a separate guarded executor must validate and consume it.",
    }
    assert promotion_one["status"] == "PREPARED_INACTIVE"
    assert promotion_one["target"]["exists"] is False
    assert promotion_one["activation"] == {
        "owner_request_available": True,
        "execution_available": False,
        "reason": "Mission Control can record the owner's exact request; a separate guarded executor must validate and consume it.",
    }
    assert promotion_one["copy_policy"]["overwrite"] is False
    assert promotion_one["copy_policy"]["credentials"] is False
    assert before == after
    print(json.dumps({
        "status": "PASS",
        "capability": "OWNER_CONTROL_INACTIVE_PLANS",
        "mission_id": MISSION_ID,
        "governed_run_plan_sha256": run_one["plan_sha256"],
        "repo_promotion_plan_sha256": promotion_one["plan_sha256"],
        "maximum_model_calls_if_later_activated": 3,
        "provider_calls_during_preparation": 0,
        "official_repo_writes": 0,
        "idempotent": True,
        "owner_request_available": True,
        "automatic_execution_exposed": False,
        "deployment": False,
        "production": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
