"""Factory-to-control-plane package bridge.

This module exports a pending accepted-package envelope from the exact local
candidate that Mission Control just built.  It is deliberately a bridge, not a
second project manager: prepared-agent revisions remain the authoritative
history and this record only points at their immutable candidate artifacts.

The bridge never accepts a package, calls a provider, installs a profile, or
creates a release.  It only creates and validates a draft envelope for the
next owner/evaluation gate.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, sha256, write_new, slugify


SCHEMA_ROOT = ROOT / "contracts" / "control_plane"
_SCHEMA_FILES = {
    "accepted_package_draft": "accepted-package-draft.schema.json",
    "accepted_package": "accepted-package.schema.json",
    "release_record": "release-record.schema.json",
    "production_promotion_plan": "production-promotion-plan.v1.schema.json",
}
_HEX = re.compile(r"^[a-f0-9]{64}$")


def _schema(kind: str) -> dict[str, Any]:
    try:
        filename = _SCHEMA_FILES[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown control-plane schema: {kind}") from exc
    return json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8"))


def validate_envelope(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    """Validate one adopted control-plane envelope with date-time checking."""
    Draft202012Validator(_schema(kind), format_checker=FormatChecker()).validate(value)
    return value


def _contained(candidate_root: Path, relative: str) -> Path:
    path = (candidate_root / relative).resolve()
    root = candidate_root.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"Control-plane artifact escapes the candidate: {relative}")
    if not path.is_file():
        raise ValueError(f"Control-plane artifact is missing: {relative}")
    return path


def _artifact(candidate_root: Path, relative: str) -> dict[str, str]:
    path = _contained(candidate_root, relative)
    return {"path": relative.replace("\\", "/"), "sha256": sha256(path.read_bytes())}


def _first_existing(candidate_root: Path, choices: list[str]) -> str:
    for relative in choices:
        if (candidate_root / relative).is_file():
            return relative
    raise ValueError("The candidate has no evaluation evidence artifact")


def _instance_id(candidate_root: Path, mission_id: str) -> str:
    blueprint = candidate_root / "runtime-foundry" / "profile-blueprint.v0.1.json"
    if blueprint.is_file():
        value = json.loads(blueprint.read_text(encoding="utf-8"))
        instance_id = value.get("instance_id")
        if isinstance(instance_id, str) and instance_id.strip():
            return instance_id
    return f"xi-{slugify(mission_id, 'candidate')[:40]}"


def _agent_id(project: dict[str, Any], candidate_root: Path) -> str:
    spec = candidate_root / "build" / "run-1" / "output" / "agent" / "agent.spec.json"
    if spec.is_file():
        value = json.loads(spec.read_text(encoding="utf-8"))
        candidate_id = value.get("candidate_id")
        if isinstance(candidate_id, str) and candidate_id.strip():
            return slugify(candidate_id)
    fields = project.get("fields") or {}
    return slugify(str(fields.get("x_agent_name") or project.get("project_id") or "x-agent"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    write_new(path, value)


def export_package_draft(project: dict[str, Any], candidate_root: Path, reference: dict[str, str]) -> dict[str, Any]:
    """Export and validate the pending package draft for one built candidate."""
    mission_id = str(project.get("mission_id") or "")
    project_id = str(project.get("project_id") or "")
    if not mission_id or not project_id:
        raise ValueError("A built candidate must have project and mission identities")

    prompt_rel = "instance/system-prompt/SYSTEM_PROMPT.md"
    knowledge_rel = "instance/knowledge/approved-knowledge.v0.1.json"
    tool_rel = "runtime-foundry/instance-runtime-contract.v0.1.json"
    runtime_rel = "input/text-runtime-candidate.v0.1.json"
    evidence_rel = _first_existing(candidate_root, [
        "runtime-foundry/local-behavior-certification.v0.1.json",
        "certification/vera-final.v0.1.json",
    ])

    artifacts = {
        "prompt": _artifact(candidate_root, prompt_rel),
        "knowledge_snapshot": _artifact(candidate_root, knowledge_rel),
        "tool_contract": _artifact(candidate_root, tool_rel),
        "runtime_settings": _artifact(candidate_root, runtime_rel),
        "evaluation_evidence": _artifact(candidate_root, evidence_rel),
        "candidate_binding": _artifact(candidate_root, "input/prepared-agent-binding.v0.1.json"),
    }
    manifest = {
        "schema_version": "1.0.0",
        "kind": "accepted_package_content_manifest",
        "project_id": project_id,
        "mission_id": mission_id,
        "source_revision_sha256": project.get("revision_sha256"),
        "approved_input_package_sha256": reference.get("package_sha256"),
        "artifacts": artifacts,
    }
    manifest_rel = "input/control-plane/accepted-package-content.v1.json"
    manifest_path = candidate_root / manifest_rel
    _write_json(manifest_path, manifest)

    package_id = f"apd-{_agent_id(project, candidate_root)}-{mission_id}"
    envelope = {
        "schema_version": "1.0.0",
        "kind": "accepted_package_draft",
        "package_id": package_id,
        "agent_id": _agent_id(project, candidate_root),
        "instance_id": _instance_id(candidate_root, mission_id),
        "package_version": "0.1.0",
        "content_manifest": _artifact(candidate_root, manifest_rel),
        "prompt": artifacts["prompt"],
        "knowledge_snapshot": artifacts["knowledge_snapshot"],
        "tool_contract": artifacts["tool_contract"],
        "runtime_settings": artifacts["runtime_settings"],
        "evaluation": {
            "evaluated_content_sha256": None,
            "verdict": "pending",
            "evidence": artifacts["evaluation_evidence"],
        },
        "accepted_by": None,
        "accepted_at": None,
    }
    validate_envelope("accepted_package_draft", envelope)
    envelope_rel = "input/control-plane/accepted-package-draft.v1.json"
    _write_json(candidate_root / envelope_rel, envelope)
    validate_package_draft(candidate_root / envelope_rel, candidate_root)
    return {
        "schema_version": envelope["schema_version"],
        "kind": envelope["kind"],
        "package_id": package_id,
        "path": envelope_rel,
        "sha256": sha256((candidate_root / envelope_rel).read_bytes()),
        "status": "PENDING_EVALUATION_AND_OWNER_ACCEPTANCE",
    }


def validate_package_draft(path: Path, candidate_root: Path | None = None) -> dict[str, Any]:
    """Validate the strict envelope and, when supplied, every referenced hash."""
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_envelope("accepted_package_draft", value)
    if candidate_root is None:
        return value
    root = candidate_root.resolve()
    refs = [value["content_manifest"], value["prompt"], value["knowledge_snapshot"],
            value["tool_contract"], value["runtime_settings"], value["evaluation"]["evidence"]]
    for ref in refs:
        artifact = _contained(root, ref["path"])
        actual = sha256(artifact.read_bytes())
        if actual != ref["sha256"] or not _HEX.fullmatch(actual):
            raise ValueError(f"Control-plane artifact hash mismatch: {ref['path']}")
    manifest_path = root / value["content_manifest"]["path"]
    if sha256(manifest_path.read_bytes()) != value["content_manifest"]["sha256"]:
        raise ValueError("Control-plane content manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("project_id"), str) or not manifest["project_id"]:
        raise ValueError("Control-plane content manifest is missing its source project")
    for name, ref in (manifest.get("artifacts") or {}).items():
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError(f"Invalid content-manifest artifact: {name}")
        artifact = _contained(root, ref["path"])
        if sha256(artifact.read_bytes()) != ref["sha256"]:
            raise ValueError(f"Content-manifest artifact hash mismatch: {ref['path']}")
    return value


def promote_package_draft(
    draft_path: Path,
    candidate_root: Path,
    *,
    evaluation: dict[str, Any],
    accepted_by: str,
    accepted_at: str,
) -> dict[str, str]:
    """Create an accepted-package envelope only after explicit gates pass.

    This function is intentionally inert until a caller supplies both a
    passing evaluation and an explicit owner acceptance.  It never performs
    provider, profile, deployment, or release actions.
    """
    draft = validate_package_draft(draft_path, candidate_root)
    if draft["kind"] != "accepted_package_draft" or draft["evaluation"]["verdict"] != "pending":
        raise ValueError("Only a pending accepted-package draft may be promoted")
    if accepted_by != "Rob":
        raise ValueError("Accepted packages require the named release authority")
    try:
        datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("accepted_at must be an ISO-8601 timestamp") from exc
    required = {"evaluated_content_sha256", "verdict", "evidence"}
    if set(evaluation) != required or evaluation["verdict"] != "pass":
        raise ValueError("A passing evaluation with evidence is required")
    if evaluation["evaluated_content_sha256"] != draft["content_manifest"]["sha256"]:
        raise ValueError("Evaluation is not bound to this exact content manifest")
    evidence = evaluation["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}:
        raise ValueError("Evaluation evidence must be a path and SHA-256")
    evidence_path = _contained(candidate_root, evidence["path"])
    if sha256(evidence_path.read_bytes()) != evidence["sha256"]:
        raise ValueError("Evaluation evidence hash does not match the candidate")
    accepted = {**draft, "kind": "accepted_package", "evaluation": evaluation,
                "accepted_by": accepted_by, "accepted_at": accepted_at}
    validate_envelope("accepted_package", accepted)
    accepted_rel = "input/control-plane/accepted-package.v1.json"
    accepted_path = candidate_root / accepted_rel
    _write_json(accepted_path, accepted)
    return {"package_id": accepted["package_id"], "path": accepted_rel,
            "sha256": sha256(accepted_path.read_bytes()), "status": "ACCEPTED"}


def prepare_preview_release_record(
    accepted_path: Path,
    candidate_root: Path,
    *,
    release_id: str,
    recorded_at: str,
    url: str,
    application_repository: str,
    application_commit_sha: str,
    anam_intended_config: str,
    dependencies: str,
    rollback_procedure: str,
) -> dict[str, str]:
    """Prepare a local preview release record for an accepted package.

    The record is deliberately ``prepared`` with verification pending. It is
    a contained handoff artifact, not a deployment or ANAM action.
    """
    accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
    validate_envelope("accepted_package", accepted)
    root = candidate_root.resolve()
    accepted_rel = accepted_path.resolve().relative_to(root).as_posix()
    accepted_ref = {"path": accepted_rel, "sha256": sha256(accepted_path.read_bytes())}
    intended_ref = _artifact(candidate_root, anam_intended_config)
    dependencies_ref = _artifact(candidate_root, dependencies)
    rollback_ref = _artifact(candidate_root, rollback_procedure)
    record = {
        "schema_version": "1.0.0",
        "kind": "release_record",
        "release_id": release_id,
        "agent_id": accepted["agent_id"],
        "instance_id": accepted["instance_id"],
        "environment": "preview",
        "status": "prepared",
        "recorded_at": recorded_at,
        "accepted_package": {"package_id": accepted["package_id"], "manifest": accepted_ref},
        "anam": {"mode": "session_config", "persona_id": None,
                 "intended_config": intended_ref, "observed_config": None, "observed_at": None},
        "application": {"repository": application_repository, "commit_sha": application_commit_sha,
                        "deployment_id": None},
        "url": url,
        "dependencies": dependencies_ref,
        "verification": {"status": "pending", "verified_at": None, "evidence": None},
        "production_approval": None,
        "rollback": {"target_record_id": None, "procedure": rollback_ref, "test_evidence": None},
    }
    validate_envelope("release_record", record)
    release_rel = "input/control-plane/release-record.preview.v1.json"
    release_path = candidate_root / release_rel
    _write_json(release_path, record)
    return {"release_id": release_id, "path": release_rel,
            "sha256": sha256(release_path.read_bytes()), "status": "PREVIEW_PREPARED"}


def verify_preview_release_record(
    prepared_path: Path,
    candidate_root: Path,
    *,
    observed_config: str,
    observed_at: str,
    verified_at: str,
    verification_evidence: str,
    rollback_test_evidence: str,
    deployment_id: str,
) -> dict[str, str]:
    """Record a verified contained preview without changing the prepared record."""
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    validate_envelope("release_record", prepared)
    if prepared["environment"] != "preview" or prepared["status"] != "prepared":
        raise ValueError("Only a prepared preview record may be verified")
    observed_ref = _artifact(candidate_root, observed_config)
    verification_ref = _artifact(candidate_root, verification_evidence)
    rollback_test_ref = _artifact(candidate_root, rollback_test_evidence)
    verified = {**prepared, "status": "verified",
                "anam": {**prepared["anam"], "observed_config": observed_ref, "observed_at": observed_at},
                "application": {**prepared["application"], "deployment_id": deployment_id},
                "verification": {"status": "passed", "verified_at": verified_at, "evidence": verification_ref},
                "rollback": {**prepared["rollback"], "test_evidence": rollback_test_ref}}
    validate_envelope("release_record", verified)
    verified_rel = "input/control-plane/release-record.preview.verified.v1.json"
    verified_path = candidate_root / verified_rel
    _write_json(verified_path, verified)
    return {"release_id": verified["release_id"], "path": verified_rel,
            "sha256": sha256(verified_path.read_bytes()), "status": "PREVIEW_VERIFIED"}


def prepare_production_promotion_plan(
    verified_path: Path,
    candidate_root: Path,
    *,
    plan_id: str,
    production_url: str,
    production_repository: str,
    production_commit_sha: str,
    approval_receipt: str,
    approved_at: str,
    rollback_procedure: str,
) -> dict[str, str]:
    """Prepare a locked production-promotion plan; never execute it."""
    verified = json.loads(verified_path.read_text(encoding="utf-8"))
    validate_envelope("release_record", verified)
    if verified["environment"] != "preview" or verified["status"] != "verified":
        raise ValueError("Production promotion requires a verified preview record")
    if verified["verification"]["status"] != "passed" or not verified["rollback"].get("test_evidence"):
        raise ValueError("Production promotion requires verification and rollback evidence")
    for ref in (
        verified["accepted_package"]["manifest"],
        verified["anam"]["intended_config"],
        verified["anam"]["observed_config"],
        verified["dependencies"],
        verified["verification"]["evidence"],
        verified["rollback"]["procedure"],
        verified["rollback"]["test_evidence"],
    ):
        path = _contained(candidate_root, ref["path"])
        if sha256(path.read_bytes()) != ref["sha256"]:
            raise ValueError(f"Verified preview artifact hash mismatch: {ref['path']}")
    source_ref = _artifact(candidate_root, verified_path.resolve().relative_to(candidate_root.resolve()).as_posix())
    approval_ref = _artifact(candidate_root, approval_receipt)
    rollback_ref = _artifact(candidate_root, rollback_procedure)
    plan = {
        "schema_version": "1.0.0", "kind": "production_promotion_plan", "plan_id": plan_id,
        "status": "READY_FOR_EXPLICIT_EXECUTION", "source_release": source_ref,
        "target": {"environment": "production", "url": production_url,
                    "repository": production_repository, "commit_sha": production_commit_sha},
        "approval": {"approved_by": "Rob", "approved_at": approved_at, "receipt": approval_ref},
        "rollback": {"target_record_id": verified["release_id"], "procedure": rollback_ref},
        "execution": {"authorized": False, "provider_actions": 0},
    }
    validate_envelope("production_promotion_plan", plan)
    plan_rel = "input/control-plane/production-promotion-plan.v1.json"
    plan_path = candidate_root / plan_rel
    _write_json(plan_path, plan)
    return {"plan_id": plan_id, "path": plan_rel,
            "sha256": sha256(plan_path.read_bytes()), "status": plan["status"]}


def preflight_production_promotion(plan_path: Path, candidate_root: Path, *, execution_authorized: bool = False) -> dict[str, str]:
    """Validate the locked plan and report the explicit-execution gate."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_envelope("production_promotion_plan", plan)
    for name in ("source_release", "approval.receipt", "rollback.procedure"):
        ref = plan["approval"]["receipt"] if name == "approval.receipt" else plan["rollback"]["procedure"] if name == "rollback.procedure" else plan["source_release"]
        path = _contained(candidate_root, ref["path"])
        if sha256(path.read_bytes()) != ref["sha256"]:
            raise ValueError(f"Promotion plan artifact hash mismatch: {ref['path']}")
    if execution_authorized:
        raise ValueError("External production execution is not enabled in the local Factory")
    return {"plan_id": plan["plan_id"], "status": "BLOCKED_EXPLICIT_EXECUTION_REQUIRED", "provider_actions": "0"}
