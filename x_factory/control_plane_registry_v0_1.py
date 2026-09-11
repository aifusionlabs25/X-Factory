"""Read-only registry projection for Factory project/package/preview links."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, sha256, slugify


SCHEMA_PATH = ROOT / "contracts" / "control_plane" / "registry-snapshot.v1.schema.json"
PREPARED_ROOT = ROOT / "drafts" / "prepared-agents"
INTERACTIVE_ROOT = ROOT / "runs" / "interactive"


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _artifact(candidate_root: Path, relative: str) -> tuple[dict[str, str], bool]:
    path = (candidate_root / relative).resolve()
    try:
        path.relative_to(candidate_root.resolve())
    except ValueError:
        return {"path": relative.replace("\\", "/"), "sha256": "0" * 64}, False
    if not path.is_file():
        return {"path": relative.replace("\\", "/"), "sha256": "0" * 64}, False
    return {"path": relative.replace("\\", "/"), "sha256": sha256(path.read_bytes())}, True


def _latest_revision(project_path: Path) -> tuple[dict[str, Any], bool]:
    versions = sorted((project_path / "revisions").glob("*.json"))
    if not versions:
        raise ValueError("Prepared project has no revisions")
    value = json.loads(versions[-1].read_text(encoding="utf-8"))
    expected = value.get("revision_sha256")
    actual = sha256(canonical({k: v for k, v in value.items() if k != "revision_sha256"}))
    return value, expected == actual


def _revision_digest(value: dict[str, Any]) -> str:
    return sha256(canonical({k: v for k, v in value.items() if k != "revision_sha256"}))


def _release_files(candidate_root: Path) -> tuple[list[dict[str, Any]], bool]:
    records: list[dict[str, Any]] = []
    integrity = True
    for path in sorted((candidate_root / "input" / "control-plane").glob("release-record.*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            artifact, exists = _artifact(candidate_root, path.relative_to(candidate_root).as_posix())
            if not exists or value.get("kind") != "release_record":
                integrity = False
                continue
            records.append({"path": artifact["path"], "sha256": artifact["sha256"],
                            "status": value.get("status"), "environment": value.get("environment")})
        except (OSError, ValueError, json.JSONDecodeError):
            integrity = False
    return records, integrity


def registry_snapshot(*, prepared_root: Path = PREPARED_ROOT, interactive_root: Path = INTERACTIVE_ROOT) -> dict[str, Any]:
    """Build a validated, read-only projection from existing immutable files."""
    entries: list[dict[str, Any]] = []
    for project_path in sorted(prepared_root.glob("project-*")):
        try:
            value, revision_ok = _latest_revision(project_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        project_id = str(value.get("project_id") or project_path.name)
        mission_id = value.get("mission_id")
        candidate_root = interactive_root / mission_id if isinstance(mission_id, str) and mission_id else None
        draft_ref = accepted_ref = None
        agent_id = instance_id = None
        lane = "PREPARATION"
        integrity = revision_ok
        release_records: list[dict[str, Any]] = []
        if value.get("status") == "APPROVED":
            lane = "APPROVED_NOT_BUILT"
        if candidate_root and candidate_root.is_dir():
            draft_path = candidate_root / "input/control-plane/accepted-package-draft.v1.json"
            accepted_path = candidate_root / "input/control-plane/accepted-package.v1.json"
            for package_path, target in ((draft_path, "draft"), (accepted_path, "accepted")):
                if package_path.is_file():
                    try:
                        package = json.loads(package_path.read_text(encoding="utf-8"))
                        ref, exists = _artifact(candidate_root, package_path.relative_to(candidate_root).as_posix())
                        if not exists or package.get("kind") not in {"accepted_package_draft", "accepted_package"}:
                            integrity = False
                        else:
                            if target == "draft":
                                draft_ref = ref
                            else:
                                accepted_ref = ref
                            agent_id = agent_id or package.get("agent_id")
                            instance_id = instance_id or package.get("instance_id")
                    except (OSError, ValueError, json.JSONDecodeError):
                        integrity = False
            release_records, release_ok = _release_files(candidate_root)
            integrity = integrity and release_ok
            if any(r["status"] == "verified" for r in release_records):
                lane = "PREVIEW_VERIFIED"
            elif any(r["status"] == "prepared" for r in release_records):
                lane = "PREVIEW_PREPARED"
            elif accepted_ref:
                lane = "ACCEPTED_PACKAGE"
            elif draft_ref:
                lane = "PACKAGE_DRAFT"
            elif value.get("status") == "BUILT":
                lane = "BUILT_CANDIDATE"
        if not agent_id:
            agent_id = slugify(str((value.get("fields") or {}).get("x_agent_name") or ""), "x-agent") if value.get("fields") else None
        entries.append({"project_id": project_id, "status": value.get("status", "UNKNOWN"),
                        "mission_id": mission_id, "agent_id": agent_id, "instance_id": instance_id,
                        "current_lane": lane, "revision": int(value.get("revision", 1)),
                        "revision_sha256": value.get("revision_sha256") if isinstance(value.get("revision_sha256"), str) else _revision_digest(value),
                        "package": {"draft": draft_ref, "accepted": accepted_ref},
                        "release_records": release_records, "integrity": "PASS" if integrity else "REVIEW_REQUIRED"})
    snapshot = {"schema_version": "1.0.0", "kind": "factory_registry_snapshot",
                "generated_at": datetime.now(timezone.utc).isoformat(), "entries": entries}
    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(snapshot)
    return snapshot
