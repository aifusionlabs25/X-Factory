#!/usr/bin/env python3
"""Deterministic Phase 0 contract and fixture validation for Hermes X Factory."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate(instance_path: Path, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(load_json(instance_path)), key=lambda item: list(item.path))]


def negative_fixture_findings(root: Path) -> list[dict[str, str]]:
    intake = load_json(root / "fixtures" / "good" / "intake.json")
    candidate = load_json(root / "fixtures" / "bad" / "x_agent_blueprint.bad.json")
    evidence = load_json(root / "evidence" / "evidence_matrix.v0.1.json")
    evidence_ids = {record["evidence_id"] for record in evidence["records"]}
    text = json.dumps(candidate, sort_keys=True).lower()
    findings: list[dict[str, str]] = []

    contaminants = [term for term in ("jordan", "harbor lane") if term in text]
    if contaminants:
        findings.append({"gate": "contamination_control", "finding": "Reference-client contamination: " + ", ".join(contaminants)})

    missing_refs = sorted({ref for component in candidate["components"]["selected"] for ref in component["evidence_refs"] if ref not in evidence_ids})
    if missing_refs:
        findings.append({"gate": "evidence_traceability", "finding": "Unknown evidence references: " + ", ".join(missing_refs)})

    explicit = {item.lower() for item in intake["must_have_capabilities"]}
    selected = {item.lower() for item in candidate["capabilities"]["required"]}
    gratuitous = sorted(selected - explicit - {"faq", "qualification", "notes", "handoff"})
    if gratuitous:
        findings.append({"gate": "minimum_architecture", "finding": "Unjustified capabilities: " + ", ".join(gratuitous)})

    prohibited = {item.lower() for item in intake["never_do"]}
    allowed = {item.lower() for item in candidate["tools_and_actions"]["allowed"]}
    conflicts = sorted(action for action in allowed if any(term in action for term in ("email", "book", "crm")))
    if conflicts or prohibited.intersection(allowed):
        findings.append({"gate": "intent_fidelity", "finding": "Candidate permits owner-prohibited actions: " + ", ".join(conflicts or sorted(prohibited.intersection(allowed)))})

    if not candidate["evaluation_plan"]["scenarios"] or not candidate["evaluation_plan"]["hard_rules"]:
        findings.append({"gate": "testability", "finding": "Scenarios and hard rules are missing"})

    if any("book" in item.lower() or "availability" in item.lower() for item in candidate["inferred_requirements"] + candidate["objectives"]["success_outcomes"]):
        findings.append({"gate": "no_invented_facts", "finding": "Booking/availability capability was invented without owner authority"})

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()

    validations = [
        (root / "fixtures" / "good" / "intake.json", root / "contracts" / "intake.v0.1.schema.json"),
        (root / "evidence" / "evidence_matrix.v0.1.json", root / "contracts" / "evidence_matrix.v0.1.schema.json"),
        (root / "catalog" / "component_catalog.v0.1.json", root / "contracts" / "component_catalog.v0.1.schema.json"),
        (root / "fixtures" / "bad" / "x_agent_blueprint.bad.json", root / "contracts" / "x_agent_blueprint.v0.1.schema.json"),
    ]

    schema_results = []
    for instance, schema in validations:
        errors = validate(instance, schema)
        schema_results.append({"instance": str(instance.relative_to(root)), "schema": str(schema.relative_to(root)), "valid": not errors, "errors": errors})

    findings = negative_fixture_findings(root)
    expected_gates = {"contamination_control", "evidence_traceability", "minimum_architecture", "intent_fidelity", "testability", "no_invented_facts"}
    found_gates = {finding["gate"] for finding in findings}
    negative_fixture_rejected = expected_gates.issubset(found_gates)

    report = {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lifecycle": "SPECIFICATION_ONLY",
        "schema_results": schema_results,
        "negative_fixture": {
            "candidate_hash": sha256(root / "fixtures" / "bad" / "x_agent_blueprint.bad.json"),
            "expected_gates": sorted(expected_gates),
            "findings": findings,
            "rejected": negative_fixture_rejected,
            "deterministic_verdict": "REVISION_REQUIRED" if negative_fixture_rejected else "INVALID_TEST_FIXTURE",
        },
        "authority": {
            "runtime_evaluated": False,
            "build_authorized": False,
            "deployment_authorized": False,
            "production_approved": False,
        },
    }

    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")

    return 0 if all(item["valid"] for item in schema_results) and negative_fixture_rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())

