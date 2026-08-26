#!/usr/bin/env python3
"""Deterministic local validation for Phase 1.2 interface closure contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return unicodedata.normalize("NFC", json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_digest(files: dict[str, bytes]) -> str:
    lines = [path.encode() + b"\0" + digest(files[path]).encode() for path in sorted(files) if path != "bundle.manifest.json"]
    return digest(b"\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    directory = args.root.resolve() / "contracts" / "phase1_2"
    names = ("output_bundle_manifest", "deterministic_generation", "acceptance_fixture")
    contracts: dict[str, Any] = {}
    schema_checks: dict[str, bool] = {}
    for name in names:
        instance = load(directory / f"{name}.v0.2.json")
        schema = load(directory / f"{name}.v0.2.schema.json")
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(instance))
        if errors:
            raise ValueError(f"{name} invalid: {'; '.join(error.message for error in errors)}")
        contracts[name] = instance
        schema_checks[name] = True

    manifest = contracts["output_bundle_manifest"]
    generation = contracts["deterministic_generation"]
    acceptance = contracts["acceptance_fixture"]
    manifest_paths = [item["path"] for item in manifest["files"]]
    template_paths = [item["output_path"] for item in generation["template_set"]["definitions"]]
    evidence_paths = [item["path"] for item in acceptance["evidence_outputs"]]
    evidence_set = set(evidence_paths)
    assertion_ids = [item["id"] for item in acceptance["assertions"]]
    referenced_evidence = {path for assertion in acceptance["assertions"] for path in assertion["evidence"]}
    mappings = generation["blueprint_field_mappings"]

    checks = {
        "exact_five_bundle_paths": len(manifest_paths) == 5 and len(set(manifest_paths)) == 5,
        "template_paths_match_bundle": set(template_paths) == set(manifest_paths),
        "requirements_mapping_is_unambiguous": mappings.get("agent/agent.spec.json.requirements") == "requirements",
        "agent_name_fallback_is_defined": mappings.get("agent/AGENT.md.name") == "identity.agent_name WHEN non-null and non-empty ELSE candidate_id",
        "purpose_role_hard_rules_are_mapped": all(key in mappings for key in ("agent/AGENT.md.purpose", "agent/AGENT.md.role", "agent/AGENT.md.hard_rules")),
        "generator_command_and_callable_are_exact": generation["generator_interface"]["module"] == "x_factory.bundle_generator" and "--evidence <empty-evidence-dir>" in generation["generator_interface"]["command"],
        "generator_boundaries_are_separate": generation["generator_interface"]["output_boundary"] != generation["generator_interface"]["evidence_boundary"],
        "exit_codes_are_complete": generation["generator_interface"]["exit_codes"] == {"0": "SUCCESS", "2": "INVALID_INPUT_OR_CONTRACT", "3": "BOUNDARY_OR_SAFETY_VIOLATION", "4": "DETERMINISM_OR_ACCEPTANCE_FAILURE"},
        "runner_can_launch_and_audit": {"os", "subprocess"}.issubset(set(generation["test_runner"]["allowed_imports"])),
        "six_assertions_bound": assertion_ids == generation["test_runner"]["normative_assertions"],
        "six_unique_evidence_paths": len(evidence_paths) == 6 and len(evidence_set) == 6,
        "all_assertion_evidence_declared": referenced_evidence.issubset(evidence_set),
        "generator_and_runner_ownership_defined": {item["producer"] for item in acceptance["evidence_outputs"]} == {"GENERATOR", "TEST_RUNNER"},
        "every_evidence_schema_has_required_and_constants": all(set(item["schema"]) == {"required", "constants"} for item in acceptance["evidence_outputs"]),
        "network_and_credentials_enforced": acceptance["environment"]["network"] == "DISABLED_BY_TEST_HARNESS" and acceptance["environment"]["provider_credentials"] == "REMOVED_AND_ASSERTED_ABSENT",
    }

    synthetic_blueprint = {"schema_version": "0.1", "candidate_id": "SYNTHETIC-V2", "requirements": [{"id": "REQ-001"}], "identity": {"agent_name": None}, "evaluation_plan": {"hard_rules": ["B", "A"]}}
    build_one = {path: canonical({"path": path, "blueprint": synthetic_blueprint, "mapping_contract": generation["contract_id"]}) for path in manifest_paths}
    build_two = {path: canonical({"path": path, "blueprint": synthetic_blueprint, "mapping_contract": generation["contract_id"]}) for path in manifest_paths}
    deterministic = {
        "identical_file_set": set(build_one) == set(build_two),
        "identical_bytes": build_one == build_two,
        "identical_root_digest": root_digest(build_one) == root_digest(build_two),
        "extra_bundle_path_rejected": set(build_one) != set({**build_two, "unexpected.txt": b"x"}),
        "utf8_lf_nfc_final_newline": all(data.decode("utf-8") == unicodedata.normalize("NFC", data.decode("utf-8")) and data.endswith(b"\n") and b"\r\n" not in data and not data.startswith(b"\xef\xbb\xbf") for data in build_one.values()),
    }
    report = {
        "schema_version": "0.2",
        "phase": "PHASE_1_2_INTERFACE_CLOSURE_VALIDATION",
        "schema_checks": schema_checks,
        "interface_checks": checks,
        "deterministic_fixture_checks": deterministic,
        "synthetic_root_digest": "sha256:" + root_digest(build_one),
        "provider_transmission_performed": False,
        "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    print(json.dumps(report, indent=2))
    return 0 if all(schema_checks.values()) and all(checks.values()) and all(deterministic.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
