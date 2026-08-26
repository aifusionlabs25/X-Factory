#!/usr/bin/env python3
"""Local deterministic validation for the prepared Phase 2.1 packet."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

import phase2_1_vera_build_verification as phase21
import phase2_vera_build_verification as phase2


def rejected(function, *args) -> bool:
    try:
        function(*args)
    except (ValueError, KeyError, PermissionError):
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pending = root / "approvals" / "pending"
    payload_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.payload.json"
    manifest_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.disclosure-manifest.json"
    preview_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.payload-preview.json"
    payload = phase2.load_json(payload_path)
    manifest = phase2.load_json(manifest_path)
    preview = phase2.load_json(preview_path)
    catalog = payload["evidence_catalog"]
    catalog_validation = phase21.validate_catalog(payload, catalog)
    catalog_hash = phase21.canonical_hash(catalog)
    payload_hash = phase2.sha256_file(payload_path)
    schema = phase2.load_json(root / "contracts" / "build_verification_evaluation.v0.2.schema.json")

    synthetic = {
        "schema_version": "0.2",
        "evaluation_id": "VERA-BUILD-EVALUATION-CONTROLLED-BUILD-004-PHASE2-1-LOCAL",
        "evaluated_build_id": phase2.BUILD_ID,
        "evaluated_blueprint_sha256": phase2.BLUEPRINT_SHA,
        "evaluated_build_record_sha256": phase2.BUILD_RECORD_SHA,
        "evaluated_candidate_root_digest": phase2.CANDIDATE_ROOT,
        "evaluated_payload_sha256": payload_hash,
        "evidence_catalog_sha256": catalog_hash,
        "gates": {gate: {"status": "PASS", "evidence_ids": sorted(ids)} for gate, ids in phase21.REQUIRED_GATE_EVIDENCE.items()},
        "defects": [],
        "verdict": "BUILD_VERIFIED",
        "authority_statement": "BUILD_VERIFICATION_ONLY_NO_INSTALL_DEPLOYMENT_OR_PRODUCTION_AUTHORITY",
    }
    Draft202012Validator(schema).validate(synthetic)
    positive = phase21.validate_model_evidence(synthetic, catalog, payload_hash, catalog_hash)

    missing_pointer_catalog = copy.deepcopy(catalog)
    missing_pointer_catalog["entries"][0]["references"][0]["json_pointer"] = "/does/not/exist"
    wrong_value_catalog = copy.deepcopy(catalog)
    wrong_value_catalog["entries"][0]["references"][0]["expected"] = "sha256:" + "0" * 64
    duplicate_catalog = copy.deepcopy(catalog)
    duplicate_catalog["entries"].append(copy.deepcopy(duplicate_catalog["entries"][0]))
    missing_required = copy.deepcopy(synthetic)
    missing_required["gates"]["blueprint_fidelity"]["evidence_ids"].remove("EVID-BUILD-001")
    incompatible = copy.deepcopy(synthetic)
    incompatible["gates"]["blueprint_fidelity"]["evidence_ids"].append("EVID-BUILD-016")
    wrong_payload_hash = copy.deepcopy(synthetic)
    wrong_payload_hash["evaluated_payload_sha256"] = "sha256:" + "0" * 64

    results = {
        "schema_version": "0.1",
        "phase": "PHASE_2_1_LOCAL_VALIDATION",
        "status": "PASS",
        "checks": {
            "catalog_entries": catalog_validation["catalog_entries"],
            "catalog_ids_unique": catalog_validation["all_ids_unique"],
            "all_json_pointers_resolve": catalog_validation["all_json_pointers_resolve"],
            "all_expected_values_match": catalog_validation["all_expected_values_match"],
            "all_claim_compatibility_rules_pass": catalog_validation["all_gate_compatibility_rules_pass"],
            "synthetic_positive_schema_valid": True,
            "synthetic_positive_promotion_valid": positive["status"] == "PASS",
            "missing_pointer_rejected": rejected(phase21.validate_catalog, payload, missing_pointer_catalog),
            "wrong_expected_value_rejected": rejected(phase21.validate_catalog, payload, wrong_value_catalog),
            "duplicate_evidence_id_rejected": rejected(phase21.validate_catalog, payload, duplicate_catalog),
            "missing_required_gate_evidence_rejected": phase21.validate_model_evidence(missing_required, catalog, payload_hash, catalog_hash)["status"] == "FAIL",
            "incompatible_gate_evidence_rejected": phase21.validate_model_evidence(incompatible, catalog, payload_hash, catalog_hash)["status"] == "FAIL",
            "wrong_payload_hash_rejected": phase21.validate_model_evidence(wrong_payload_hash, catalog, payload_hash, catalog_hash)["status"] == "FAIL",
            "candidate_root_digest_unchanged": payload["candidate"]["candidate_root_digest"] == phase2.CANDIDATE_ROOT,
            "build_record_hash_unchanged": payload["build_evidence"]["build_record_sha256"] == phase2.BUILD_RECORD_SHA,
            "absolute_windows_paths_absent": not bool(phase2.WINDOWS_PATH.search(json.dumps(payload, ensure_ascii=False, sort_keys=True))),
            "provider_transmission_performed": preview["provider_transmission_performed"],
            "manifest_payload_hash_matches": manifest["payload_sha256"] == payload_hash,
            "manifest_catalog_hash_matches": manifest["evidence_catalog_sha256"] == catalog_hash,
        },
        "disclosure_manifest_sha256": phase2.sha256_file(manifest_path),
        "payload_sha256": payload_hash,
        "evidence_catalog_sha256": catalog_hash,
    }
    boolean_checks = [value for value in results["checks"].values() if isinstance(value, bool) and value is not False]
    expected_true_count = sum(isinstance(value, bool) for key, value in results["checks"].items() if key != "provider_transmission_performed")
    if len(boolean_checks) != expected_true_count or results["checks"]["provider_transmission_performed"] is not False:
        results["status"] = "FAIL"
    print(json.dumps(results, indent=2))
    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
