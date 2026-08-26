"""One-call local completion route: independent review, then Porter packaging."""

from __future__ import annotations

import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.independent_review_v0_1 import IndependentReviewError, find_independent_review, run_independent_review
from x_factory.mission_control_factory_v0_1 import ROOT, MissionControlError, canonical, load_json, sha256, write_new
from x_factory.repo_foundry_v0_1 import RepoFoundryError, create_local_repo, find_local_repo


COMPLETION_ROOT = ROOT / "runs" / "completions"
COMPLETION_SCHEMA = ROOT / "contracts" / "completion_record.v0.1.schema.json"
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")


class CompletionPipelineError(MissionControlError):
    pass


def _digest(value: dict[str, Any]) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != "completion_sha256"}))


def completion_path(mission_id: str) -> Path:
    if not MISSION_ID.fullmatch(mission_id):
        raise CompletionPipelineError("Invalid mission ID")
    return COMPLETION_ROOT / mission_id / "completion-record.v0.1.json"


def find_completion(mission_id: str) -> dict[str, Any] | None:
    path = completion_path(mission_id)
    if not path.is_file():
        return None
    record = load_json(path)
    Draft202012Validator(load_json(COMPLETION_SCHEMA)).validate(record)
    if _digest(record) != record["completion_sha256"]:
        raise CompletionPipelineError("Completion record hash validation failed")
    return record


def complete_local_draft(mission_id: str) -> dict[str, Any]:
    if not MISSION_ID.fullmatch(mission_id):
        raise CompletionPipelineError("Invalid mission ID")
    existing = find_completion(mission_id)
    if existing:
        return existing
    try:
        review = run_independent_review(mission_id)
        if review["verdict"] != "READY_FOR_PORTER_PACKAGING":
            raise CompletionPipelineError("Independent review did not release the candidate to Porter")
        repo = create_local_repo(mission_id)
    except (IndependentReviewError, RepoFoundryError) as error:
        raise CompletionPipelineError(str(error)) from error
    if repo.get("status") != "LOCAL_REPO_READY" or repo.get("verification", {}).get("status") != "PASS":
        raise CompletionPipelineError("Porter repository verification did not pass")

    completion_id = f"completion-{sha256(canonical({'mission_id': mission_id, 'review': review['review_sha256'], 'repo': repo['root_digest']}))[:16]}"
    record = {
        "schema_version": "0.1",
        "completion_id": completion_id,
        "mission_id": mission_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "LOCAL_DRAFT_COMPLETE",
        "route": [
            {"order": 1, "specialist": "Atlas", "job": "Normalize the owner brief", "status": "PASS"},
            {"order": 2, "specialist": "Aria", "job": "Assemble the agent blueprint", "status": "PASS"},
            {"order": 3, "specialist": "Vera", "job": "Validate the build specification", "status": "PASS"},
            {"order": 4, "specialist": "Mason", "job": "Compile repeatable candidate bundles", "status": "PASS"},
            {"order": 5, "specialist": "Knowledge Studio", "job": "Bind owner-approved source knowledge", "status": "PASS"},
            {"order": 6, "specialist": "Troy", "job": "Compile the governed production System Prompt", "status": "PASS"},
            {"order": 7, "specialist": "Vera", "job": "Certify deterministic behavior and the Prompt Forge package", "status": "PASS"},
            {"order": 8, "specialist": "Runtime Foundry", "job": "Seal the local runtime candidate", "status": "PASS"},
            {"order": 9, "specialist": "Rook", "job": "Independently rerun tests and attack omissions", "status": "PASS"},
            {"order": 10, "specialist": "Porter", "job": "Package and verify the complete local repository", "status": "PASS"},
        ],
        "review": {
            "review_id": review["review_id"],
            "verdict": review["verdict"],
            "review_sha256": review["review_sha256"],
            "relative_path": f"reviews/independent-local/{mission_id}/independent-local-review.v0.1.json",
        },
        "repo": {
            "repo_id": repo["repo_id"],
            "status": repo["status"],
            "local_path": repo["local_path"],
            "preview_url": repo["preview_url"],
            "root_digest": repo["root_digest"],
            "tests": repo["verification"]["status"],
        },
        "authority": {"provider_calls": 0, "network_attempts": 0, "credentials_copied": False, "existing_repo_mutation": False, "deployment": False, "production": False},
    }
    record["completion_sha256"] = _digest(record)
    Draft202012Validator(load_json(COMPLETION_SCHEMA)).validate(record)
    final_root = COMPLETION_ROOT / mission_id
    staging = COMPLETION_ROOT / f".{mission_id}.staging-{secrets.token_hex(3)}"
    try:
        staging.mkdir(parents=True)
        write_new(staging / "completion-record.v0.1.json", record)
        staging.replace(final_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return record
