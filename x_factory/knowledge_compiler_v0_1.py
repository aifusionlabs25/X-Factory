"""Deterministic, source-linked knowledge compilation and owner review."""

from __future__ import annotations

import csv
import io
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.knowledge_loading_v0_1 import (
    KnowledgeLoadingError,
    _package_root,
    package_status,
)
from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256, slugify, write_new


COMPILATION_SCHEMA = ROOT / "contracts/knowledge_compilation.v0.1.schema.json"
REVIEW_SCHEMA = ROOT / "contracts/knowledge_compilation_review.v0.1.schema.json"
COMPILATION_ID = re.compile(r"^kc-[a-z0-9][a-z0-9-]{2,72}$")
MAX_ENTRIES = 200
WEBSITE_QUALITY_VERSION = "WEBSITE_RELEVANCE_V0_1"
WEBSITE_BOILERPLATE = {
    "about", "and more", "book now", "cart", "close", "contact", "contact us",
    "faq", "home", "learn more", "menu", "open menu close menu", "read more",
    "no results match your search try removing a few filters", "shop now", "skip to content", "store", "view fullsize",
}
WEBSITE_CTA = re.compile(
    r"^(?:book|buy|call|click|contact|discover|explore|fill|learn|read|schedule|send|shop|sign up|subscribe|view)(?:\s+\w+){0,8}[.!…]*$",
    re.IGNORECASE,
)
WEBSITE_GENERIC_COPY = re.compile(
    r"(?:designed to meet your needs|move forward with clarity and confidence|"
    r"thoughtful,? human[- ]centered approach|what (?:really )?sets us apart|"
    r"reach us anytime via our contact page|fill out the form now)",
    re.IGNORECASE,
)
PHONE_OR_EMAIL = re.compile(r"(?:\b\d{3}[-. )]+\d{3}[-. ]+\d{4}\b|\b[^\s@]+@[^\s@]+\.[^\s@]+\b)")


class KnowledgeCompilerError(KnowledgeLoadingError):
    pass


def _digest_without(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _validate_compilation(value: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(load_json(COMPILATION_SCHEMA)).validate(value)
    if _digest_without(value, "compilation_sha256") != value["compilation_sha256"]:
        raise KnowledgeCompilerError("Knowledge compilation hash validation failed")
    return value


def _validate_review(value: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(load_json(REVIEW_SCHEMA)).validate(value)
    if _digest_without(value, "review_sha256") != value["review_sha256"]:
        raise KnowledgeCompilerError("Knowledge review hash validation failed")
    return value


def _clean(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def _kind(title: str, statement: str) -> str:
    combined = f"{title} {statement}".casefold()
    if title.rstrip().endswith("?"):
        return "FAQ"
    if any(word in combined for word in ("must ", "never ", "only ", "policy", "require", "prohibit", "cannot ", "may not ")):
        return "POLICY"
    if any(word in combined for word in ("service", "support", "capability", "can help", "offer", "provide")):
        return "CAPABILITY"
    return "REFERENCE"


def _raw_entry(
    *,
    title: str,
    statement: str,
    file_record: dict[str, Any],
    line_start: int,
    line_end: int,
    method: str,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    normalized = _clean(statement, 100000)
    if not normalized:
        return []
    chunks = [normalized[index : index + 1900].strip() for index in range(0, len(normalized), 1900)]
    return [
        {
            "kind": kind or _kind(title, chunk),
            "title": _clean(title or chunk[:90], 300),
            "statement": chunk,
            "source": {
                "file": file_record["original_name"],
                "file_sha256": file_record["sha256"],
                "line_start": max(1, line_start),
                "line_end": max(max(1, line_start), line_end),
            },
            "extraction_method": method,
            "potential_conflict_group": None,
        }
        for chunk in chunks
        if chunk
    ]


def _find_line(lines: list[str], needle: Any) -> int:
    target = _clean(needle, 120).casefold()
    if not target:
        return 1
    for number, line in enumerate(lines, 1):
        if target[:60] in _clean(line, 500).casefold():
            return number
    return 1


def _json_entries(content: str, file_record: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise KnowledgeCompilerError(f"{file_record['original_name']} is not valid JSON: {error.msg}") from error
    lines = content.splitlines() or [content]
    entries: list[dict[str, Any]] = []

    def walk(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            folded = {str(key).casefold(): key for key in node}
            q_key = next((folded[key] for key in ("question", "q") if key in folded), None)
            a_key = next((folded[key] for key in ("answer", "a") if key in folded), None)
            if q_key is not None and a_key is not None and not isinstance(node[a_key], (dict, list)):
                question = _clean(node[q_key], 300)
                answer = _clean(node[a_key], 100000)
                entries.extend(_raw_entry(title=question, statement=answer, file_record=file_record, line_start=_find_line(lines, node[q_key]), line_end=_find_line(lines, node[a_key]), method="STRUCTURED_QA", kind="FAQ"))
                for key, child in node.items():
                    if key not in {q_key, a_key}:
                        walk(child, [*path, str(key)])
                return
            for key, child in node.items():
                walk(child, [*path, str(key)])
        elif isinstance(node, list):
            for index, child in enumerate(node, 1):
                walk(child, [*path, str(index)])
        elif node is not None:
            title = " › ".join(path) or "Value"
            statement = f"{title}: {node}"
            line = _find_line(lines, node)
            entries.extend(_raw_entry(title=title, statement=statement, file_record=file_record, line_start=line, line_end=line, method="STRUCTURED_FIELD"))

    walk(value, [])
    return entries


def _csv_entries(content: str, file_record: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
    except csv.Error as error:
        raise KnowledgeCompilerError(f"{file_record['original_name']} is not valid CSV") from error
    if not reader.fieldnames:
        raise KnowledgeCompilerError(f"{file_record['original_name']} has no CSV header")
    entries: list[dict[str, Any]] = []
    folded = {name.casefold(): name for name in reader.fieldnames if name}
    q_key = next((folded[key] for key in ("question", "q") if key in folded), None)
    a_key = next((folded[key] for key in ("answer", "a") if key in folded), None)
    for index, row in enumerate(rows, 2):
        if q_key and a_key and row.get(q_key) and row.get(a_key):
            entries.extend(_raw_entry(title=row[q_key], statement=row[a_key], file_record=file_record, line_start=index, line_end=index, method="STRUCTURED_QA", kind="FAQ"))
        else:
            fields = [f"{key}: {_clean(value, 500)}" for key, value in row.items() if key and value and _clean(value, 500)]
            if fields:
                entries.extend(_raw_entry(title=f"Row {index - 1}", statement="; ".join(fields), file_record=file_record, line_start=index, line_end=index, method="CSV_ROW"))
    return entries


def _text_entries(content: str, file_record: dict[str, Any]) -> list[dict[str, Any]]:
    # Website provenance is preserved in the package manifest and file header,
    # but it is not itself a customer-facing fact.
    lines = [
        line
        for line in content.splitlines()
        if not re.match(r"^\s*(?:Source URL|Captured):\s*", line, re.IGNORECASE)
    ]
    entries: list[dict[str, Any]] = []
    consumed: set[int] = set()
    for index, line in enumerate(lines):
        question_match = re.match(r"^\s*(?:Q(?:uestion)?\s*[:.-])\s*(.+)$", line, re.IGNORECASE)
        if not question_match:
            continue
        for answer_index in range(index + 1, min(index + 4, len(lines))):
            if not lines[answer_index].strip():
                continue
            answer_match = re.match(r"^\s*(?:A(?:nswer)?\s*[:.-])\s*(.+)$", lines[answer_index], re.IGNORECASE)
            if answer_match:
                entries.extend(_raw_entry(title=question_match.group(1), statement=answer_match.group(1), file_record=file_record, line_start=index + 1, line_end=answer_index + 1, method="STRUCTURED_QA", kind="FAQ"))
                consumed.update({index, answer_index})
            break

    blocks: list[tuple[int, int, list[str]]] = []
    start = None
    block: list[str] = []
    for index, line in enumerate([*lines, ""]):
        if index < len(lines) and index in consumed:
            continue
        if line.strip():
            if start is None:
                start = index + 1
            block.append(line.strip())
        elif block:
            blocks.append((start or 1, index, block))
            start, block = None, []

    heading = ""
    persistent_heading = file_record["original_name"].casefold().startswith("website-")
    for line_start, line_end, block_lines in blocks:
        if len(block_lines) == 1 and re.match(r"^#{1,6}\s+", block_lines[0]):
            heading = re.sub(r"^#{1,6}\s+", "", block_lines[0]).strip()
            continue
        statement_lines = [re.sub(r"^[-*+]\s+", "", item) for item in block_lines if not re.match(r"^#{1,6}\s*$", item)]
        statement = " ".join(statement_lines)
        title = heading or re.sub(r"^#{1,6}\s+", "", statement_lines[0] if statement_lines else "Reference")[:100]
        entries.extend(_raw_entry(title=title, statement=statement, file_record=file_record, line_start=line_start, line_end=max(line_start, line_end), method="EXACT_PARAGRAPH"))
        if not persistent_heading:
            heading = ""
    return entries


def _yaml_entries(content: str, file_record: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(content.splitlines(), 1):
        match = re.match(r"^\s*[-]?\s*([A-Za-z0-9_. -]{1,120}):\s*(.+?)\s*$", line)
        if match and not match.group(2).startswith(("|", ">")):
            title, value = match.groups()
            entries.extend(_raw_entry(title=title, statement=f"{title}: {value}", file_record=file_record, line_start=index, line_end=index, method="STRUCTURED_FIELD"))
    return entries or _text_entries(content, file_record)


def _extract(content: str, file_record: dict[str, Any]) -> list[dict[str, Any]]:
    suffix = Path(file_record["stored_name"]).suffix.lower()
    if suffix == ".json":
        return _json_entries(content, file_record)
    if suffix == ".csv":
        return _csv_entries(content, file_record)
    if suffix in {".yaml", ".yml"}:
        return _yaml_entries(content, file_record)
    return _text_entries(content, file_record)


def _website_category(title: str, statement: str) -> str:
    combined = f"{title} {statement}".casefold()
    if any(token in combined for token in ("hours", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "availability", "open ")):
        return "HOURS_OR_AVAILABILITY"
    if any(token in combined for token in ("address", "located", "location", "phone", "email", "contact", "service area", "serving ")):
        return "LOCATION_OR_CONTACT"
    if any(token in combined for token in ("must ", "never ", "policy", "require", "cannot ", "may not ", "guarantee", "price", "pricing", "refund", "cancel")):
        return "BUSINESS_POLICY"
    if title.rstrip().endswith("?") or any(token in combined for token in ("frequently asked", " faq ")):
        return "FAQ"
    if any(token in combined for token in ("service", "repair", "install", "maintenance", "inspection", "support", "offer", "provide", "specialize")):
        return "SERVICE_OR_CAPABILITY"
    if any(token in combined for token in ("about us", "our team", "our story", "mission", "values", "family owned", "experience")):
        return "BRAND_REFERENCE"
    return "GENERAL_REFERENCE"


def _website_keep(item: dict[str, Any]) -> bool:
    title = re.sub(r"\W+", " ", item["title"].casefold()).strip()
    statement = re.sub(r"\s+", " ", item["statement"]).strip()
    normalized = re.sub(r"\W+", " ", statement.casefold()).strip()
    if not normalized or normalized in WEBSITE_BOILERPLATE or title in WEBSITE_BOILERPLATE:
        return False
    if re.fullmatch(r"(?:cart\s*)?\(?\s*\d+\s*\)?", normalized):
        return False
    if WEBSITE_CTA.fullmatch(statement):
        return False
    if WEBSITE_GENERIC_COPY.search(statement):
        return False
    if (not title or re.fullmatch(r"[.\d\s-]+", title)) and not PHONE_OR_EMAIL.search(statement):
        return False
    if len(normalized) < 28 and not PHONE_OR_EMAIL.search(statement):
        return False
    words = normalized.split()
    if len(words) <= 8 and sum(word in WEBSITE_BOILERPLATE for word in words) >= max(2, len(words) // 2):
        return False
    return True


def _finalize_entries(raw_entries: list[dict[str, Any]], *, website_source: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, dict[str, Any] | None]:
    input_count = len(raw_entries)
    boilerplate_removed = 0
    grouped_fragments = 0
    if website_source:
        retained = []
        for item in raw_entries:
            if _website_keep(item):
                retained.append(item)
            else:
                boilerplate_removed += 1
        raw_entries = retained
        grouped: list[dict[str, Any]] = []
        positions: dict[tuple[str, str, str], int] = {}
        for item in raw_entries:
            normalized_title = re.sub(r"\W+", " ", item["title"].casefold()).strip()
            normalized_statement = re.sub(r"\W+", " ", item["statement"].casefold()).strip()
            heading_based = normalized_title != normalized_statement and not normalized_statement.startswith(normalized_title + " ")
            key = (item["source"]["file"].casefold(), normalized_title, item["kind"])
            if heading_based and key in positions:
                target = grouped[positions[key]]
                candidate = f"{target['statement']}; {item['statement']}"
                if len(candidate) <= 1900:
                    target["statement"] = candidate
                    target["source"]["line_end"] = max(target["source"]["line_end"], item["source"]["line_end"])
                    target["extraction_method"] = "EXACT_PARAGRAPH"
                    continue
            if heading_based:
                positions[key] = len(grouped)
            grouped.append(item)
        grouped_fragments = len(raw_entries) - len(grouped)
        raw_entries = grouped
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for item in raw_entries:
        normalized_title = re.sub(r"\W+", " ", item["title"].casefold()).strip()
        normalized_statement = re.sub(r"\W+", " ", item["statement"].casefold()).strip()
        key = (item["kind"], normalized_statement) if website_source else (
            item["kind"], normalized_title, normalized_statement, item["source"]["file"].casefold(), str(item["source"]["line_start"]),
        )
        if key not in seen:
            if website_source:
                item["relevance"] = {
                    "category": _website_category(item["title"], item["statement"]),
                    "recommended_target": "KNOWLEDGE_BANK_ONLY",
                    "owner_selection_required": True,
                }
            unique.append(item)
            seen.add(key)
    duplicates_removed = len(raw_entries) - len(unique)
    discarded = max(0, len(unique) - MAX_ENTRIES)
    entries = unique[:MAX_ENTRIES]
    for index, item in enumerate(entries, 1):
        item["entry_id"] = f"K-{index:04d}"

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in entries:
        if item["kind"] == "FAQ":
            groups.setdefault(re.sub(r"\W+", " ", item["title"].casefold()).strip(), []).append(item)
    conflicts = []
    for items in groups.values():
        if len(items) > 1 and len({item["statement"].casefold() for item in items}) > 1:
            conflict_id = f"CONFLICT-{len(conflicts) + 1:03d}"
            for item in items:
                item["potential_conflict_group"] = conflict_id
            conflicts.append({"conflict_id": conflict_id, "entry_ids": [item["entry_id"] for item in items], "reason": "The same normalized question has different source answers; owner resolution is required."})
    quality_filter = None
    if website_source:
        categories: dict[str, int] = {}
        for item in entries:
            category = item["relevance"]["category"]
            categories[category] = categories.get(category, 0) + 1
        quality_filter = {
            "version": WEBSITE_QUALITY_VERSION,
            "source_type": "PUBLIC_WEBSITE_CAPTURE",
            "input_entries": input_count,
            "boilerplate_removed": boilerplate_removed,
            "grouped_fragments": grouped_fragments,
            "duplicates_removed": duplicates_removed,
            "kept_entries": len(entries),
            "categories": categories,
            "system_prompt_candidates": 0,
        }
    return entries, conflicts, discarded, quality_filter


def _compilation_root(package_id: str, compilation_id: str) -> Path:
    if not COMPILATION_ID.fullmatch(compilation_id):
        raise KnowledgeCompilerError("Invalid knowledge compilation ID")
    return _package_root(package_id) / "derived/compilations" / compilation_id


def _latest_review(root: Path, compilation: dict[str, Any]) -> dict[str, Any] | None:
    review_paths = sorted((root / "reviews").glob("*.json"), reverse=True) if (root / "reviews").is_dir() else []
    if not review_paths:
        return None
    review = _validate_review(load_json(review_paths[0]))
    if review["compilation_id"] != compilation["compilation_id"] or review["compilation_sha256"] != compilation["compilation_sha256"]:
        raise KnowledgeCompilerError("Knowledge review no longer matches its compilation")
    return review


def get_compilation(package_id: str, compilation_id: str | None = None) -> dict[str, Any]:
    package = package_status(package_id)
    parent = _package_root(package_id) / "derived/compilations"
    roots = [_compilation_root(package_id, compilation_id)] if compilation_id else sorted((item for item in parent.iterdir() if item.is_dir()), reverse=True) if parent.is_dir() else []
    if not roots or not (roots[0] / "compilation.v0.1.json").is_file():
        raise KnowledgeCompilerError("Knowledge package has not been compiled")
    compilation = _validate_compilation(load_json(roots[0] / "compilation.v0.1.json"))
    if compilation["package_id"] != package_id or compilation["source_manifest_sha256"] != package["manifest_sha256"]:
        raise KnowledgeCompilerError("Knowledge compilation source binding failed")
    return {**compilation, "latest_review": _latest_review(roots[0], compilation)}


def compilation_summary(package_id: str) -> dict[str, Any] | None:
    try:
        compilation = get_compilation(package_id)
    except KnowledgeCompilerError as error:
        if "has not been compiled" in str(error):
            return None
        raise
    review = compilation["latest_review"]
    return {
        "compilation_id": compilation["compilation_id"],
        "compilation_sha256": compilation["compilation_sha256"],
        "status": review["status"] if review else compilation["status"],
        "entries": len(compilation["entries"]),
        "conflicts": len(compilation["conflicts"]),
        "approved_entries": review["approved_count"] if review else 0,
        "rejected_entries": review["rejected_count"] if review else 0,
        "review_id": review["review_id"] if review else None,
        "review_sha256": review["review_sha256"] if review else None,
        "quality_filter_version": compilation.get("quality_filter", {}).get("version"),
        "requires_recapture": package_status(package_id)["authority"]["source"] == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE" and compilation.get("quality_filter", {}).get("version") != WEBSITE_QUALITY_VERSION,
    }


def compile_package(package_id: str) -> dict[str, Any]:
    package = package_status(package_id)
    if package["effective_status"] != "OWNER_APPROVED_FOR_COMMISSIONING" or not package["approval"]:
        raise KnowledgeCompilerError("Owner approval is required before knowledge compilation")
    try:
        existing = get_compilation(package_id)
        website_source = package["authority"]["source"] == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE"
        quality_current = existing.get("quality_filter", {}).get("version") == WEBSITE_QUALITY_VERSION
        if existing["source_manifest_sha256"] == package["manifest_sha256"]:
            if website_source and not quality_current:
                raise KnowledgeCompilerError("This website package predates the relevance-aware capture format; capture a clean copy from the website before review")
            return existing
    except KnowledgeCompilerError as error:
        if "has not been compiled" not in str(error):
            raise

    raw_entries: list[dict[str, Any]] = []
    root = _package_root(package_id)
    for file_record in package["files"]:
        data = (root / "files" / file_record["stored_name"]).read_bytes()
        if sha256(data) != file_record["sha256"]:
            raise KnowledgeCompilerError("Knowledge source changed before compilation")
        raw_entries.extend(_extract(data.decode("utf-8"), file_record))
    website_source = package["authority"]["source"] == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE"
    entries, conflicts, discarded, quality_filter = _finalize_entries(raw_entries, website_source=website_source)
    if not entries:
        raise KnowledgeCompilerError("No reviewable knowledge entries could be extracted from this package")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    compilation_id = f"kc-{slugify(package_id[3:])[:34]}-{stamp}-{secrets.token_hex(3)}"
    compilation = {
        "schema_version": "0.1",
        "compilation_id": compilation_id,
        "package_id": package_id,
        "status": "COMPILED_PENDING_OWNER_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256": package["manifest_sha256"],
        "entries": entries,
        "conflicts": conflicts,
        "truncation": {"entry_limit": MAX_ENTRIES, "discarded_entries": discarded},
        "authority": {
            "method": "LOCAL_DETERMINISTIC_EXTRACTION",
            "semantic_inference": False,
            "runtime_truth": False,
            "provider_calls": 0,
            "owner_review_required": True,
            "production_approved": False,
        },
    }
    if quality_filter is not None:
        compilation["quality_filter"] = quality_filter
    compilation["compilation_sha256"] = _digest_without(compilation, "compilation_sha256")
    _validate_compilation(compilation)
    target = _compilation_root(package_id, compilation_id)
    target.mkdir(parents=True)
    try:
        write_new(target / "compilation.v0.1.json", compilation)
    except Exception:
        import shutil

        if target.exists():
            shutil.rmtree(target)
        raise
    return {**compilation, "latest_review": None}


def review_compilation(package_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"compilation_id", "decisions"}:
        raise KnowledgeCompilerError("Review request accepts only compilation_id and decisions")
    compilation = get_compilation(package_id, str(value.get("compilation_id") or ""))
    package = package_status(package_id)
    if package["authority"]["source"] == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE" and compilation.get("quality_filter", {}).get("version") != WEBSITE_QUALITY_VERSION:
        raise KnowledgeCompilerError("This website compilation predates the relevance filter and cannot be finalized; capture a clean copy from the website first")
    decisions = value.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise KnowledgeCompilerError("Review every compiled entry before finalizing")
    expected = {item["entry_id"] for item in compilation["entries"]}
    normalized = []
    seen: set[str] = set()
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != {"entry_id", "decision"}:
            raise KnowledgeCompilerError("Each review decision needs exactly entry_id and decision")
        entry_id = str(decision["entry_id"])
        disposition = str(decision["decision"])
        if entry_id in seen or entry_id not in expected or disposition not in {"APPROVE", "REJECT"}:
            raise KnowledgeCompilerError("Knowledge review contains an invalid or duplicate decision")
        normalized.append({"entry_id": entry_id, "decision": disposition})
        seen.add(entry_id)
    if seen != expected:
        raise KnowledgeCompilerError("Every compiled entry must receive an approve or reject decision")
    normalized.sort(key=lambda item: item["entry_id"])
    approved_ids = {item["entry_id"] for item in normalized if item["decision"] == "APPROVE"}
    for conflict in compilation["conflicts"]:
        if len(approved_ids.intersection(conflict["entry_ids"])) > 1:
            raise KnowledgeCompilerError(f"Resolve {conflict['conflict_id']} by approving at most one conflicting entry")
    approved_count = sum(item["decision"] == "APPROVE" for item in normalized)
    rejected_count = len(normalized) - approved_count
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    review_id = f"kr-{slugify(compilation['compilation_id'][3:])[:34]}-{stamp}-{secrets.token_hex(3)}"
    review = {
        "schema_version": "0.1",
        "review_id": review_id,
        "package_id": package_id,
        "compilation_id": compilation["compilation_id"],
        "status": "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD" if approved_count else "OWNER_REVIEW_COMPLETE_NO_APPROVED_KNOWLEDGE",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "compilation_sha256": compilation["compilation_sha256"],
        "decisions": normalized,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "owner_attestation": "I reviewed every source-linked proposed entry and approve only the entries explicitly marked APPROVE for this local instance-build input.",
        "authority": {
            "instance_build_input": True,
            "runtime_installation": False,
            "provider_calls": 0,
            "deployment_authorized": False,
            "production_approved": False,
        },
    }
    review["review_sha256"] = _digest_without(review, "review_sha256")
    _validate_review(review)
    target = _compilation_root(package_id, compilation["compilation_id"]) / "reviews" / f"{review_id}.json"
    write_new(target, review)
    return get_compilation(package_id, compilation["compilation_id"])
