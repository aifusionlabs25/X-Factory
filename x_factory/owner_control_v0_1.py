"""Owner-facing inactive control packets for Hermes review and repo promotion."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x_factory.chassis_depot_v0_1 import derive_public_role
from x_factory.mission_control_factory_v0_1 import INTERACTIVE_ROOT, MissionControlError, ROOT, canonical, load_json
from x_factory.repo_foundry_v0_1 import find_local_repo


CONTROL_ROOT = ROOT / "control" / "owner-gates"
OFFICIAL_REPOS_ROOT = Path(r"C:\AI Fusion Labs\X AGENTS\REPOS")
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")


class OwnerControlError(MissionControlError):
    pass


def _digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical(value))


def _mission(mission_id: str) -> tuple[Path, dict[str, Any]]:
    if not MISSION_ID.fullmatch(mission_id):
        raise OwnerControlError("Invalid mission ID")
    root = INTERACTIVE_ROOT / mission_id
    record_path = root / "mission-record.json"
    if not record_path.is_file():
        raise OwnerControlError("Mission not found")
    return root, load_json(record_path)


def _safe_repo_name(display_name: str) -> str:
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", display_name).strip(" .")
    name = re.sub(r"\s+", " ", name)
    if not name or name in {".", ".."}:
        raise OwnerControlError("Agent name cannot form a safe repository directory")
    return name[:80]


def governed_run_status(mission_id: str) -> dict[str, Any] | None:
    if not MISSION_ID.fullmatch(mission_id):
        return None
    root = CONTROL_ROOT / mission_id
    for name in ("governed-run-plan.v0.2.json", "governed-run-plan.v0.1.json"):
        path = root / name
        if path.is_file():
            return load_json(path)
    return None


def prepare_governed_run(mission_id: str) -> dict[str, Any]:
    v2_path = CONTROL_ROOT / mission_id / "governed-run-plan.v0.2.json"
    if v2_path.is_file():
        return load_json(v2_path)
    mission_root, record = _mission(mission_id)
    artifacts = {
        "owner_brief": load_json(mission_root / record["artifacts"]["owner_brief"]),
        "blueprint": load_json(mission_root / record["artifacts"]["blueprint"]),
        "x_link_candidate": load_json(mission_root / record["artifacts"]["x_link_package"]),
    }
    body = {
        "schema_version": "0.2",
        "mission_id": mission_id,
        "status": "PREPARED_INACTIVE",
        "purpose": "One contained Atlas to Aria to Vera semantic review of this immutable local candidate.",
        "provider": "openai-codex",
        "model": "gpt-5.6-luna",
        "reasoning": "low",
        "stages": [
            {"sequence": 1, "profile": "atlas", "role": "Intent and boundary review"},
            {"sequence": 2, "profile": "aria", "role": "Architecture and completeness review"},
            {"sequence": 3, "profile": "vera", "role": "Independent semantic certification"},
        ],
        "ceilings": {"model_calls": 3, "retries": 0, "tools": 0, "oauth_refreshes": 0},
        "inputs": {name: {"sha256": _digest(value)} for name, value in artifacts.items()},
        "writes": {"factory_review_evidence_only": True, "candidate_mutation": False, "other_profile_writes": False},
        "prohibited": ["tools or MCP", "memory or delegation", "authentication mutation", "candidate rebuilding", "ANAM action", "X-Link installation", "deployment", "release", "production"],
        "owner_summary": "Three Luna review calls. Atlas checks intent, Aria checks architecture, and Vera certifies the specification. No tools, retries, credential changes, builds, installs, or deployment.",
        "activation": {"owner_request_available": True, "execution_available": False, "reason": "Mission Control can record the owner's exact request; a separate guarded executor must validate and consume it."},
    }
    body["plan_sha256"] = _digest(body)
    _write_new(v2_path, body)
    return body


def promotion_status(mission_id: str) -> dict[str, Any] | None:
    if not MISSION_ID.fullmatch(mission_id):
        return None
    root = CONTROL_ROOT / mission_id
    for name in ("repo-promotion-plan.v0.2.json", "repo-promotion-plan.v0.1.json"):
        path = root / name
        if path.is_file():
            return load_json(path)
    return None


def prepare_repo_promotion(mission_id: str) -> dict[str, Any]:
    v2_path = CONTROL_ROOT / mission_id / "repo-promotion-plan.v0.2.json"
    if v2_path.is_file():
        return load_json(v2_path)
    _, mission_record = _mission(mission_id)
    repo = find_local_repo(mission_id)
    if not repo:
        raise OwnerControlError("Porter must create and verify the local repository before preparing its official handoff")
    runtime_state = mission_record.get("runtime_foundry", {})
    if runtime_state.get("behavior_status") != "RUNTIME_BEHAVIOR_VERIFIED":
        raise OwnerControlError("Preview testing is not complete. Verify the named runtime behavior before creating an official repository")
    source = ROOT / repo["relative_path"]
    agent = mission_record["agent"]
    chassis = agent.get("derived_from_chassis") or {}
    public_role = agent.get("public_role_title") or derive_public_role(
        agent.get("purpose", ""),
        chassis.get("chassis_role_title") or chassis.get("role_title") or "Concierge",
    )
    public_name = (
        f"{agent['agent_name']} — {public_role}"
        if agent.get("derived_from_chassis") and public_role
        else agent["agent_name"] if agent.get("derived_from_chassis") else agent["display_name"]
    )
    target = OFFICIAL_REPOS_ROOT / _safe_repo_name(public_name)
    try:
        target.resolve(strict=False).relative_to(OFFICIAL_REPOS_ROOT.resolve(strict=False))
    except ValueError as error:
        raise OwnerControlError("Official repository target escaped its fixed root") from error
    target_exists = target.exists()
    body = {
        "schema_version": "0.2",
        "mission_id": mission_id,
        "repo_id": repo["repo_id"],
        "status": "BLOCKED_TARGET_EXISTS" if target_exists else "PREPARED_INACTIVE",
        "source": {"path": str(source), "root_digest": repo["root_digest"], "files": len(repo["files"]) + 1},
        "target": {"root": str(OFFICIAL_REPOS_ROOT), "path": str(target), "exists": target_exists},
        "copy_policy": {"new_directory_only": True, "atomic_sibling_staging": True, "overwrite": False, "credentials": False, "populated_env_files": False},
        "post_copy_checks": ["all source hashes match", "repo tests pass from destination", "no populated .env exists", "source and target manifests agree"],
        "prohibited": ["existing repo mutation", "credential copying", "dependency installation", "X-Link registry promotion", "provider calls", "deployment", "release", "production"],
        "owner_summary": "Copy this sealed repo into the official X-Agent repos root as a brand-new directory, verify every hash and test, and stop before installation or deployment.",
        "activation": {"owner_request_available": True, "execution_available": False, "reason": "Mission Control can record the owner's exact request; a separate guarded executor must validate and consume it."},
    }
    body["plan_sha256"] = _digest(body)
    _write_new(v2_path, body)
    return body


def governed_run_request_status(mission_id: str) -> dict[str, Any] | None:
    path = CONTROL_ROOT / mission_id / "governed-review-request.v0.1.json"
    return load_json(path) if MISSION_ID.fullmatch(mission_id) and path.is_file() else None


def repo_promotion_request_status(mission_id: str) -> dict[str, Any] | None:
    path = CONTROL_ROOT / mission_id / "repo-promotion-request.v0.1.json"
    return load_json(path) if MISSION_ID.fullmatch(mission_id) and path.is_file() else None


def repo_promotion_execution_status(mission_id: str) -> dict[str, Any] | None:
    path = CONTROL_ROOT / mission_id / "repo-promotion-execution.v0.1.json"
    return load_json(path) if MISSION_ID.fullmatch(mission_id) and path.is_file() else None


def _request(mission_id: str, kind: str, plan: dict[str, Any], filename: str) -> dict[str, Any]:
    if plan.get("status") != "PREPARED_INACTIVE":
        raise OwnerControlError("The plan is not eligible for an owner execution request")
    path = CONTROL_ROOT / mission_id / filename
    if path.is_file():
        existing = load_json(path)
        if existing.get("plan_sha256") != plan.get("plan_sha256"):
            raise OwnerControlError("Existing owner request is bound to a different plan")
        return existing
    body = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "request_kind": kind,
        "status": "OWNER_REQUESTED_AWAITING_GUARDED_EXECUTOR",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "request_source": "MISSION_CONTROL_OWNER_ACTION",
        "plan_sha256": plan["plan_sha256"],
        "owner_acknowledgement": plan["owner_summary"],
        "automatic_execution": False,
        "provider_calls_at_request_time": 0,
        "external_writes_at_request_time": 0,
    }
    body["request_sha256"] = _digest(body)
    _write_new(path, body)
    return body


def request_governed_run(mission_id: str) -> dict[str, Any]:
    previous = latest_semantic_result(mission_id)
    if previous and previous.get("status") == "HERMES_SEMANTIC_REVIEW_PASS":
        raise OwnerControlError("This exact mission already has a passing Hermes semantic review; duplicate provider work is blocked")
    plan = prepare_governed_run(mission_id)
    return _request(mission_id, "HERMES_SEMANTIC_REVIEW", plan, "governed-review-request.v0.1.json")


def request_repo_promotion(mission_id: str) -> dict[str, Any]:
    plan = prepare_repo_promotion(mission_id)
    return _request(mission_id, "OFFICIAL_REPO_HANDOFF", plan, "repo-promotion-request.v0.1.json")


def latest_semantic_result(mission_id: str) -> dict[str, Any] | None:
    review_root = ROOT / "reviews" / mission_id
    if not review_root.is_dir():
        return None
    summaries = sorted(review_root.glob("*/semantic-review-summary.json"), key=lambda item: item.parent.name, reverse=True)
    return load_json(summaries[0]) if summaries else None


def owner_control_status(mission_id: str) -> dict[str, Any]:
    _mission(mission_id)
    return {
        "mission_id": mission_id,
        "governed_run": governed_run_status(mission_id),
        "governed_run_request": governed_run_request_status(mission_id),
        "semantic_result": latest_semantic_result(mission_id),
        "repo_promotion": promotion_status(mission_id),
        "repo_promotion_request": repo_promotion_request_status(mission_id),
        "repo_promotion_execution": repo_promotion_execution_status(mission_id),
    }
