"""Minimal Factory-intake brief contract for qualified Hunter prospects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from ipaddress import ip_address
from typing import Any, Mapping
from urllib.parse import urlparse


CONTRACT_VERSION = "hunter.factory-intake-brief.v0.7"
SYSTEM_PROMPT_QUESTION = "What should this X-Agent do?"
STATUS = "draft_for_rob_review_no_build_authority"
FACTORY_ROLE = "Operational QA Concierge"


def is_public_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"https", "http"} or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in {None, 80, 443} or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ip_address(host).is_global
        except ValueError:
            return "." in host
    except ValueError:
        return False

ROLE_BY_WEDGE = {
    "emergency_after_hours": "Emergency Intake & Human Handoff Guide",
    "moving_relocation": "Relocation Intake & Estimate Preparation Guide",
    "complex_service_estimate": "Service Qualification & Inspection Preparation Guide",
}
HANDOFF_BY_WEDGE = {
    "emergency_after_hours": "the live or on-call response team",
    "moving_relocation": "the correct branch or human moving estimator",
    "complex_service_estimate": "the appropriate human inspector or estimator",
}
AUDIENCE_BY_WEDGE = {
    "emergency_after_hours": "Prospective and existing customers needing urgent service guidance",
    "moving_relocation": "Prospective moving customers planning a move or requesting an estimate",
    "complex_service_estimate": "Prospective customers evaluating service, inspection, or estimate options",
}
STYLE_BY_WEDGE = {
    "emergency_after_hours": "Calm, concise, safety-first, capable, and reassuring",
    "moving_relocation": "Warm, organized, practical, transparent, and reassuring",
    "complex_service_estimate": "Clear, consultative, precise, transparent, and helpful",
}


@dataclass(frozen=True)
class FactoryIntakeBrief:
    contract_version: str
    system_prompt_question: str
    system_prompt_brief: str
    customer_moment: str
    role_foundation: str
    who_will_use_this: str
    personality_and_communication_style: str
    anything_else_about_company: str
    additional_requirements: tuple[str, ...]
    additional_boundaries: tuple[str, ...]
    appearance_recommendation: str
    appearance_reason: str
    agent_job: str
    preview_scenario: tuple[Mapping[str, str], ...]
    knowledge_direction_only: str
    website_sources_for_factory_review: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("additional_requirements", "additional_boundaries", "preview_scenario", "website_sources_for_factory_review", "evidence_refs"):
            result[key] = list(result[key])
        return result


def build_factory_intake_brief(prospect: Mapping[str, Any]) -> FactoryIntakeBrief:
    wedge = str(prospect.get("gtm_wedge", ""))
    if wedge not in ROLE_BY_WEDGE:
        raise ValueError("qualified prospect must have a supported GTM wedge")
    company = str(prospect.get("company_name", "")).strip()
    moment = str(prospect.get("customer_moment", "")).strip()
    agent_job = str(prospect.get("proposed_x_agent", "")).strip()
    boundaries = tuple(str(x).strip() for x in prospect.get("intentionally_not_included", []) if str(x).strip())
    sources = tuple(str(x.get("url", "")).strip() for x in prospect.get("public_sources", []) if isinstance(x, Mapping) and str(x.get("url", "")).strip())
    conversation = tuple(
        {"role": str(turn.get("role", "")), "text": str(turn.get("text", ""))}
        for turn in prospect.get("example_first_conversation", []) if isinstance(turn, Mapping)
    )
    if not all((company, moment, agent_job)):
        raise ValueError("company, customer moment, and proposed X-Agent are required")
    if len(boundaries) < 2:
        raise ValueError("at least two explicit boundaries are required")
    if len(sources) < 2:
        raise ValueError("at least two public evidence sources are required")
    if not 2 <= len(conversation) <= 5:
        raise ValueError("preview scenario must contain two to five turns")

    handoff = HANDOFF_BY_WEDGE[wedge]
    compact_boundaries = "; ".join(boundaries)
    system_prompt = (
        f"You are {company}'s branded {ROLE_BY_WEDGE[wedge].lower()}. "
        f"Help visitors in this customer moment: {moment} "
        f"Proposed job: {agent_job} "
        "Use only owner-approved company knowledge, ask one useful question at a time, correct misunderstandings, "
        f"and prepare a concise structured summary for {handoff}. "
        "Do not claim that a summary was sent or help was dispatched without a verified connection. "
        f"Stay within these boundaries: {compact_boundaries}."
    )
    requirements = [
        "Answer owner-approved service and process questions",
        "Guide a structured, conversational intake one useful question at a time",
        "Correct missing or contradictory details before handoff",
        f"Prepare a concise summary for {handoff}",
    ]
    if "photo" in agent_job.lower() or "visual" in agent_job.lower() or "image" in agent_job.lower():
        requirements.insert(2, "Guide optional, consented visual intake without making a diagnosis")

    avatar_value = str(prospect.get("avatar_value", "UNKNOWN")).upper()
    appearance = "Mia avatar" if avatar_value == "HIGH" else "Create later"
    company_context = (
        f"Public-source research for {company} ({prospect.get('location', 'service area not stated')}) indicates: "
        f"{str(prospect.get('why_hunter_selected', '')).strip()} "
        "Treat this as research context only; the Factory should review the cited pages before converting any claim into approved company knowledge."
    )

    return FactoryIntakeBrief(
        contract_version=CONTRACT_VERSION,
        system_prompt_question=SYSTEM_PROMPT_QUESTION,
        system_prompt_brief=system_prompt,
        customer_moment=moment,
        role_foundation=FACTORY_ROLE,
        who_will_use_this=AUDIENCE_BY_WEDGE[wedge],
        personality_and_communication_style=STYLE_BY_WEDGE[wedge],
        anything_else_about_company=company_context,
        additional_requirements=tuple(requirements),
        additional_boundaries=boundaries,
        appearance_recommendation=appearance,
        appearance_reason=str(prospect.get("avatar_value_reason", "")).strip(),
        agent_job=agent_job,
        preview_scenario=conversation,
        knowledge_direction_only="Factory should review the cited public company pages and add only owner-approved facts. Hunter does not create or approve Knowledge Bank files.",
        website_sources_for_factory_review=sources,
        evidence_refs=tuple(str(x.get("title", "public source")) for x in prospect.get("public_sources", []) if isinstance(x, Mapping)),
        status=STATUS,
    )


def validate_factory_intake_brief(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "contract_version", "system_prompt_question", "system_prompt_brief", "customer_moment",
        "role_foundation", "who_will_use_this", "personality_and_communication_style",
        "anything_else_about_company", "additional_requirements", "additional_boundaries",
        "appearance_recommendation", "appearance_reason", "agent_job", "preview_scenario",
        "knowledge_direction_only", "website_sources_for_factory_review", "evidence_refs", "status",
    }
    missing = sorted(required - set(value))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors
    extras = sorted(set(value) - required)
    if extras:
        errors.append(f"unknown fields: {', '.join(extras)}")
    array_fields = {"additional_requirements", "additional_boundaries", "preview_scenario", "website_sources_for_factory_review", "evidence_refs"}
    for key in required - array_fields:
        if not isinstance(value[key], str) or not value[key].strip():
            errors.append(f"{key} must be a nonempty string")
    for key in array_fields - {"preview_scenario"}:
        if not isinstance(value[key], list) or any(not isinstance(item, str) or not item.strip() for item in value[key]):
            errors.append(f"{key} must contain nonempty strings")
    if value["contract_version"] != CONTRACT_VERSION:
        errors.append("invalid contract version")
    if value["system_prompt_question"] != SYSTEM_PROMPT_QUESTION:
        errors.append("system prompt question must be canonical")
    if not 250 <= len(str(value["system_prompt_brief"])) <= 1800:
        errors.append("system prompt brief must be 250 to 1800 characters")
    if not isinstance(value["additional_requirements"], list) or len(value["additional_requirements"]) < 3:
        errors.append("at least three additional requirements are required")
    if not isinstance(value["additional_boundaries"], list) or len(value["additional_boundaries"]) < 2:
        errors.append("at least two boundaries are required")
    if value["appearance_recommendation"] not in ("Mia avatar", "Create later", "Stock image", "Text only"):
        errors.append("appearance recommendation must match a Factory option")
    if not isinstance(value["preview_scenario"], list) or not 2 <= len(value["preview_scenario"]) <= 5:
        errors.append("preview scenario must contain two to five turns")
    elif any(not isinstance(turn, Mapping) or turn.get("role") not in ("agent", "visitor") or not isinstance(turn.get("text"), str) or not turn["text"].strip() for turn in value["preview_scenario"]):
        errors.append("preview turns must contain an agent/visitor role and nonempty text")
    if not isinstance(value["website_sources_for_factory_review"], list) or len(value["website_sources_for_factory_review"]) < 2:
        errors.append("at least two website sources are required")
    elif any(not is_public_url(url) for url in value["website_sources_for_factory_review"]):
        errors.append("website sources must be public HTTP(S) URLs without credentials")
    if not isinstance(value["evidence_refs"], list) or len(value["evidence_refs"]) < 2:
        errors.append("at least two evidence references are required")
    if value["status"] != STATUS:
        errors.append("brief must remain a draft with no build authority")
    if "does not create or approve Knowledge Bank files" not in str(value["knowledge_direction_only"]):
        errors.append("knowledge direction must preserve Hunter's non-authoring boundary")
    return errors


def add_factory_briefs(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(payload))
    prospects = result.get("qualified_prospects")
    if not isinstance(prospects, list):
        raise ValueError("qualified_prospects must be an array")
    for prospect in prospects:
        prospect["factory_intake_brief"] = build_factory_intake_brief(prospect).as_dict()
    result["report_revision"] = "hunter.report.v0.7.1-audit"
    result["factory_intake_brief_contract"] = CONTRACT_VERSION
    result["factory_intake_brief_policy"] = {
        "required_for_qualified_prospects": True,
        "first_question": SYSTEM_PROMPT_QUESTION,
        "knowledge_bank_files_created": False,
        "factory_write_performed": False,
        "owner_authorization_implied": False,
    }
    return result


def validate_run_factory_briefs(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("factory_intake_brief_contract") != CONTRACT_VERSION:
        errors.append("run is missing the v0.7 Factory brief contract")
    policy = payload.get("factory_intake_brief_policy")
    if not isinstance(policy, Mapping) or policy.get("required_for_qualified_prospects") is not True or policy.get("first_question") != SYSTEM_PROMPT_QUESTION or any(policy.get(key) is not False for key in ("knowledge_bank_files_created", "factory_write_performed", "owner_authorization_implied")):
        errors.append("run must explicitly deny knowledge authoring, Factory writes, and owner authorization")
    prospects = payload.get("qualified_prospects")
    if not isinstance(prospects, list):
        return errors + ["qualified_prospects must be an array"]
    for index, prospect in enumerate(prospects):
        brief = prospect.get("factory_intake_brief") if isinstance(prospect, Mapping) else None
        if not isinstance(brief, Mapping):
            errors.append(f"prospect {index} is missing factory_intake_brief")
            continue
        errors.extend(f"prospect {index}: {error}" for error in validate_factory_intake_brief(brief))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Add and validate Hunter v0.7 Factory intake briefs")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new revision instead of overwriting evidence")
    with args.input.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    result = add_factory_briefs(payload)
    errors = validate_run_factory_briefs(result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"Hunter v0.7 Factory briefs valid: {len(result['qualified_prospects'])} prospects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
