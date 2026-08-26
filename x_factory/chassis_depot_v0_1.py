"""Local, immutable X-Agent Chassis Depot and deterministic commissioning path."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import (
    MissionControlError,
    ROOT,
    SECRET_LIKE,
    PATH_LIKE,
    MODULE_CATALOG,
    canonical,
    create_mission,
    load_json,
    sha256,
    split_list,
)
from x_factory.knowledge_loading_v0_1 import KnowledgeLoadingError, commissioning_reference


CHASSIS_ROOT = ROOT / "chassis"
CHASSIS_SCHEMA = ROOT / "contracts/chassis_manifest.v0.1.schema.json"
COMMISSIONING_SCHEMA = ROOT / "contracts/commissioning_request.v0.1.schema.json"
CHASSIS_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

PUBLIC_ROLE_DOMAINS = (
    (re.compile(r"\bhome[- ]services?\b", re.IGNORECASE), "Home Services"),
    (re.compile(r"\bcustomer (?:service|support)\b", re.IGNORECASE), "Customer Support"),
    (re.compile(r"\bdata (?:quality|operations?|services?)\b", re.IGNORECASE), "Data Services"),
    (re.compile(r"\breal estate\b", re.IGNORECASE), "Real Estate"),
    (re.compile(r"\b(?:healthcare|medical|patient)\b", re.IGNORECASE), "Patient Services"),
    (re.compile(r"\b(?:financial|finance|banking)\b", re.IGNORECASE), "Financial Services"),
    (re.compile(r"\b(?:legal|law firm)\b", re.IGNORECASE), "Legal Services"),
)


class ChassisDepotError(MissionControlError):
    pass


def derive_public_role(purpose: str, chassis_role_title: str) -> str | None:
    """Return a safe customer-facing role only when the owner intent names a clear domain."""
    archetype = "Concierge" if "concierge" in chassis_role_title.casefold() else "Assistant"
    for pattern, domain in PUBLIC_ROLE_DOMAINS:
        if pattern.search(purpose):
            return f"{domain} {archetype}"
    return None


def _digest_manifest(manifest: dict[str, Any]) -> str:
    return sha256(canonical({key: value for key, value in manifest.items() if key != "chassis_sha256"}))


def validate_chassis(manifest: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(load_json(CHASSIS_SCHEMA)).validate(manifest)
    if _digest_manifest(manifest) != manifest["chassis_sha256"]:
        raise ChassisDepotError("Chassis manifest hash validation failed")
    if manifest["authority"].get("production_approved") is not False:
        raise ChassisDepotError("Chassis authority is not safely bounded")
    return manifest


def get_chassis(chassis_id: str, version: str | None = None) -> dict[str, Any]:
    if not CHASSIS_ID.fullmatch(chassis_id):
        raise ChassisDepotError("Invalid chassis ID")
    root = CHASSIS_ROOT / chassis_id
    if version:
        if not VERSION.fullmatch(version):
            raise ChassisDepotError("Invalid chassis version")
        candidates = [root / version / "chassis-manifest.json"]
    else:
        candidates = sorted(root.glob("*/chassis-manifest.json"), key=lambda item: tuple(int(part) for part in item.parent.name.split(".")), reverse=True) if root.is_dir() else []
    if not candidates or not candidates[0].is_file():
        raise ChassisDepotError("Chassis not found")
    return validate_chassis(load_json(candidates[0]))


def list_chassis() -> list[dict[str, Any]]:
    if not CHASSIS_ROOT.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for root in sorted(item for item in CHASSIS_ROOT.iterdir() if item.is_dir()):
        try:
            result.append(get_chassis(root.name))
        except (OSError, ValueError, ChassisDepotError):
            continue
    return result


def recommend_chassis(purpose: Any) -> dict[str, Any]:
    """Rank validated chassis against one plain-English owner intent."""
    if not isinstance(purpose, str):
        raise ChassisDepotError("What should this X-Agent do? is required")
    intent = re.sub(r"\s+", " ", purpose).strip()
    if len(intent) < 10 or len(intent) > 3000:
        raise ChassisDepotError("Describe the X-Agent's job in at least 10 characters")
    if SECRET_LIKE.search(intent):
        raise ChassisDepotError("Remove credentials, tokens, passwords, or private keys from the job description")
    if PATH_LIKE.search(intent):
        raise ChassisDepotError("Filesystem paths are not accepted in the job description")
    chassis = list_chassis()
    if not chassis:
        raise ChassisDepotError("No validated chassis are available")

    intent_terms = set(re.findall(r"[a-z0-9]+", intent.casefold()))
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in chassis:
        searchable = " ".join(
            [
                item["role_title"],
                item["summary"],
                item["invariants"]["purpose_template"],
                *item["invariants"]["must_accomplish"],
            ]
        ).casefold()
        chassis_terms = set(re.findall(r"[a-z0-9]+", searchable))
        ranked.append((len(intent_terms & chassis_terms), item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["role_title"].casefold()))
    best_score, best = ranked[0]
    return {
        "schema_version": "0.1",
        "owner_intent": intent,
        "recommended_by": "ATLAS_LOCAL_INTENT_MATCH",
        "provider_calls": 0,
        "recommended": best,
        "match_terms": best_score,
        "alternatives": [item for _, item in ranked[1:]],
    }


def list_module_options(chassis_id: str) -> dict[str, Any]:
    chassis = get_chassis(chassis_id)
    catalog = load_json(MODULE_CATALOG)["modules"]
    by_id = {item["module_id"]: item for item in catalog}
    included = [
        {
            "module_id": module_id,
            "name": by_id[module_id]["name"],
            "category": by_id[module_id]["category"],
            "status": "INCLUDED_LOCKED",
        }
        for module_id in chassis["modules"]
        if module_id in by_id
    ]
    optional = [
        {
            "module_id": item["module_id"],
            "name": item["name"],
            "category": item["category"],
            "description": item["description"],
            "requires_knowledge_package": item.get("requires_knowledge_package", False),
            "status": "AVAILABLE_FOR_COMMISSIONING",
        }
        for item in catalog
        if item.get("commissioning_option")
    ]
    return {
        "schema_version": "0.1",
        "chassis_id": chassis["chassis_id"],
        "chassis_version": chassis["version"],
        "included": included,
        "optional": optional,
        "locked": [
            {
                "module_id": "CMP-EXTERNAL-ACTION-RUNTIME",
                "name": "External action runtime",
                "status": "PROHIBITED_IN_CONTAINED_FACTORY",
                "reason": "Sending, booking, provider mutation, and production actions require a later separately governed stage.",
            }
        ],
    }


def _validation_errors(schema_path: Path, value: Any) -> list[str]:
    errors = sorted(Draft202012Validator(load_json(schema_path)).iter_errors(value), key=lambda item: list(item.path))
    return [error.message for error in errors[:5]]


def commission_chassis(chassis_id: str, request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ChassisDepotError("Commissioning request must be a JSON object")
    errors = _validation_errors(COMMISSIONING_SCHEMA, request)
    if errors:
        raise ChassisDepotError("; ".join(errors))
    serialized = str(request)
    if SECRET_LIKE.search(serialized):
        raise ChassisDepotError("Remove credentials, tokens, passwords, or private keys from commissioning inputs")
    if PATH_LIKE.search(serialized):
        raise ChassisDepotError("Upload paths are not accepted in this commissioning slice")
    chassis = get_chassis(chassis_id)
    option_catalog = {item["module_id"]: item for item in load_json(MODULE_CATALOG)["modules"] if item.get("commissioning_option")}
    selected_options = list(request.get("optional_module_ids") or [])
    unknown_options = sorted(set(selected_options) - set(option_catalog))
    if unknown_options:
        raise ChassisDepotError(f"Module is not available for commissioning: {unknown_options[0]}")
    knowledge_package = None
    package_id = request.get("knowledge_package_id")
    if package_id:
        try:
            knowledge_package = commissioning_reference(package_id)
        except KnowledgeLoadingError as error:
            raise ChassisDepotError(str(error)) from error
        if "CMP-CLIENT-KNOWLEDGE-PACK" not in selected_options:
            selected_options.append("CMP-CLIENT-KNOWLEDGE-PACK")
    if "CMP-CLIENT-KNOWLEDGE-PACK" in selected_options and not knowledge_package:
        raise ChassisDepotError("The Approved client knowledge pack option requires an owner-approved package")
    invariants = chassis["invariants"]
    requirements = [*invariants["must_accomplish"], *split_list(request.get("additional_requirements") or "")]
    boundaries = [*invariants["never_do"], *split_list(request.get("additional_boundaries") or "")]
    purpose = re.sub(r"\s+", " ", request["purpose"]).strip()
    agent_name = re.sub(r"\s+", " ", request["x_agent_name"]).strip()
    client_name = re.sub(r"\s+", " ", request["client_name"]).strip()
    public_role_title = derive_public_role(purpose, chassis["role_title"])
    runtime_role_title = public_role_title or "X-Agent"
    mission_payload = {
        "purpose": purpose,
        "agent_or_client": runtime_role_title,
        "x_agent_name": agent_name,
        "client_name": client_name,
        "role_title": runtime_role_title,
        "public_role_title": public_role_title,
        "chassis_role_title": chassis["role_title"],
        "chassis_id": chassis["chassis_id"],
        "chassis_version": chassis["version"],
        "chassis_sha256": chassis["chassis_sha256"],
        "client_context": request.get("client_context") or "",
        "personality": request["personality"],
        "must_accomplish": "; ".join(requirements),
        "never_do": "; ".join(boundaries),
        "target_users": request["target_users"],
        "output_artifact": invariants["output_artifact"],
        "presence_mode": request["presence_mode"],
        "persona_catalog_id": "ANAM-STOCK-MIA-SUPPORT-GUIDE" if request["presence_mode"] == "EXISTING_ANAM" else None,
        "selected_optional_modules": selected_options,
        "knowledge_package": knowledge_package,
        "owner_active_input_ms": request.get("owner_active_input_ms"),
    }
    record = create_mission(mission_payload)
    record["commissioning_summary"] = {
        "status": "COMMISSIONED_LOCAL_CANDIDATE_BUILT",
        "chassis_id": chassis["chassis_id"],
        "chassis_version": chassis["version"],
        "chassis_sha256": chassis["chassis_sha256"],
        "knowledge_package": knowledge_package or "CLIENT_MATERIALS_NOT_YET_INGESTED",
        "selected_optional_modules": selected_options,
        "commissioned_instance_intent": purpose,
        "provider_calls": 0,
        "production_approved": False,
    }
    return record
