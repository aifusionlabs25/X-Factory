"""Owner-reviewed Hunter lead inbox and one-way, hash-bound Factory handoff."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from x_factory import hunter_draft_v0_1 as hunter_draft
from x_factory.hunter_draft_v0_1 import MAX_OBSERVATION_AGE_DAYS, REVIEW_ROOT
from x_factory.mission_control_factory_v0_1 import ROOT

INBOX_ROOT = ROOT / "drafts/hunter-inbox"
INCOMING_ROOT = ROOT / "drafts/hunter/incoming"
REFRESH_REQUEST_ROOT = ROOT / "drafts/hunter-refresh/requests"
HANDOFF_SCHEMA = ROOT / "contracts/hunter_factory_lead_handoff.v0.1.schema.json"


class HunterInboxError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _read_receipts() -> list[tuple[dict[str, Any], Path]]:
    """Read only receipts bound to the supported, independently pinned source.

    A refresh result's own hash or OWNER_REVIEWED label cannot establish an
    owner decision. Incoming files remain research until a reviewed-source
    registration flow exists; they must never become accepted receipts here.
    """
    records = []
    try:
        run = hunter_draft.source_run()
    except hunter_draft.HunterDraftError as error:
        raise HunterInboxError(str(error)) from error
    prospects = {item["prospect_id"]: item for item in run["qualified_prospects"]}
    review_schema = json.loads((ROOT / "contracts/hunter_draft_review.v0.1.schema.json").read_text(encoding="utf-8"))
    for path in REVIEW_ROOT.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        if record.get("schema_version") != "hunter.owner-reviewed-draft.v0.1" or record.get("status") != "OWNER_REVIEWED_DRAFT_ONLY":
            continue
        expected = record.get("record_sha256")
        actual = _digest({k: v for k, v in record.items() if k != "record_sha256"})
        if not expected or expected != actual:
            continue
        snapshot = record.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        prospect_id = snapshot.get("prospect_id")
        if not isinstance(prospect_id, str) or prospect_id not in prospects:
            continue
        expected_snapshot = {
            "source_id": hunter_draft.SOURCE_ID,
            "source_run_sha256": hunter_draft.SOURCE_SHA256,
            "prospect_id": prospect_id,
            "research_status": "UNAPPROVED_RESEARCH",
            "original_prospect": prospects[prospect_id],
        }
        if (snapshot != expected_snapshot or record.get("snapshot_sha256") != _digest(expected_snapshot)
                or path.name != hunter_draft.receipt_path(prospect_id).name
                or record.get("chassis_id") != hunter_draft.CHASSIS_ID
                or any(record.get(key) is not False for key in ("knowledge_approved", "mission_created", "outreach_performed"))
                or type(record.get("provider_calls")) is not int or record["provider_calls"] != 0):
            continue
        check = {"source_id": snapshot["source_id"], "prospect_id": prospect_id,
                 "snapshot_sha256": record["snapshot_sha256"], "chassis_sha256": record.get("chassis_sha256"),
                 "fields": record.get("fields"), "owner_confirmed": True}
        if list(Draft202012Validator(review_schema).iter_errors(check)):
            continue
        records.append((record, path))
    return records


def _handoff_path(prospect_id: str) -> Path:
    return INBOX_ROOT / f"{prospect_id}.json"


def _needs_reverification(prospect: dict[str, Any]) -> bool:
    """Report stale research without treating an inbox handoff as fresh evidence."""
    audit = prospect.get("browser_audit", {})
    observed = [item.get("observed_on", "") for item in prospect.get("public_sources", [])]
    observed.append(audit.get("checked_on", ""))
    today = date.today()
    try:
        return any((today - date.fromisoformat(stamp)).days < 0 or
                   (today - date.fromisoformat(stamp)).days > MAX_OBSERVATION_AGE_DAYS
                   for stamp in observed)
    except (TypeError, ValueError):
        return True


def _load_handoff(path: Path) -> dict[str, Any]:
    try:
        handoff = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HunterInboxError("A saved Factory handoff is unreadable.") from error
    try:
        Draft202012Validator(json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))).validate(handoff)
    except ValidationError as error:
        raise HunterInboxError("A saved Factory handoff no longer matches its contract.") from error
    if handoff.get("handoff_sha256") != _digest({k: v for k, v in handoff.items() if k != "handoff_sha256"}):
        raise HunterInboxError("A saved Factory handoff failed its integrity check.")
    return handoff


def _bound_handoff(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    handoff = _load_handoff(path)
    snapshot = record["snapshot"]
    if (handoff["source"]["draft_receipt_sha256"] != record["record_sha256"]
            or handoff["source"]["source_id"] != snapshot["source_id"]
            or handoff["source"]["source_run_sha256"] != snapshot["source_run_sha256"]
            or handoff["prospect"]["prospect_id"] != snapshot["prospect_id"]
            or handoff["factory_intake"]["fields"] != record["fields"]
            or handoff["factory_intake"]["chassis_id"] != record["chassis_id"]
            or handoff["factory_intake"]["chassis_sha256"] != record["chassis_sha256"]):
        raise HunterInboxError("The handoff does not match its reviewed Hunter draft. Nothing was replaced.")
    return handoff


def list_inbox() -> dict[str, Any]:
    leads = []
    for record, path in _read_receipts():
        prospect = record["snapshot"]["original_prospect"]
        prospect_id = prospect["prospect_id"]
        handoff_path = _handoff_path(prospect_id)
        handoff = _bound_handoff(handoff_path, record) if handoff_path.is_file() else None
        stale = _needs_reverification(prospect)
        blockers = hunter_draft.blockers(prospect)
        leads.append({
            "prospect_id": prospect_id,
            "company_name": record["fields"]["client_name"],
            "website": prospect.get("website", ""),
            "wedge": prospect.get("gtm_wedge", ""),
            "score": prospect.get("overall_score", 0),
            "score_band": prospect.get("overall_band", ""),
            "reviewed_at": record.get("reviewed_at", ""),
            "status": "NEEDS_FRESH_RESEARCH" if stale else "REVIEW_BLOCKED" if blockers else "HANDOFF_READY" if handoff else "READY_TO_SEND",
            "blockers": blockers,
            "handoff_id": handoff.get("handoff_id") if handoff else None,
            "reverification_required": stale,
            "source_id": record["snapshot"]["source_id"],
            "source_receipt": path.name,
        })
    leads.sort(key=lambda item: item["reviewed_at"], reverse=True)
    from x_factory import prepared_agent_v0_1 as preparation
    for lead in leads:
        matches=[]
        for origin_path in preparation.PROJECT_ROOT.glob('project-*/hunter-origin.json'):
            origin=preparation.read(origin_path)
            if origin.get('prospect_id')==lead['prospect_id']:
                project=preparation.get_project(origin_path.parent.name)
                matches.append(project)
        if matches:
            project=max(matches,key=lambda p:p['updated_at'])
            lead['preparation']={k:project[k] for k in ('project_id','status','message','updated_at')}
    return {"schema_version": "hunter.factory-lead-inbox.v0.1", "leads": leads,
            "owner_action_required": True, "refresh_return_mode": "MANUAL_REVIEW_REQUIRED"}


def send_to_factory(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != {"prospect_id"} or not isinstance(request["prospect_id"], str):
        raise HunterInboxError("Choose one reviewed Hunter lead; no other fields are accepted.")
    matches = [(record, path) for record, path in _read_receipts() if record["snapshot"].get("prospect_id") == request["prospect_id"]]
    if len(matches) != 1:
        raise HunterInboxError("That lead is not an owner-reviewed Hunter draft.")
    record, path = matches[0]
    prospect = record["snapshot"]["original_prospect"]
    brief = prospect["factory_intake_brief"]
    handoff_path = _handoff_path(request["prospect_id"])
    if handoff_path.is_file():
        return {"handoff": _bound_handoff(handoff_path, record), "reused": True}
    fields = record["fields"]
    handoff = {
        "schema_version": "hunter.factory-lead-handoff.v0.1",
        "handoff_id": "lh-" + _digest({"source": record["snapshot"], "draft": fields})[:16],
        "status": "READY_FOR_FACTORY_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_id": record["snapshot"]["source_id"],
            "source_run_sha256": record["snapshot"]["source_run_sha256"],
            "draft_receipt_sha256": record["record_sha256"],
            "research_status": record["snapshot"]["research_status"],
            "evidence_urls": [item["url"] for item in prospect.get("public_sources", [])],
        },
        "prospect": {
            "prospect_id": prospect["prospect_id"],
            "company_name": prospect["company_name"],
            "website": prospect["website"],
            "vertical": prospect.get("vertical", ""),
            "location": prospect.get("location", ""),
            "wedge": prospect.get("gtm_wedge", ""),
            "score": prospect.get("overall_score", 0),
            "score_band": prospect.get("overall_band", ""),
        },
        "factory_intake": {
            "fields": fields,
            "chassis_id": record["chassis_id"],
            "chassis_sha256": record["chassis_sha256"],
            "proposed_job": brief.get("agent_job", prospect.get("proposed_x_agent", "")),
            "boundaries": brief.get("additional_boundaries", []),
        },
        "guardrails": {
            "knowledge_approved": False,
            "mission_created": False,
            "provider_calls": 0,
            "outreach_performed": False,
            "owner_action_required": True,
        },
    }
    handoff["handoff_sha256"] = _digest(handoff)
    Draft202012Validator(json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))).validate(handoff)
    INBOX_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with handoff_path.open("x", encoding="utf-8") as handle:
            json.dump(handoff, handle, ensure_ascii=False, indent=2)
    except FileExistsError:
        return {"handoff": _bound_handoff(handoff_path, record), "reused": True}
    return {"handoff": handoff, "reused": False}


def use_handoff(request: dict[str, Any]) -> dict[str, Any]:
    """Load a fresh, validated handoff into the normal Factory form."""
    if not isinstance(request, dict) or set(request) != {"prospect_id"} or not isinstance(request["prospect_id"], str):
        raise HunterInboxError("Choose one Factory handoff; no other fields are accepted.")
    matches = [(record, path) for record, path in _read_receipts() if record["snapshot"].get("prospect_id") == request["prospect_id"]]
    if len(matches) != 1:
        raise HunterInboxError("That lead does not have one validated Hunter result.")
    record, _ = matches[0]
    handoff_path = _handoff_path(request["prospect_id"])
    if not handoff_path.is_file():
        raise HunterInboxError("Send this reviewed lead to the Factory before using it.")
    _bound_handoff(handoff_path, record)
    try:
        return hunter_draft.reopen_draft({"source_id": record["snapshot"]["source_id"],
                                         "prospect_id": request["prospect_id"]})
    except hunter_draft.HunterDraftError as error:
        raise HunterInboxError(str(error)) from error
