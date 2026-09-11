"""Validate Hunter v0.4 three-wedge commercial qualification artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .scoring_v04 import (
    CONTRACT_VERSION,
    CommercialPenaltiesV04,
    ScoreComponentsV04,
    compute_score_v04,
    qualification_band_v04,
)


WEDGES = {"emergency_after_hours", "moving_relocation", "complex_service_estimate"}
AVATAR_VALUES = {"HIGH", "MEDIUM", "LOW"}
DEMO_VALUES = {"YES", "MAYBE", "NO"}
STRENGTH_VALUES = {"HIGH", "MEDIUM", "LOW"}
GATE_FIELDS = {
    "observable_friction", "economic_value", "structured_intake", "human_handoff",
    "public_knowledge", "conversational_advantage", "presence_human_interaction_value",
}
STRENGTH_METRIC = {
    "emergency_after_hours": "after_hours_urgency_strength",
    "moving_relocation": "intake_complexity_strength",
    "complex_service_estimate": "qualification_complexity_strength",
}
PROHIBITED_SOURCE_FAMILIES = {
    "reddit", "anonymous_forum", "company_careers", "company_ats", "job_board", "employment_listing"
}
PROHIBITED_URL_TOKENS = (
    "reddit.com", "/careers", "/career", "/jobs", "/job/", "greenhouse.io", "lever.co"
)
REQUIRED_FIELDS = {
    "prospect_id", "company_name", "website", "vertical", "location", "gtm_wedge",
    "verification_status", "stage", "why_hunter_selected", "customer_moment",
    "proposed_x_agent", "example_first_conversation", "avatar_value", "avatar_value_reason",
    "current_factory_fit", "intentionally_not_included", "public_sources", "browser_audit",
    "qualification_gate", "qualification_gate_count", "wedge_strength", "score_components",
    "score_rationale", "penalties", "raw_score", "penalty_log", "overall_score",
    "overall_band", "rob_demo_recommendation", "rob_demo_reason", "why_rob_should_care",
    "authority",
}


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def validate_prospect(prospect: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pid = str(prospect.get("prospect_id", "<unknown>"))
    missing = sorted(REQUIRED_FIELDS - set(prospect))
    if missing:
        errors.append(f"{pid}: missing fields: {', '.join(missing)}")

    wedge = prospect.get("gtm_wedge")
    if wedge not in WEDGES:
        errors.append(f"{pid}: invalid gtm_wedge")
    if not _domain(str(prospect.get("website", ""))):
        errors.append(f"{pid}: website must be an absolute public URL")

    sources = prospect.get("public_sources")
    if not isinstance(sources, list) or len(sources) < 2:
        errors.append(f"{pid}: at least two public sources are required")
    else:
        first_party = False
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"{pid}: public_sources[{index}] must be an object")
                continue
            required = {"title", "url", "source_family", "observed_on", "claim"}
            if required - set(source):
                errors.append(f"{pid}: public_sources[{index}] is incomplete")
            family = source.get("source_family")
            url = str(source.get("url", ""))
            if family in PROHIBITED_SOURCE_FAMILIES or any(t in url.lower() for t in PROHIBITED_URL_TOKENS):
                errors.append(f"{pid}: prohibited source in public_sources[{index}]")
            if not _domain(url):
                errors.append(f"{pid}: invalid source URL in public_sources[{index}]")
            first_party = first_party or family == "company_website"
        if not first_party:
            errors.append(f"{pid}: first-party company evidence is required")

    audit = prospect.get("browser_audit")
    if not isinstance(audit, dict) or not audit.get("rendered_page_checked"):
        errors.append(f"{pid}: rendered intake page audit is required")

    gate = prospect.get("qualification_gate")
    if not isinstance(gate, dict) or set(gate) != GATE_FIELDS:
        errors.append(f"{pid}: qualification_gate must contain exactly the seven v0.4 fields")
    else:
        if any(not isinstance(value, bool) for value in gate.values()):
            errors.append(f"{pid}: qualification gate values must be boolean")
        count = sum(value is True for value in gate.values())
        if prospect.get("qualification_gate_count") != count:
            errors.append(f"{pid}: qualification_gate_count mismatch")
        if count < 4:
            errors.append(f"{pid}: primary shortlist requires at least four of seven qualification gates")

    strength = prospect.get("wedge_strength")
    if not isinstance(strength, dict):
        errors.append(f"{pid}: wedge_strength must be an object")
    elif wedge in WEDGES:
        if strength.get("metric") != STRENGTH_METRIC[wedge]:
            errors.append(f"{pid}: wedge_strength metric does not match wedge")
        if strength.get("value") not in STRENGTH_VALUES or not strength.get("reason"):
            errors.append(f"{pid}: invalid wedge strength")
        if wedge == "emergency_after_hours" and strength.get("value") == "HIGH":
            if not strength.get("direct_evidence_urls") or not strength.get("direct_evidence_claim"):
                errors.append(f"{pid}: HIGH emergency strength requires direct public evidence")

    avatar = prospect.get("avatar_value")
    if avatar not in AVATAR_VALUES or not prospect.get("avatar_value_reason"):
        errors.append(f"{pid}: avatar value and reason are required")

    conversation = prospect.get("example_first_conversation")
    if not isinstance(conversation, list) or not 2 <= len(conversation) <= 5:
        errors.append(f"{pid}: example_first_conversation must contain two to five turns")

    try:
        components = ScoreComponentsV04.from_mapping(prospect.get("score_components", {}))
        penalties = CommercialPenaltiesV04.from_mapping(prospect.get("penalties", {}))
        raw, score, log = compute_score_v04(components, penalties)
        if prospect.get("raw_score") != raw:
            errors.append(f"{pid}: raw_score mismatch; expected {raw}")
        if prospect.get("overall_score") != score:
            errors.append(f"{pid}: overall_score mismatch; expected {score}")
        if prospect.get("penalty_log") != log:
            errors.append(f"{pid}: penalty_log mismatch")
        band = qualification_band_v04(score)
        if prospect.get("overall_band") != band:
            errors.append(f"{pid}: overall_band mismatch; expected {band}")
        if penalties.speculative_pain:
            errors.append(f"{pid}: speculative pain cannot qualify for the primary shortlist")
        if penalties.human_replacement:
            errors.append(f"{pid}: human-replacement thesis cannot qualify for the primary shortlist")
    except (TypeError, ValueError) as exc:
        errors.append(f"{pid}: invalid scoring data: {exc}")

    demo = prospect.get("rob_demo_recommendation")
    if demo not in DEMO_VALUES or not prospect.get("rob_demo_reason"):
        errors.append(f"{pid}: demo recommendation and reason are required")
    elif demo == "YES":
        if prospect.get("overall_score", 0) < 80:
            errors.append(f"{pid}: demo YES requires score >= 80")
        if avatar == "LOW":
            errors.append(f"{pid}: demo YES requires MEDIUM or HIGH avatar value")
        if isinstance(strength, dict) and strength.get("value") == "LOW":
            errors.append(f"{pid}: demo YES requires MEDIUM or HIGH wedge strength")

    if prospect.get("authority") != "advisory_only_no_outreach":
        errors.append(f"{pid}: authority boundary is missing")
    return errors


def validate_run(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "hunter.run.v0.4":
        errors.append("schema_version must be hunter.run.v0.4")
    if payload.get("scoring_contract") != CONTRACT_VERSION:
        errors.append(f"scoring_contract must be {CONTRACT_VERSION}")
    if payload.get("experiment") != "three_wedge_national_gtm":
        errors.append("experiment must be three_wedge_national_gtm")
    if payload.get("employment_thesis_policy") != "excluded":
        errors.append("employment_thesis_policy must be excluded")
    if not isinstance(payload.get("preserved_evidence"), list) or len(payload["preserved_evidence"]) < 3:
        errors.append("preserved_evidence must reference prior runs")

    prospects = payload.get("qualified_prospects")
    if not isinstance(prospects, list):
        return errors + ["qualified_prospects must be an array"]
    seen: set[str] = set()
    prior_score = 101
    for prospect in prospects:
        if not isinstance(prospect, dict):
            errors.append("every qualified prospect must be an object")
            continue
        errors.extend(validate_prospect(prospect))
        domain = _domain(str(prospect.get("website", "")))
        if domain in seen:
            errors.append(f"duplicate prospect domain: {domain}")
        seen.add(domain)
        score = prospect.get("overall_score")
        if isinstance(score, int):
            if score > prior_score:
                errors.append("qualified_prospects must be sorted by descending overall_score")
            prior_score = score

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or metrics.get("qualified_prospects") != len(prospects):
        errors.append("metrics.qualified_prospects must match the shortlist")
    comparisons = payload.get("wedge_comparison")
    if not isinstance(comparisons, list) or {c.get("wedge") for c in comparisons if isinstance(c, dict)} != WEDGES:
        errors.append("wedge_comparison must contain all three wedges")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    with args.path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    errors = validate_run(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Hunter v0.4 artifact valid: {len(payload['qualified_prospects'])} prospects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
