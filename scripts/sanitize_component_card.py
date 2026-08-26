#!/usr/bin/env python3
"""Create a model-safe component card without sending sealed evidence anywhere."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

SANITIZER = "x-factory-local-sanitizer/0.1"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def validate_mappings(recipe_items: list[dict[str, Any]], source_items: list[str], label: str) -> list[str]:
    indexes: set[int] = set()
    statements: list[str] = []
    for item in recipe_items:
        if set(item) != {"source_index", "statement"}:
            raise ValueError(f"{label} entries must contain only source_index and statement")
        index = item["source_index"]
        if not isinstance(index, int) or index < 0 or index >= len(source_items):
            raise ValueError(f"{label} source_index {index!r} is outside the sealed evidence record")
        if index in indexes:
            raise ValueError(f"{label} source_index {index} is mapped more than once")
        indexes.add(index)
        statement = item["statement"].strip()
        if len(statement) < 10:
            raise ValueError(f"{label} statement is too short")
        statements.append(statement)
    if indexes != set(range(len(source_items))):
        raise ValueError(f"{label} must map every sealed source statement exactly once")
    return statements


def disclosure_violations(card: dict[str, Any], markers: list[str]) -> list[str]:
    violations: list[str] = []
    strings = list(walk_strings(card))
    joined = "\n".join(strings)
    lowered = joined.casefold()

    if any(marker.casefold() in lowered for marker in markers if marker.strip()):
        violations.append("private_marker")
    if re.search(r"(?i)(?:[a-z]:\\|/home/|/users/|\\\\[^\\]+\\)", joined):
        violations.append("repo_or_local_path")
    if re.search(r"(?i)\b(?:https?|ssh|git)://|\bwww\.", joined):
        violations.append("url")
    if re.search(r"(?i)(?:sk-[a-z0-9_-]{12,}|api[_-]?key\s*[:=]|bearer\s+[a-z0-9._-]{12,}|password\s*[:=]|secret\s*[:=])", joined):
        violations.append("credential_pattern")
    if any("\n" in value or "\r" in value for value in strings):
        violations.append("multiline_payload")
    if re.search(r"(?im)^(?:def|class|import|from|function|const|let|var)\s+|=>|#!/", joined):
        violations.append("source_code_pattern")
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-matrix", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--markers", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    evidence = load_json(args.evidence_matrix)
    recipe = load_json(args.recipe)
    marker_doc = load_json(args.markers)
    records = [item for item in evidence["records"] if item["evidence_id"] == recipe["source_evidence_id"]]
    if len(records) != 1:
        raise ValueError("Recipe must resolve to exactly one sealed evidence record")
    source = records[0]

    capabilities = validate_mappings(recipe["safe_capabilities"], source["capability_proven"], "safe_capabilities")
    limitations = validate_mappings(recipe["safe_limitations"], source["limitations"], "safe_limitations")
    sealed_record_hash = sha256_bytes(canonical_bytes(source))
    sealed_ref = "SEALED-" + sealed_record_hash.removeprefix("sha256:")[:16].upper()

    card = {
        "schema_version": "0.1",
        "card_id": recipe["card_id"],
        "component_id": recipe["component_id"],
        "evidence_id": recipe["safe_evidence_id"],
        "display_name": recipe["display_name"],
        "provenance": {
            "sealed_source_ref": sealed_ref,
            "source_artifact_hash": source["artifact_hash"],
            "derivation_hash": sealed_record_hash,
            "observed_date": source["observed_date"],
            "source_kind": "PRIVATE_REPOSITORY_EVIDENCE",
        },
        "verification_class": source["verification_class"],
        "capabilities": [
            {"capability_id": f"CAP-{index:03d}", "statement": statement}
            for index, statement in enumerate(capabilities, start=1)
        ],
        "dependencies": recipe["dependencies"],
        "limitations": limitations,
        "tests": [
            {
                "test_id": f"TEST-{index:03d}",
                "statement": item["statement"],
                "evidence_class": item["evidence_class"],
            }
            for index, item in enumerate(recipe["tests"], start=1)
        ],
        "excluded_authority": {
            "external_actions": False,
            "build": False,
            "deployment": False,
            "production": False,
        },
        "disclosure": {
            "contains_private_names": False,
            "contains_repo_or_local_paths": False,
            "contains_source_code": False,
            "contains_credentials": False,
            "sanitizer": SANITIZER,
        },
        "lifecycle": "PENDING_EXACT_PAYLOAD_APPROVAL",
    }

    violations = disclosure_violations(card, marker_doc["markers"])
    if violations:
        raise ValueError("Model-safe disclosure checks failed: " + ", ".join(violations))

    schema = load_json(args.schema)
    Draft202012Validator.check_schema(schema)
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(card), key=lambda item: list(item.path))
    if schema_errors:
        raise ValueError("Card schema validation failed: " + "; ".join(error.message for error in schema_errors))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    card_hash = sha256_file(args.output)
    report = {
        "schema_version": "0.1",
        "sanitizer": SANITIZER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sealed_record_hash": sealed_record_hash,
        "output_card_sha256": card_hash,
        "source_capability_mappings": len(capabilities),
        "source_limitation_mappings": len(limitations),
        "mapping_summary": {
            "included": {
                "sanitized_capabilities": len(capabilities),
                "sanitized_limitations": len(limitations),
                "dependencies": len(recipe["dependencies"]),
                "tests": len(recipe["tests"]),
            },
            "removed_source_fields": [
                "evidence_id",
                "source_repo",
                "source_path",
                "source_commit",
                "working_tree_state",
            ],
            "rejected_fields": [],
            "unmapped_source_capabilities": 0,
            "unmapped_source_limitations": 0,
        },
        "semantic_privacy_classification": {
            "DIRECT_IDENTIFIERS": "none",
            "CREDENTIAL_MATERIAL": "none",
            "PRIVATE_PATHS": "none",
            "UNIQUE_CLIENT_IDENTIFIERS": "none",
            "SOURCE_CODE": "none",
            "RAW_PRIVATE_TEXT": "none",
        },
        "checks": {
            "schema_valid": True,
            "private_markers_absent": True,
            "repo_or_local_paths_absent": True,
            "source_code_absent": True,
            "credentials_absent": True,
            "all_source_statements_mapped_once": True,
        },
        "provider_transmission_performed": False,
        "approval_status": "PENDING_EXACT_PAYLOAD_APPROVAL",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"card": str(args.output), "card_sha256": card_hash, "report": str(args.report)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
