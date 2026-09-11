"""Prepare a bounded, owner-reviewed Hunter re-verification request."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from x_factory.hunter_inbox_v0_1 import _digest, _read_receipts
from x_factory.mission_control_factory_v0_1 import ROOT

REQUEST_ROOT = ROOT / "drafts/hunter-refresh/requests"
REQUEST_SCHEMA = ROOT / "contracts/hunter_refresh_request.v0.1.schema.json"


class HunterRefreshError(ValueError):
    pass


def _path(prospect_id: str):
    return REQUEST_ROOT / f"{prospect_id}.json"


def _request_for(record: dict[str, Any]) -> dict[str, Any]:
    prospect = record["snapshot"]["original_prospect"]
    urls = [item["url"] for item in prospect.get("public_sources", [])][:6]
    prompt = (
        f"Run one fresh, read-only public-source verification for {prospect['company_name']} ({prospect['website']}). "
        "Recheck the cited company pages, report the observation date and rendered-page status, "
        "preserve unknowns, and return one owner-reviewable prospect draft only. Do not contact the company, "
        "submit forms, approve Knowledge Bank facts, create a Factory mission, build an agent, or perform outreach. "
        "This request is prepared for manual execution in Hunter. Return the source evidence for owner review; "
        "automatic import of refresh results is not connected. A new reviewed source binding is required before Factory use."
    )
    request = {
        "schema_version": "hunter.factory-refresh-request.v0.1",
        "refresh_id": "hr-" + _digest({"source": record["snapshot"], "receipt": record["record_sha256"]})[:16],
        "status": "READY_FOR_HUNTER",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_id": record["snapshot"]["source_id"],
            "source_run_sha256": record["snapshot"]["source_run_sha256"],
            "draft_receipt_sha256": record["record_sha256"],
        },
        "prospect": {
            "prospect_id": prospect["prospect_id"],
            "company_name": prospect["company_name"],
            "website": prospect["website"],
            "location": prospect.get("location", ""),
            "requested_urls": urls,
        },
        "instructions": {"prompt": prompt, "scope": "ONE_PROSPECT_PUBLIC_SOURCE_REVERIFICATION"},
        "return_contract": {"dropbox": "drafts/hunter/incoming", "required_status": "OWNER_REVIEWED_DRAFT_ONLY", "owner_review_required": True},
        "guardrails": {"knowledge_approved": False, "mission_created": False, "provider_calls": 0, "outreach_performed": False},
    }
    request["request_sha256"] = _digest(request)
    Draft202012Validator(json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))).validate(request)
    return request


def _load_existing(target, expected: dict[str, Any]) -> dict[str, Any]:
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
        Draft202012Validator(json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))).validate(existing)
    except (OSError, ValueError, ValidationError) as error:
        raise HunterRefreshError("The saved refresh request is unreadable or invalid; nothing was replaced.") from error
    if (existing.get("request_sha256") != _digest({k: v for k, v in existing.items() if k != "request_sha256"})
            or existing["source"] != expected["source"] or existing["prospect"] != expected["prospect"]
            or existing["refresh_id"] != expected["refresh_id"]):
        raise HunterRefreshError("The saved refresh request does not match this reviewed draft; nothing was replaced.")
    return existing


def _response(request: dict[str, Any], *, reused: bool) -> dict[str, Any]:
    # Existing request records are immutable, including older wording. Explain
    # the current connection state outside the hash-bound saved packet.
    return {"refresh_request": request, "reused": reused,
            "execution_mode": "MANUAL_HUNTER_REQUEST",
            "automatic_return_supported": False,
            "next_step": "Run this request in Hunter, then review its evidence. A new reviewed source binding is required before Factory use."}


def create_refresh_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"prospect_id"} or not isinstance(payload["prospect_id"], str):
        raise HunterRefreshError("Choose one reviewed Hunter lead; no other refresh fields are accepted.")
    matches = [(record, path) for record, path in _read_receipts() if record["snapshot"].get("prospect_id") == payload["prospect_id"]]
    if len(matches) != 1:
        raise HunterRefreshError("That lead is not an owner-reviewed Hunter draft.")
    request = _request_for(matches[0][0])
    target = _path(payload["prospect_id"])
    if target.is_file():
        return _response(_load_existing(target, request), reused=True)
    REQUEST_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(request, handle, ensure_ascii=False, indent=2)
    except FileExistsError:
        return _response(_load_existing(target, request), reused=True)
    return _response(request, reused=False)
