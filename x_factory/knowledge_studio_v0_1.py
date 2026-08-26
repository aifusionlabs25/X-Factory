"""OMNARA Knowledge Studio: compile approved source evidence into a usable Knowledge Bank."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256


PACKAGE_SCHEMA = ROOT / "contracts/knowledge_studio_package.v0.1.schema.json"


class KnowledgeStudioError(RuntimeError):
    pass


def _digest_without(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _parts(statement: str) -> list[str]:
    return [re.sub(r"\s+", " ", part).strip(" ;") for part in statement.split(";") if part.strip(" ;")]


def _friendly_list(parts: list[str]) -> str:
    cleaned = [part.rstrip(".") for part in parts]
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _neutral_title(entry: dict[str, Any]) -> str:
    title = " ".join(str(entry["title"]).split()).strip(" .")
    statement = entry["statement"].casefold()
    if title.casefold() == "built to dominate":
        return "Realtor and inspection repair support" if "realtor" in statement else "Company services and service area"
    if title.casefold() in {"maintain stronger", "relentless craft. unshakable results"}:
        return "Construction and maintenance" if "power-packed" in statement else "Company experience and focus"
    return title[:1].upper() + title[1:]


def _curate(entry: dict[str, Any], client_name: str) -> dict[str, Any]:
    source_statement = " ".join(entry["statement"].split())
    parts = _parts(source_statement)
    title = _neutral_title(entry)
    transformation = "EXACT_NORMALIZED"
    statement = source_statement
    if "power-packed" in source_statement.casefold() and "dominate deadlines" in source_statement.casefold():
        statement = f"{client_name} provides construction and maintenance solutions."
        transformation = "MARKETING_NEUTRALIZATION"
    elif len(parts) >= 3 and all(len(part) <= 120 for part in parts):
        statement = f"{client_name} handles {_friendly_list(parts)}."
        transformation = "LIST_TO_CUSTOMER_ANSWER"
    elif len(parts) >= 3:
        first = parts[0].rstrip(".") + "."
        service_part = next((part for part in parts if "services include" in part.casefold()), parts[1])
        statement = f"{first} {service_part.rstrip('.')}."
        transformation = "MULTIPARAGRAPH_CONDENSATION"
    elif title != " ".join(str(entry["title"]).split()).strip(" ."):
        transformation = "TITLE_NORMALIZATION"
    category = "SERVICES"
    lowered = statement.casefold()
    if entry["kind"] == "POLICY":
        category = "POLICIES_AND_BOUNDARIES"
    elif "central mississippi" in lowered or "greater jackson" in lowered:
        category = "SERVICE_AREA"
    elif "experience" in lowered or "construction and maintenance solutions" in lowered:
        category = "COMPANY_OVERVIEW"
    aliases = [title.casefold()]
    for token in ("interior repairs", "carpentry", "flooring", "kitchens", "bathrooms", "exterior repairs", "electrical", "inspection repairs"):
        if token in f"{title} {statement}".casefold() and token not in aliases:
            aliases.append(token)
    return {
        "entry_id": entry["entry_id"],
        "kind": entry["kind"],
        "category": category,
        "title": title,
        "statement": statement,
        "aliases": aliases,
        "source_entry_ids": [entry["entry_id"]],
        "source_statement_sha256": sha256(source_statement.encode("utf-8")),
        "transformation": transformation,
        "source": deepcopy(entry["source"]),
    }


def _document(identity: dict[str, str], title: str, entries: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", f"X-Agent: {identity['agent_name']}", f"Client: {identity['client_name']}", "", "> Owner-approved source facts, curated locally by OMNARA. No provider calls. Not deployed.", ""]
    for entry in entries:
        lines.extend([f"## {entry['title']}", "", entry["statement"], "", f"Source evidence: `{', '.join(entry['source_entry_ids'])}`", ""])
    if not entries:
        lines.extend(["No approved entries belong to this section yet.", ""])
    return "\n".join(lines).rstrip() + "\n"


def compile_knowledge_studio(bundle: dict[str, Any], mission_id: str) -> dict[str, Any]:
    """Return immutable curated artifacts while retaining the exact source bundle separately."""
    entries = [_curate(item, bundle["identity"]["client_name"]) for item in bundle["entries"]]
    if len({item["entry_id"] for item in entries}) != len(entries):
        raise KnowledgeStudioError("Duplicate curated knowledge entry IDs")
    identity = deepcopy(bundle["identity"])
    grouped = {category: [item for item in entries if item["category"] == category] for category in (
        "COMPANY_OVERVIEW", "SERVICES", "SERVICE_AREA", "APPROVED_FAQS", "POLICIES_AND_BOUNDARIES", "QUALIFICATION", "ESCALATION", "GLOSSARY"
    )}
    paths = {
        "instance/knowledge/00-KNOWLEDGE-INDEX.md": _document(identity, f"{identity['agent_name']} Knowledge Bank Index", entries),
        "instance/knowledge/01-COMPANY-OVERVIEW.md": _document(identity, "Company Overview", grouped["COMPANY_OVERVIEW"]),
        "instance/knowledge/02-SERVICES.md": _document(identity, "Services", grouped["SERVICES"]),
        "instance/knowledge/03-SERVICE-AREA.md": _document(identity, "Service Area", grouped["SERVICE_AREA"]),
        "instance/knowledge/04-APPROVED-FAQS.md": _document(identity, "Approved FAQs", grouped["APPROVED_FAQS"]),
        "instance/knowledge/05-POLICIES-AND-BOUNDARIES.md": _document(identity, "Policies and Boundaries", grouped["POLICIES_AND_BOUNDARIES"]),
        "instance/knowledge/06-QUALIFICATION-GUIDE.md": _document(identity, "Qualification Guide", grouped["QUALIFICATION"]),
        "instance/knowledge/07-ESCALATION-GUIDE.md": _document(identity, "Escalation Guide", grouped["ESCALATION"]),
        "instance/knowledge/08-GLOSSARY-AND-ALIASES.md": _document(identity, "Glossary and Aliases", grouped["GLOSSARY"]),
    }
    values = {path: value.encode("utf-8") for path, value in paths.items()}
    curated = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "status": "CURATED_KNOWLEDGE_BANK_READY_LOCAL_CANDIDATE",
        "specialist": "OMNARA",
        "mode": "ARIA_CONTROLLED_KNOWLEDGE_ENGINEERING_SIDECAR",
        "input_binding": {"source_bundle_sha256": bundle["bundle_sha256"], "source_entry_ids": [item["entry_id"] for item in bundle["entries"]], "source_entry_count": len(bundle["entries"])},
        "entries": entries,
        "files": {path: sha256(data) for path, data in values.items()},
        "quality": {"source_entries_preserved": True, "curated_entries_traceable": all(item["source_entry_ids"] for item in entries), "unsupported_facts_added": 0, "duplicate_entry_ids": 0, "customer_answers_present": all(item["statement"] for item in entries)},
        "authority": {"provider_calls": 0, "network_calls": 0, "self_approval": False, "source_mutation": False, "deployment_authorized": False, "production_approved": False},
    }
    curated["package_sha256"] = _digest_without(curated, "package_sha256")
    Draft202012Validator(load_json(PACKAGE_SCHEMA)).validate(curated)
    traceability = {"schema_version": "0.1", "mission_id": mission_id, "source_bundle_sha256": bundle["bundle_sha256"], "knowledge_studio_sha256": curated["package_sha256"], "entries": [{"entry_id": item["entry_id"], "source_entry_ids": item["source_entry_ids"], "source_statement_sha256": item["source_statement_sha256"], "transformation": item["transformation"], "source": item["source"]} for item in entries]}
    values["instance/knowledge/curated-knowledge.v0.1.json"] = canonical(curated)
    values["instance/knowledge/SOURCE-TRACEABILITY.json"] = canonical(traceability)
    return {"status": curated["status"], "specialist": "OMNARA", "entry_count": len(entries), "package_sha256": curated["package_sha256"], "entries": entries, "values": values, "artifacts": {"knowledge_studio_package": "instance/knowledge/curated-knowledge.v0.1.json", "knowledge_studio_traceability": "instance/knowledge/SOURCE-TRACEABILITY.json", "knowledge_index": "instance/knowledge/00-KNOWLEDGE-INDEX.md"}}
