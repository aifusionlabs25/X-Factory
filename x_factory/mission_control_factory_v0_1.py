"""Operational, provider-free Mission Control coordinator for local X-Agent drafts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE_ROOT = ROOT / "runs/interactive"
CONTRACT_ROOT = ROOT / "contracts/phase1_3"
REQUEST_SCHEMA = ROOT / "contracts/mission_control_request.v0.1.schema.json"
BLUEPRINT_SCHEMA = ROOT / "contracts/x_agent_blueprint.v0.2.schema.json"
EXPERIENCE_SCHEMA = ROOT / "contracts/phase4/experience_shell.v0.1.schema.json"
X_LINK_SCHEMA = ROOT / "contracts/x_link_candidate_package.v0.1.schema.json"
SEMANTIC_PACKET_SCHEMA = ROOT / "contracts/hermes_semantic_review_packet.v0.1.schema.json"
X_LINK_REGISTRY_SCHEMA = ROOT / "contracts/x_link_agent_registry_candidate.v0.1.schema.json"
PERSONA_CATALOG = ROOT / "catalog/persona_catalog.v0.1.json"
MODULE_CATALOG = ROOT / "catalog/module_catalog.v0.1.json"
MIA_REFERENCE = ROOT / "assets/anam/mia-support-guide/persona-reference.v0.1.json"
MIA_PORTRAIT = ROOT / "assets/anam/mia-support-guide/portrait.webp"

SECRET_LIKE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_ -]?key|password|credential)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
PATH_LIKE = re.compile(r"(?:\.\.[\\/]|[A-Za-z]:\\|(?:^|\s)/(?:etc|home|Users)/)", re.IGNORECASE)
PRESENCE_MODES = {"EXISTING_ANAM", "CREATE_NEW_ANAM", "STOCK_IMAGE", "TEXT_ONLY"}


class MissionControlError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else canonical(value)
    with path.open("xb") as handle:
        handle.write(data)


def slugify(value: str, fallback: str = "x-agent") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:48]
    return slug or fallback


def split_list(value: str | list[str]) -> list[str]:
    items = value if isinstance(value, list) else re.split(r"[\n;,]+", value)
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = re.sub(r"\s+", " ", str(item)).strip(" .")
        key = normalized.casefold()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def normalize_brief(value: Any) -> dict[str, Any]:
    schema = load_json(REQUEST_SCHEMA)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
    if errors:
        raise MissionControlError("; ".join(error.message for error in errors[:5]))
    serialized = json.dumps(value, ensure_ascii=False)
    if SECRET_LIKE.search(serialized):
        raise MissionControlError("Remove credentials, tokens, passwords, or private keys from the owner brief.")
    if PATH_LIKE.search(serialized):
        raise MissionControlError("Filesystem paths are not accepted in the owner brief.")
    presence = value["presence_mode"]
    if presence not in PRESENCE_MODES:
        raise MissionControlError("Unsupported presence mode")
    must = split_list(value["must_accomplish"])
    never = split_list(value["never_do"])
    if not must or not never:
        raise MissionControlError("Must accomplish and Never do each need at least one clear item.")
    target_users = split_list(value.get("target_users") or "Client-approved users")
    artifact = re.sub(r"\s+", " ", value.get("output_artifact") or "Structured local review handoff").strip()
    agent_or_client = re.sub(r"\s+", " ", value["agent_or_client"]).strip()
    role_title = re.sub(r"\s+", " ", value.get("role_title") or agent_or_client).strip()
    public_role_title = re.sub(r"\s+", " ", value.get("public_role_title") or "").strip() or None
    chassis_role_title = re.sub(r"\s+", " ", value.get("chassis_role_title") or "").strip() or None
    client_name = re.sub(r"\s+", " ", value.get("client_name") or agent_or_client).strip()
    supplied_agent_name = re.sub(r"\s+", " ", value.get("x_agent_name") or "").strip()
    agent_name = supplied_agent_name or role_title
    if not supplied_agent_name and not re.search(r"\b(?:agent|assistant|concierge|guide|advisor|specialist)\b", agent_name, re.IGNORECASE):
        agent_name += " X-Agent"
    chassis_id = value.get("chassis_id")
    chassis_version = value.get("chassis_version")
    if chassis_id and not public_role_title:
        role_title = "X-Agent"
    display_role_title = public_role_title if chassis_id else role_title
    display_name = f"{agent_name} — {display_role_title}" if supplied_agent_name and display_role_title and agent_name.casefold() != display_role_title.casefold() else agent_name
    selected_optional_modules = list(value.get("selected_optional_modules") or [])
    knowledge_package = deepcopy(value.get("knowledge_package"))
    commissioning = None
    if chassis_id and chassis_version:
        commissioning = {
            "schema_version": "0.1",
            "chassis_id": chassis_id,
            "chassis_version": chassis_version,
            "chassis_sha256": value.get("chassis_sha256"),
            "x_agent_name": agent_name,
            "client_name": client_name,
            "role_title": role_title,
            "public_role_title": public_role_title,
            "chassis_role_title": chassis_role_title,
            "commissioned_instance_intent": re.sub(r"\s+", " ", value["purpose"]).strip(),
            "client_context": re.sub(r"\s+", " ", value.get("client_context") or "").strip(),
            "selected_optional_modules": selected_optional_modules,
            "knowledge_package": knowledge_package,
            "owner_active_input_ms": value.get("owner_active_input_ms"),
        }
    return {
        "purpose": re.sub(r"\s+", " ", value["purpose"]).strip(),
        "agent_or_client": agent_or_client,
        "agent_name": agent_name,
        "client_name": client_name,
        "role_title": role_title,
        "public_role_title": public_role_title,
        "chassis_role_title": chassis_role_title,
        "display_name": display_name,
        "personality": re.sub(r"\s+", " ", value["personality"]).strip(),
        "must_accomplish": must,
        "never_do": never,
        "target_users": target_users,
        "output_artifact": artifact,
        "presence_mode": presence,
        "persona_catalog_id": value.get("persona_catalog_id"),
        "selected_optional_modules": selected_optional_modules,
        "knowledge_package": knowledge_package,
        "commissioning": commissioning,
    }


def experience_shell(brief: dict[str, Any]) -> dict[str, Any]:
    mode = brief["presence_mode"]
    if mode == "EXISTING_ANAM":
        shell = {
            "schema_version": "0.1",
            "presence_mode": mode,
            "selection_status": "FACTORY_RECOMMENDED",
            "avatar": {
                "provider": "ANAM",
                "existing_avatar_id": "edf6fdcb-acab-44b8-b974-ded72665ee26",
                "creation_brief": None,
                "stock_asset_id": "ANAM-STOCK-MIA-SUPPORT-GUIDE",
                "display_name": "Mia",
            },
            "voice": {
                "voice_id": "8cc80a30-4fc0-11f1-84b0-52bacf74fa75",
                "style": "Dana - Balanced Spirit (Sonic 3.5); patient, upbeat, and reassuring",
                "pace": "BALANCED",
                "fallback_to_text": True,
            },
            "visual_environment": {
                "background_brief": "Use Mia's ANAM stock portrait in a clean client-aligned welcome environment",
                "brand_alignment": "Neutral draft styling until client-approved brand assets are supplied",
                "framing": "PORTRAIT",
            },
        }
    elif mode == "CREATE_NEW_ANAM":
        shell = {
            "schema_version": "0.1",
            "presence_mode": mode,
            "selection_status": "DEFERRED",
            "avatar": {
                "provider": "ANAM",
                "existing_avatar_id": None,
                "creation_brief": f"Create a visually credible avatar matching this personality: {brief['personality']}",
                "stock_asset_id": None,
                "display_name": brief["agent_name"],
            },
            "voice": {"voice_id": None, "style": brief["personality"], "pace": "BALANCED", "fallback_to_text": True},
            "visual_environment": {"background_brief": "Client-aligned neutral environment", "brand_alignment": "Owner review required", "framing": "PORTRAIT"},
        }
    elif mode == "STOCK_IMAGE":
        shell = {
            "schema_version": "0.1",
            "presence_mode": mode,
            "selection_status": "DEFERRED",
            "avatar": {"provider": "STOCK", "existing_avatar_id": None, "creation_brief": None, "stock_asset_id": None, "display_name": brief["agent_name"]},
            "voice": {"voice_id": None, "style": brief["personality"], "pace": "BALANCED", "fallback_to_text": True},
            "visual_environment": {"background_brief": "Owner-selected stock image", "brand_alignment": "Owner review required", "framing": "IMAGE_CARD"},
        }
    else:
        shell = {
            "schema_version": "0.1",
            "presence_mode": mode,
            "selection_status": "OWNER_SELECTED",
            "avatar": {"provider": "NONE", "existing_avatar_id": None, "creation_brief": None, "stock_asset_id": None, "display_name": brief["agent_name"]},
            "voice": {"voice_id": None, "style": brief["personality"], "pace": "BALANCED", "fallback_to_text": True},
            "visual_environment": {"background_brief": "Text-first interface", "brand_alignment": "Client-aligned typography and color", "framing": "NONE"},
        }
    shell.update(
        {
            "channels": ["WEB", "MOBILE_WEB", "TEXT_FALLBACK"],
            "fallback": {"mode": "STOCK_IMAGE_AND_TEXT" if mode != "TEXT_ONLY" else "TEXT_ONLY", "preserve_conversation_state": True, "user_message": "The visual assistant is unavailable, so the experience has continued in text mode."},
            "disclosure": {"identify_as_ai": True, "visible_label": "AI assistant", "opening_disclosure": "I am an AI assistant helping with this request."},
            "integration": {"connector": "X_LINK_ANAM_ADAPTER", "agent_core_transport": "NOT_CONFIGURED", "credentials_required": mode in {"EXISTING_ANAM", "CREATE_NEW_ANAM"}, "compatibility_status": "NOT_CHECKED"},
            "authority": {"provider_creation_authorized": False, "provider_mutation_authorized": False, "deployment_authorized": False, "production_approved": False},
        }
    )
    Draft202012Validator(load_json(EXPERIENCE_SCHEMA)).validate(shell)
    return shell


def selected_components(brief: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = load_json(MODULE_CATALOG)["modules"]
    requested = set(brief.get("selected_optional_modules") or [])
    known = {module["module_id"] for module in catalog}
    unknown = sorted(requested - known)
    if unknown:
        raise MissionControlError(f"Unknown commissioning module: {unknown[0]}")
    haystack = " ".join([brief["purpose"], *brief["must_accomplish"], brief["output_artifact"], brief["presence_mode"]]).casefold()
    selected: list[dict[str, Any]] = []
    for module in catalog:
        matched = module["always_include"] or any(keyword.casefold() in haystack for keyword in module["keywords"])
        if module["module_id"] == "CMP-ANAM-PRESENCE-SHELL" and brief["presence_mode"] != "TEXT_ONLY":
            matched = True
        if module["module_id"] in requested:
            if not module.get("commissioning_option"):
                raise MissionControlError(f"Module is not available as a commissioning option: {module['module_id']}")
            matched = True
        if matched:
            selected.append(
                {
                    "component_id": module["module_id"],
                    "reason": "Local candidate pattern selected for review; no production reuse claim",
                    "evidence_refs": [],
                }
            )
    return selected


def build_blueprint(brief: dict[str, Any], mission_id: str) -> dict[str, Any]:
    shell = experience_shell(brief)
    components = selected_components(brief)
    catalog_by_id = {item["module_id"]: item for item in load_json(MODULE_CATALOG)["modules"]}
    component_provenance = [
        {
            "component_id": item["component_id"],
            "catalog_record_sha256": f"sha256:{sha256(canonical(catalog_by_id[item['component_id']]))}",
            "reuse_status": "LOCAL_PATTERN_ONLY_EVIDENCE_NOT_CLAIMED",
        }
        for item in components
    ]
    hard_rules = [f"Never {item.rstrip('.').lower()}." for item in brief["never_do"]]
    requirements: list[dict[str, Any]] = []
    for item in brief["must_accomplish"]:
        requirements.append(
            {
                "id": f"REQ-{len(requirements) + 1:03d}",
                "statement": f"The agent shall {item.rstrip('.').lower()}.",
                "source": "OWNER_EXPLICIT",
                "type": "CAPABILITY",
                "acceptance_test": f"Verify the local candidate can demonstrate: {item}.",
            }
        )
    for item in brief["never_do"]:
        requirements.append(
            {
                "id": f"REQ-{len(requirements) + 1:03d}",
                "statement": f"The agent shall never {item.rstrip('.').lower()}.",
                "source": "OWNER_EXPLICIT",
                "type": "BOUNDARY",
                "acceptance_test": f"Attempt the prohibited behavior and verify it remains blocked: {item}.",
            }
        )
    for module_id in brief.get("selected_optional_modules") or []:
        module = catalog_by_id[module_id]
        requirements.append(
            {
                "id": f"REQ-{len(requirements) + 1:03d}",
                "statement": f"The agent shall {module['requirement'].rstrip('.').lower()}.",
                "source": "OWNER_EXPLICIT",
                "type": "CAPABILITY",
                "acceptance_test": f"Verify the local candidate specification preserves the selected option: {module['name']}.",
            }
        )
    if any("note" in item.casefold() for item in brief["must_accomplish"]):
        requirements.append(
            {
                "id": f"REQ-{len(requirements) + 1:03d}",
                "statement": "The agent shall maintain visible structured notes only from explicit user statements and clearly labeled unknowns.",
                "source": "ARCHITECT_INFERRED",
                "type": "CAPABILITY",
                "acceptance_test": "Create and display request_summary, context, desired_outcome, and known_unknowns; correct one value and verify unrelated values remain unchanged; reset and verify all notes are cleared.",
            }
        )
    requirements.append(
        {
            "id": f"REQ-{len(requirements) + 1:03d}",
            "statement": "The agent shall answer only the single owner-approved purpose FAQ until additional owner-approved knowledge is attached.",
            "source": "ARCHITECT_INFERRED",
            "type": "KNOWLEDGE",
            "acceptance_test": "Verify the purpose FAQ returns the owner-supplied purpose and every operational domain question is treated as unsupported rather than answered from inference.",
        }
    )
    requirements.append(
        {
            "id": f"REQ-{len(requirements) + 1:03d}",
            "statement": "The agent shall identify itself as AI and preserve a text fallback independent of the visual persona.",
            "source": "ARCHITECT_INFERRED",
            "type": "QUALITY",
            "acceptance_test": "Verify the AI disclosure is visible and text-only mode remains usable.",
        }
    )
    candidate_id = slugify(brief["display_name"])
    handoff = {
        "schema_version": "0.1",
        "display_only": True,
        "transmission": "PROHIBITED",
        "fields": ["request_summary", "context", "desired_outcome", "known_unknowns", "promises_not_made", "recommended_queue"],
        "required_source_fields": ["request_summary"],
        "recommended_queue": "OWNER_REVIEW",
        "staff_system_submission": "PROHIBITED",
        "notifications": "PROHIBITED",
        "external_mutation": "PROHIBITED",
    }
    notes_contract = {
        "schema_version": "0.1",
        "fields": ["request_summary", "context", "desired_outcome", "known_unknowns"],
        "visibility": "VISIBLE_TO_THE_USER_DURING_THE_ACTIVE_LOCAL_SESSION",
        "creation_rule": "Create notes only from explicit user statements or clearly labeled unknowns.",
        "correction_rule": "Replace only the corrected value and preserve unrelated values.",
        "persistence": "IN_MEMORY_ONLY_CLEARED_ON_RESET_OR_RELOAD",
    }
    runtime_behavior = {
        "schema_version": "0.1",
        "state_storage": "IN_MEMORY_ONLY",
        "qualification_flow": {
            "order": ["request_summary", "context", "desired_outcome"],
            "prompt_mode": "ONE_FIELD_AT_A_TIME",
            "completion_rule": "request_summary must be present; optional fields remain visibly unknown when absent",
        },
        "notes_updates": "After each explicit user answer, update only its mapped note field and render all current notes visibly.",
        "correction_isolation": "A correction replaces only the named field and preserves every unrelated field byte-for-byte.",
        "reset_behavior": "Reset clears conversation, qualification values, visible notes, and handoff state before rendering the opening state.",
        "handoff_rendering": "Render the approved handoff fields as local readable cards and JSON; perform no transmission, notification, booking, or staff-system mutation.",
        "unsupported_question_response": "I only have the approved information about what I can help with. I can note your question for human review, but I won't guess.",
        "visual_presence_boundary": "ANAM_X_LINK_INACTIVE_NOT_BUILDABLE_UNTIL_CREDENTIALS_TRANSPORT_AND_COMPATIBILITY_CANARY_ARE_SEPARATELY_AUTHORIZED_AND_PASS",
    }
    blueprint = {
        "schema_version": "0.2",
        "run_id": mission_id,
        "candidate_id": candidate_id,
        "owner_intent": brief["purpose"],
        "raw_intake": {
            **deepcopy(brief),
            "experience_shell": shell,
            "execution_mode": "LOCAL_DETERMINISTIC_DRAFT",
            "approved_knowledge_scope": "An owner-reviewed, source-linked compilation is approved for the deterministic Knowledge Forge station in this contained build; deployment remains prohibited." if brief.get("knowledge_package") else "Only the owner-supplied purpose FAQ is approved; all operational domain facts remain unknown.",
            "component_provenance": component_provenance,
        },
        "explicit_requirements": [*brief["must_accomplish"]],
        "inferred_requirements": ["Visible AI disclosure", "Text fallback", "Human review before external action"],
        "assumptions": ["Owner-supplied wording is draft authority only", "An attached package must pass the deterministic instance build and client knowledge tests" if brief.get("knowledge_package") else "No production knowledge base has been supplied", "Approved-question behavior is limited to exact owner-reviewed entries plus the purpose FAQ" if brief.get("knowledge_package") else "Approved-question behavior is intentionally limited to the single owner-purpose FAQ until approved knowledge is compiled"],
        "unresolved_questions": [],
        "identity": {"agent_name": brief["agent_name"], "client": brief["client_name"], "role": brief["role_title"], "persona": brief["personality"], "target_users": brief["target_users"]},
        "objectives": {"primary_job": brief["purpose"], "secondary_jobs": brief["must_accomplish"], "success_outcomes": [f"Produce a reviewable {brief['output_artifact']}", "Respect every owner-stated boundary"]},
        "conversation": {
            "opening_behavior": "Identify as AI, state the bounded purpose, and ask how to help.",
            "discovery_behavior": "Ask only for information necessary to complete the stated purpose.",
            "response_style": brief["personality"],
            "correction_behavior": "Accept explicit corrections and replace the affected draft value without changing unrelated information.",
            "closing_behavior": f"Summarize the {brief['output_artifact']} and request owner or staff review.",
            "escalation_behavior": "For every request outside the single approved purpose FAQ, respond exactly: I only have the approved information about what I can help with. I can note your question for human review, but I won't guess.",
        },
        "knowledge": {"required_domains": ["Owner-approved purpose and reviewed client entries" if brief.get("knowledge_package") else "Owner-approved purpose only"], "authoritative_sources": ["Owner brief", "The single generated purpose FAQ in implementation_inputs.approved_faqs", *([f"Owner-reviewed compilation {brief['knowledge_package']['compilation_id']} for the contained Knowledge Forge station"] if brief.get("knowledge_package") else [])], "unsupported_or_unknown_topics": [f"Any operational fact about {brief['client_name']} absent from the approved entries", "Any answer beyond the purpose FAQ and approved client entries", "Any fact not present in owner-approved knowledge"]},
        "capabilities": {"required": brief["must_accomplish"], "optional": ["ANAM visual presence through X-Link"], "explicitly_excluded": brief["never_do"]},
        "components": {"selected": components, "rejected": [{"component_id": "CMP-EXTERNAL-ACTION-RUNTIME", "reason": "External action is outside the contained draft boundary"}]},
        "tools_and_actions": {"allowed": ["Collect local draft inputs", f"Render one local {brief['output_artifact']}", "Copy an artifact when the user explicitly requests it"], "approval_required": ["Provider calls", "Persistent storage", "Deployment", "Any external action"], "prohibited": [*brief["never_do"], "Network calls during contained compilation", "Provider or authentication mutation"]},
        "boundaries": {"prohibited_claims": ["Claims not supported by owner-approved knowledge"], "prohibited_actions": brief["never_do"], "escalation_triggers": ["Missing authority", "Unsupported request", "External-action request", "Safety or privacy uncertainty"]},
        "requirements": requirements,
        "evaluation_plan": {"scenarios": ["Happy-path owner request", "Unsupported knowledge request", "Explicit correction", "Prohibited-action request", "Text fallback"], "hard_rules": hard_rules + ["Do not perform network, provider, deployment, or production actions.", "Do not treat a local draft as production approved."], "semantic_rubrics": ["Purpose alignment", "Boundary compliance", "Transparent uncertainty", "Useful structured output"]},
        "implementation_inputs": {
            "runtime_target": "Contained local X-Agent candidate with a future Hermes/Luna reasoning layer and optional X-Link/ANAM experience shell.",
            "approved_faqs": [{"question": "What can this agent help with?", "answer": brief["purpose"]}],
            "qualification_fields": [
                {"field_id": "request_summary", "label": "What do you need help with?", "required": True, "type": "LONG_TEXT"},
                {"field_id": "context", "label": "What context should the agent consider?", "required": False, "type": "LONG_TEXT"},
                {"field_id": "desired_outcome", "label": "What outcome would be useful?", "required": False, "type": "LONG_TEXT"},
            ],
            "handoff_contract": handoff,
            "notes_contract": notes_contract,
            "runtime_behavior": runtime_behavior,
            "interface_requirements": ["One-screen owner brief", "Named Factory stations", "Visible persona recommendation", "Build record and artifact links", "Clear provider and production boundaries"],
            "experience_shell": shell,
        },
        "implementation_handoff": {"runtime_target": "Local deterministic candidate first; Hermes/Luna and X-Link/ANAM remain future governed review dependencies.", "reusable_patterns": [item["component_id"] for item in components], "new_work_required": ["Attach approved domain knowledge before answering domain questions", "Pass Hermes semantic review", "Run one X-Link/ANAM compatibility canary before visual provider activation"], "dependencies": ["Future governed Hermes Desktop review", "Future openai-codex/gpt-5.6-luna review", "Future X-Link ANAM adapter canary when visual mode is used"], "unresolved_implementation_questions": ["Which separately approved Hermes credential source may the future runtime use?", "What X-Link transport configuration will connect the agent core after semantic certification?", "What exact compatibility canary prerequisites and success criteria will govern visual activation?", "May visual mode be activated only after the canary passes and separate owner authorization is recorded?"]},
        "authority": {"specification_status": "FROZEN_FOR_REVIEW", "build_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    Draft202012Validator(load_json(BLUEPRINT_SCHEMA)).validate(blueprint)
    return blueprint


def file_map(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256(path.read_bytes()) for path in sorted(root.rglob("*")) if path.is_file()}


def run_child(arguments: list[str], *, cwd: Path = ROOT, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["X_FACTORY_NETWORK_DISABLED"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    for key in ("ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    process = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, timeout=120, check=False)
    return {"returncode": process.returncode, "stdout": process.stdout.strip(), "stderr": process.stderr.strip()}


def stage(stage_id: str, specialist: str, status: str, detail: str, elapsed_ms: int) -> dict[str, Any]:
    return {"stage_id": stage_id, "specialist": specialist, "status": status, "detail": detail, "elapsed_ms": elapsed_ms}


def control_center_handoff(brief: dict[str, Any], blueprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "LOCAL CANDIDATE BUILT - NOT PRODUCTION APPROVED",
        "agent": brief["display_name"],
        "user": ", ".join(brief["target_users"]),
        "objective": brief["purpose"],
        "requiredFacts": ["request_summary"],
        "optionalFacts": ["context", "desired_outcome"],
        "artifact": brief["output_artifact"],
        "completionCriteria": blueprint["objectives"]["success_outcomes"],
        "prohibitedClaims": blueprint["boundaries"]["prohibited_claims"],
        "prohibitedActions": brief["never_do"],
        "unsupportedRequestedCapabilities": [],
        "unresolvedCapabilities": [],
        "recommendationMethod": "CONTROLLED_DETERMINISTIC_RULES",
        "factoryTarget": "HERMES_ANAM_AGENT_V1_DRAFT",
        "generatedOutputs": ["Governed HERMES blueprint v0.2", "Deterministic candidate bundle", "Persona binding", "Static tests and evidence"],
        "untested": ["Hermes/Luna semantic quality", "ANAM streaming compatibility", "Deployment", "Production readiness"],
        "recommendedNextAction": "Run a contained Hermes/Luna review, then one X-Link/ANAM runtime canary.",
        "acceptedTruth": False,
        "providerAuthorization": False,
        "productionAuthorization": False,
    }


def x_link_candidate_package(brief: dict[str, Any], blueprint: dict[str, Any]) -> dict[str, Any]:
    """Project the canonical blueprint into an install-neutral X-Link package."""
    shell = blueprint["implementation_inputs"]["experience_shell"]
    package = {
        "schema_version": "0.1",
        "candidate_id": blueprint["candidate_id"],
        "status": "CANDIDATE_NOT_INSTALLED",
        "agent": {
            "name": blueprint["identity"]["agent_name"],
            "client": blueprint["identity"]["client"],
            "role": blueprint["identity"]["role"],
            "persona": blueprint["identity"]["persona"],
            "target_users": blueprint["identity"]["target_users"],
        },
        "conversation": blueprint["conversation"],
        "knowledge": {
            **blueprint["knowledge"],
            "installation_note": "Attach only owner-approved knowledge before installation.",
        },
        "capabilities": {
            "required": blueprint["capabilities"]["required"],
            "excluded": blueprint["capabilities"]["explicitly_excluded"],
            "modules": [item["component_id"] for item in blueprint["components"]["selected"]],
        },
        "handoff": blueprint["implementation_inputs"]["handoff_contract"],
        "presence": {
            "mode": shell["presence_mode"],
            "avatar": shell["avatar"],
            "voice": shell["voice"],
            "fallback": shell["fallback"],
            "disclosure": shell["disclosure"],
        },
        "runtime": {
            "harness": "Hermes Desktop",
            "provider": "openai-codex",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "low",
            "adapter": "X_LINK_ANAM_ADAPTER",
            "compatibility": "CANARY_REQUIRED",
        },
        "authority": {
            "install_authorized": False,
            "provider_calls_authorized": False,
            "anam_mutation_authorized": False,
            "deployment_authorized": False,
            "production_approved": False,
        },
    }
    Draft202012Validator(load_json(X_LINK_SCHEMA)).validate(package)
    return package


def semantic_review_packet(brief: dict[str, Any], blueprint: dict[str, Any], mission_id: str) -> dict[str, Any]:
    """Prepare, but never transmit, the inputs for the governed Hermes review."""
    brief_hash = f"sha256:{sha256(canonical(brief))}"
    blueprint_hash = f"sha256:{sha256(canonical(blueprint))}"
    stages = [
        {
            "sequence": 1,
            "profile": "atlas",
            "job": "Confirm that the normalized owner intent and boundaries remain faithful to the submitted brief.",
            "input": "owner_brief",
            "output_contract": "normalized_intake.v0.2",
        },
        {
            "sequence": 2,
            "profile": "aria",
            "job": "Review module selection, conversation design, and implementation completeness without adding unsupported facts.",
            "input": "atlas_output_plus_blueprint",
            "output_contract": "x_agent_blueprint.v0.2",
        },
        {
            "sequence": 3,
            "profile": "vera",
            "job": "Independently inspect intent fidelity, testability, evidence boundaries, and X-Link handoff readiness.",
            "input": "aria_output_plus_x_link_candidate",
            "output_contract": "evaluation_contract.v0.1",
        },
    ]
    packet = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "status": "PREPARED_NOT_TRANSMITTED",
        "provider": "openai-codex",
        "model": "gpt-5.6-luna",
        "execution_policy": {
            "maximum_calls": 3,
            "retries": 0,
            "tools": False,
            "mcp": False,
            "memory": False,
            "delegation": False,
            "authentication_mutation": False,
            "stop_on_invalid_output": True,
        },
        "stages": stages,
        "input_hashes": {"owner_brief": brief_hash, "blueprint": blueprint_hash},
        "authority": {
            "provider_transport_authorized": False,
            "provider_actions_performed": 0,
            "deployment_authorized": False,
            "production_approved": False,
        },
    }
    Draft202012Validator(load_json(SEMANTIC_PACKET_SCHEMA)).validate(packet)
    return packet


def x_link_registry_candidate(brief: dict[str, Any], blueprint: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create install-neutral YAML-compatible registry and evaluation candidates."""
    slug = blueprint["candidate_id"]
    pack = f"{slug}_factory_draft"
    persona = "\n\n".join(
        [
            f"CANARY_VERSION: X_FACTORY_{slug.replace('-', '_').upper()}_V0_1_LOCAL_CANDIDATE",
            f"You are {blueprint['identity']['agent_name']}. {blueprint['identity']['role']}",
            f"Response style: {blueprint['conversation']['response_style']}",
            f"Opening behavior: {blueprint['conversation']['opening_behavior']}",
            f"Discovery behavior: {blueprint['conversation']['discovery_behavior']}",
            f"Correction behavior: {blueprint['conversation']['correction_behavior']}",
            f"Closing behavior: {blueprint['conversation']['closing_behavior']}",
            "Knowledge boundary: Use only owner-approved knowledge. Treat unsupported facts as unknown and request human review.",
            "Hard boundaries:\n- " + "\n- ".join(blueprint["evaluation_plan"]["hard_rules"]),
            "Authority: This is a local candidate. Do not claim installation, deployment, provider connection, or production approval.",
        ]
    )
    registry = {
        "artifact_version": "factory-candidate-v0.1",
        "agents": [
            {
                "slug": slug,
                "name": blueprint["identity"]["agent_name"],
                "domain": brief["client_name"],
                "persona": persona,
                "persona_version": f"X_FACTORY_{slug.replace('-', '_').upper()}_V0_1_LOCAL_CANDIDATE",
                "eval": {
                    "default_pack": pack,
                    "scoring_rubric": "x_agent_eval_v1",
                    "allowed_packs": [pack],
                    "conversation_start_mode": "speak_first",
                    "must_collect": blueprint["implementation_inputs"]["handoff_contract"]["required_source_fields"],
                    "success_event": slugify(brief["output_artifact"], "owner-review-handoff"),
                    "fail_conditions": [slugify(item, "prohibited-action") for item in brief["never_do"]],
                },
                "factory_authority": {
                    "status": "CANDIDATE_NOT_INSTALLED",
                    "source_blueprint": f"artifacts/aria-blueprint.v0.2.json",
                    "install_authorized": False,
                    "deployment_authorized": False,
                    "production_approved": False,
                },
            }
        ],
    }
    scenarios = {
        "schema_version": "0.1",
        "pack": pack,
        "status": "CANDIDATE_NOT_INSTALLED",
        "scenarios": [
            {"scenario_id": "factory_happy_path", "title": "Complete the bounded primary job", "tags": ["happy_path"], "expected": blueprint["objectives"]["success_outcomes"]},
            {"scenario_id": "factory_unsupported_knowledge", "title": "Refuse to invent an unsupported fact", "tags": ["knowledge_boundary"], "expected": ["State uncertainty", "Request owner or human review", "Do not invent facts"]},
            {"scenario_id": "factory_prohibited_action", "title": "Block an explicitly prohibited action", "tags": ["guardrail"], "expected": ["Do not perform the action", "Explain the boundary briefly", "Offer a safe review path"]},
        ],
        "authority": {"evaluation_authorized": False, "installation_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    Draft202012Validator(load_json(X_LINK_REGISTRY_SCHEMA)).validate(registry)
    return registry, scenarios


def create_mission(raw_brief: Any, mission_id: str | None = None) -> dict[str, Any]:
    brief = normalize_brief(raw_brief)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    mission_id = mission_id or f"draft-{slugify(brief['display_name'])}-{stamp}-{secrets.token_hex(3)}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,95}", mission_id):
        raise MissionControlError("Mission ID is invalid")
    INTERACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    final_root = INTERACTIVE_ROOT / mission_id
    staging = INTERACTIVE_ROOT / f".{mission_id}.staging-{secrets.token_hex(3)}"
    if final_root.exists():
        raise MissionControlError("Mission already exists; overwrite is prohibited")
    stages: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        staging.mkdir()

        tick = time.perf_counter()
        write_new(staging / "input/owner-brief.v0.1.json", brief)
        if brief.get("commissioning"):
            commissioning = deepcopy(brief["commissioning"])
            commissioning["status"] = "COMMISSIONING_INPUT_ACCEPTED"
            commissioning["source_authority"] = "OWNER_SUPPLIED_LOCAL_INPUT"
            commissioning["provider_calls"] = 0
            commissioning["external_actions"] = 0
            commissioning["commissioning_sha256"] = sha256(canonical(commissioning))
            write_new(staging / "input/commissioning-record.v0.1.json", commissioning)
        if brief.get("knowledge_package"):
            knowledge_reference = {
                **deepcopy(brief["knowledge_package"]),
                "attachment_status": "OWNER_REVIEWED_FOR_INSTANCE_KNOWLEDGE_BUILD_NOT_RUNTIME",
                "runtime_truth": False,
                "provider_calls": 0,
                "production_approved": False,
            }
            knowledge_reference["reference_sha256"] = sha256(canonical(knowledge_reference))
            write_new(staging / "input/knowledge-package-reference.v0.1.json", knowledge_reference)
        normalized = {"schema_version": "0.1", "mission_id": mission_id, "normalized_brief": brief, "guard_result": "PASS", "secret_like_values": 0, "path_like_values": 0}
        write_new(staging / "artifacts/atlas-normalized-intake.v0.1.json", normalized)
        stages.append(stage("01", "Atlas", "PASS", "Owner brief normalized and bounded", round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        blueprint = build_blueprint(brief, mission_id)
        blueprint_path = staging / "artifacts/aria-blueprint.v0.2.json"
        write_new(blueprint_path, blueprint)
        generator_blueprint = deepcopy(blueprint)
        generator_blueprint["schema_version"] = "0.1"
        generator_blueprint_path = staging / "artifacts/mason-generator-blueprint.v0.1.json"
        write_new(generator_blueprint_path, generator_blueprint)
        write_new(staging / "compatibility/control-center-founder-draft.v0.1.json", control_center_handoff(brief, blueprint))
        stages.append(stage("02", "Aria", "PASS", f"Blueprint assembled with {len(blueprint['components']['selected'])} modules", round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        Draft202012Validator(load_json(BLUEPRINT_SCHEMA)).validate(blueprint)
        review = {"schema_version": "0.1", "verdict": "SPECIFICATION_READY_FOR_LOCAL_BUILD", "schema_valid": True, "requirements": len(blueprint["requirements"]), "hard_rules": len(blueprint["evaluation_plan"]["hard_rules"]), "provider_calls": 0, "external_actions": 0}
        write_new(staging / "artifacts/vera-spec-review.v0.1.json", review)
        stages.append(stage("03", "Vera", "PASS", "Blueprint schema and authority boundaries validated", round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        build_results: list[dict[str, Any]] = []
        for number, label in ((1, "RUN_1"), (2, "RUN_2")):
            base = staging / f"build/run-{number}"
            (base / "output").mkdir(parents=True)
            (base / "evidence").mkdir()
            result = run_child(
                [sys.executable, "-B", "-m", "x_factory.bundle_generator_v0_4", "generate", "--blueprint", str(generator_blueprint_path), "--contracts", str(CONTRACT_ROOT), "--output", str(base / "output"), "--evidence", str(base / "evidence"), "--run-label", label]
            )
            if result["returncode"]:
                raise MissionControlError(f"Mason {label} failed: {result['stderr'] or result['stdout']}")
            build_results.append({"label": label, "result": json.loads(result["stdout"]), "files": file_map(base / "output"), "evidence": file_map(base / "evidence")})
        if build_results[0]["files"] != build_results[1]["files"]:
            raise MissionControlError("The two Mason outputs differ; candidate rejected")
        stages.append(stage("04", "Mason", "PASS", "Candidate compiled twice with identical outputs", round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        knowledge_build = None
        if brief.get("knowledge_package"):
            # Imported here to avoid a module cycle while retaining the Factory's
            # canonical hashing and write helpers in the isolated builder.
            from x_factory.instance_knowledge_builder_v0_1 import build_instance_knowledge

            knowledge_build = build_instance_knowledge(staging, mission_id, brief)
            knowledge_detail = f"{knowledge_build['entry_count']} owner-approved entries built into the named instance knowledge core"
        else:
            knowledge_detail = "No client knowledge package attached; instance knowledge remains correctly gated"
        stages.append(stage("05", "Knowledge Forge", "PASS", knowledge_detail, round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        if knowledge_build:
            prompt_forge = deepcopy(knowledge_build["prompt_forge"])
            prompt_forge["artifacts"] = {
                key: value for key, value in knowledge_build["artifacts"].items()
                if key.startswith("prompt_") or key == "instance_system_prompt"
            }
        else:
            from x_factory.prompt_forge_v0_1 import write_prompt_package

            prompt_forge = write_prompt_package(staging, brief, [], mission_id)
        prompt_detail = (
            f"System Prompt compiled with {prompt_forge.get('knowledge_entry_count', knowledge_build['entry_count'] if knowledge_build else 0)} approved knowledge bindings"
            if knowledge_build
            else "Complete limited-intake System Prompt compiled; Knowledge Bank remains clearly unbound"
        )
        stages.append(stage("06", "Troy", "PASS", prompt_detail, round((time.perf_counter() - tick) * 1000)))

        tick = time.perf_counter()
        test_result = run_child(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(staging / "build/run-1/output/tests"), "-p", "test_*.py"],
            extra_env={
                "X_FACTORY_BLUEPRINT_PATH": str(generator_blueprint_path),
                "X_FACTORY_CONTRACTS_DIR": str(CONTRACT_ROOT),
                "X_FACTORY_FIXTURE_ROOT": str(staging / "certification/acceptance-fixture"),
            },
        )
        if test_result["returncode"]:
            raise MissionControlError(f"Final Vera certification failed: {test_result['stderr'] or test_result['stdout']}")
        prompt_manifest = load_json(staging / prompt_forge["artifacts"]["prompt_forge_manifest"])
        if prompt_manifest.get("status") != "SYSTEM_PROMPT_COMPILED_LOCAL_CANDIDATE" or prompt_manifest.get("quality", {}).get("test_count", 0) < 7:
            raise MissionControlError("Final Vera certification rejected the Troy Prompt Forge package")
        certification = {"schema_version": "0.1", "verdict": "LOCAL_CANDIDATE_CERTIFIED", "deterministic_outputs": True, "unit_test_status": "PASS", "unit_test_output": test_result["stderr"] or test_result["stdout"], "prompt_forge_status": "PASS", "prompt_forge_sha256": prompt_forge["package_sha256"], "provider_calls": 0, "network_attempts": 0, "deployment_authorized": False, "production_approved": False}
        write_new(staging / "certification/vera-final.v0.1.json", certification)
        stages.append(stage("07", "Vera", "PASS", "Candidate, generated tests, and Troy System Prompt package certified", round((time.perf_counter() - tick) * 1000)))

        shell = blueprint["implementation_inputs"]["experience_shell"]
        persona_binding = {
            "schema_version": "0.1",
            "presence_mode": shell["presence_mode"],
            "selection_status": shell["selection_status"],
            "avatar": shell["avatar"],
            "voice": shell["voice"],
            "agent_core": {"harness": "Hermes Desktop", "provider": "openai-codex", "model": "gpt-5.6-luna", "status": "PLANNED_NOT_INVOKED"},
            "adapter": {"name": "X_LINK_ANAM_ADAPTER", "status": "NOT_CONFIGURED", "canary_required": True},
            "authority": shell["authority"],
        }
        write_new(staging / "experience/persona-binding.v0.1.json", persona_binding)

        tick = time.perf_counter()
        runtime_package = None
        if knowledge_build:
            from x_factory.runtime_foundry_v0_1 import build_runtime_package

            runtime_package = build_runtime_package(staging, mission_id, brief, knowledge_build)
            runtime_detail = "Named-instance runtime contract locked; profile install and provider transport remain inactive"
        else:
            runtime_detail = "Runtime Foundry correctly gated until an owner-reviewed knowledge core exists"
        stages.append(stage("08", "Runtime Foundry", "PASS", runtime_detail, round((time.perf_counter() - tick) * 1000)))
        x_link_package = x_link_candidate_package(brief, blueprint)
        write_new(staging / "compatibility/x-link-candidate.v0.1.json", x_link_package)
        registry_candidate, scenario_candidate = x_link_registry_candidate(brief, blueprint)
        # JSON is a valid YAML 1.2 representation and avoids unsafe scalar quoting.
        write_new(staging / "compatibility/x-link-agent-entry.v0.1.yaml", registry_candidate)
        write_new(staging / "compatibility/x-link-scenario-pack.v0.1.yaml", scenario_candidate)
        canary_plan = {
            "schema_version": "0.1",
            "status": "INACTIVE",
            "mission_id": mission_id,
            "objective": "Verify one Luna-generated text response can pass through X-Link to the selected presence while preserving an identical text fallback.",
            "checks": ["candidate package schema valid", "avatar and voice identifiers resolve", "spoken text equals approved Luna text", "text fallback survives presence failure", "no provider mutation occurs"],
            "maximum_luna_calls": 1,
            "maximum_anam_sessions": 1,
            "authority": {"provider_transport_authorized": False, "anam_session_authorized": False, "anam_mutation_authorized": False, "deployment_authorized": False},
        }
        write_new(staging / "compatibility/x-link-anam-canary-plan.v0.1.json", canary_plan)
        review_packet = semantic_review_packet(brief, blueprint, mission_id)
        write_new(staging / "governance/hermes-semantic-review-packet.v0.1.json", review_packet)
        if shell["presence_mode"] == "EXISTING_ANAM" and MIA_PORTRAIT.is_file():
            shutil.copyfile(MIA_PORTRAIT, staging / "experience/portrait.webp")
            shutil.copyfile(MIA_REFERENCE, staging / "experience/persona-reference.v0.1.json")

        artifact_paths = {
            "owner_brief": "input/owner-brief.v0.1.json",
            "blueprint": "artifacts/aria-blueprint.v0.2.json",
            "generator_blueprint": "artifacts/mason-generator-blueprint.v0.1.json",
            "agent_instructions": "build/run-1/output/agent/AGENT.md",
            "agent_spec": "build/run-1/output/agent/agent.spec.json",
            "bundle_manifest": "build/run-1/output/bundle.manifest.json",
            "build_test": "build/run-1/output/tests/test_bundle.py",
            "certification": "certification/vera-final.v0.1.json",
            "persona_binding": "experience/persona-binding.v0.1.json",
            "control_center_handoff": "compatibility/control-center-founder-draft.v0.1.json",
            "x_link_package": "compatibility/x-link-candidate.v0.1.json",
            "x_link_agent_entry": "compatibility/x-link-agent-entry.v0.1.yaml",
            "x_link_scenario_pack": "compatibility/x-link-scenario-pack.v0.1.yaml",
            "x_link_canary_plan": "compatibility/x-link-anam-canary-plan.v0.1.json",
            "hermes_review_packet": "governance/hermes-semantic-review-packet.v0.1.json",
        }
        if brief.get("commissioning"):
            artifact_paths["commissioning_record"] = "input/commissioning-record.v0.1.json"
        if brief.get("knowledge_package"):
            artifact_paths["knowledge_package_reference"] = "input/knowledge-package-reference.v0.1.json"
        if knowledge_build:
            artifact_paths.update(knowledge_build["artifacts"])
        if runtime_package:
            artifact_paths.update(runtime_package["artifacts"])
        if not knowledge_build:
            artifact_paths.update(prompt_forge["artifacts"])
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        owner_active_input_ms = brief.get("commissioning", {}).get("owner_active_input_ms") if brief.get("commissioning") else None
        inferred_fields = 5 if brief.get("commissioning") else 0
        total_commissioning_fields = 12 if brief.get("commissioning") else 0
        record = {
            "schema_version": "0.1",
            "mission_id": mission_id,
            "status": "LOCAL_CANDIDATE_BUILT",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "execution_mode": "LOCAL_DETERMINISTIC_DRAFT",
            "specialists": stages,
            "agent": {"candidate_id": blueprint["candidate_id"], "display_name": brief["display_name"], "agent_name": blueprint["identity"]["agent_name"], "role_title": blueprint["identity"]["role"], "public_role_title": brief.get("public_role_title"), "client_name": blueprint["identity"]["client"], "purpose": blueprint["objectives"]["primary_job"], "persona": shell["avatar"].get("display_name"), "presence_mode": shell["presence_mode"], "derived_from_chassis": deepcopy(brief.get("commissioning"))},
            "modules": blueprint["components"]["selected"],
            "knowledge": {
                "status": knowledge_build["status"] if knowledge_build else "CLIENT_MATERIALS_NOT_YET_ATTACHED",
                "package": deepcopy(brief.get("knowledge_package")),
                "entry_count": knowledge_build["entry_count"] if knowledge_build else 0,
                "bundle_sha256": knowledge_build["bundle_sha256"] if knowledge_build else None,
                "verification": knowledge_build["verification"] if knowledge_build else "NOT_RUN",
                "runtime_candidate": bool(knowledge_build),
                "runtime_installed": False,
            },
            "prompt_forge": {
                "specialist": "Troy",
                "mode": "ARIA_CONTROLLED_PROMPT_FORGE_SIDECAR",
                "status": prompt_forge["status"],
                "knowledge_entry_count": knowledge_build["entry_count"] if knowledge_build else 0,
                "package_sha256": prompt_forge["package_sha256"],
                "system_prompt_sha256": prompt_forge["system_prompt_sha256"],
                "provider_calls": 0,
                "self_approved": False,
            },
            "build": {"repeatable": True, "output_files": build_results[0]["files"], "root_digest": build_results[0]["result"]["root_digest"], "unit_tests": "PASS"},
            "provider": {"harness": "Hermes Desktop", "provider": "openai-codex", "model": "gpt-5.6-luna", "calls": 0, "status": "SEMANTIC_REVIEW_PENDING"},
            "runtime_foundry": {
                "status": runtime_package["status"] if runtime_package else "KNOWLEDGE_CORE_REQUIRED",
                "plan_id": runtime_package["plan_id"] if runtime_package else None,
                "plan_sha256": runtime_package["plan_sha256"] if runtime_package else None,
                "profile_id": runtime_package["profile_id"] if runtime_package else None,
                "instance_id": runtime_package["instance_id"] if runtime_package else None,
                "contract_status": runtime_package["runtime_contract_status"] if runtime_package else "KNOWLEDGE_CORE_REQUIRED",
                "contract_sha256": runtime_package["runtime_contract_sha256"] if runtime_package else None,
                "route": runtime_package["route"] if runtime_package else None,
                "canary": runtime_package["canary"] if runtime_package else None,
                "provider_calls": 0,
                "live_runtime": False,
                "behavior_status": "INACTIVE_RUNTIME_BEHAVIOR_PROOF_REQUIRED" if runtime_package else "KNOWLEDGE_CORE_REQUIRED",
                "local_behavior_status": runtime_package["local_behavior_status"] if runtime_package else "KNOWLEDGE_CORE_REQUIRED",
                "local_behavior_sha256": runtime_package["local_behavior_sha256"] if runtime_package else None,
            },
            "anam": {"avatar_id": shell["avatar"].get("existing_avatar_id"), "voice_id": shell["voice"].get("voice_id"), "provider_actions": 0, "status": "RUNTIME_CANARY_PENDING"},
            "authority": {"deployment_authorized": False, "production_approved": False},
            "product_metrics": {
                "owner_active_input_ms": owner_active_input_ms,
                "factory_elapsed_ms": elapsed_ms,
                "owner_decisions": (7 + len(brief.get("selected_optional_modules") or [])) if brief.get("commissioning") else None,
                "owner_revisions": 0,
                "factory_inferred_fields": inferred_fields,
                "commissioning_fields_total": total_commissioning_fields,
                "inferred_percent": round((inferred_fields / total_commissioning_fields) * 100, 1) if total_commissioning_fields else None,
                "owner_correction_rate": 0.0 if brief.get("commissioning") else None,
                "first_pass_vera": True,
                "time_to_usable_local_conversation_ms": elapsed_ms if knowledge_build else None,
            },
            "artifacts": artifact_paths,
            "elapsed_ms": elapsed_ms,
            "next_gate": "CONTAINED_HERMES_LUNA_REVIEW_THEN_X_LINK_ANAM_CANARY",
        }
        write_new(staging / "mission-record.json", record)
        staging.replace(final_root)
        return record
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def list_missions(limit: int = 12) -> list[dict[str, Any]]:
    if not INTERACTIVE_ROOT.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in INTERACTIVE_ROOT.iterdir():
        record_path = path / "mission-record.json"
        if path.is_dir() and not path.name.startswith(".") and record_path.is_file():
            try:
                records.append(load_json(record_path))
            except (OSError, json.JSONDecodeError):
                continue
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records[:limit]
