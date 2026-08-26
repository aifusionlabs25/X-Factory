#!/usr/bin/env python3
"""Catalog-bound Phase 2.1 Vera verification of unchanged controlled-build-004."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import phase2_vera_build_verification as phase2

RUN_ID = "contained-vera-build-verification-002"
MARKER = "X_FACTORY_GOVERNED_BUILD_VERIFICATION_V0_2"
SCOPE = "EXACT_CATALOG_BOUND_CONTROLLED_BUILD_004_PAYLOAD_FOR_ONE_CONTAINED_VERA_PHASE2_1_REVISION_PROOF"
PRIOR_EVALUATION_SHA = "sha256:572fb8d6bcf61ad5051fdda75aff1d6eccc86051cc8ee1b99cb8d7712eef817d"
POST_VALIDATION_SHA = "sha256:8a05609dd91cf43c790259eb524e21e66020f921217afbfd931ffd4e204ec256"

GATES = (
    "blueprint_fidelity", "required_files_present", "no_undeclared_files",
    "no_unauthorized_features", "excluded_capabilities_absent",
    "origin_policy_honored", "no_reference_contamination", "schema_conformance",
    "deterministic_acceptance_passed", "repeatability_passed",
    "zero_external_activity", "staging_boundary_preserved",
    "authority_boundary_preserved", "evidence_chain_complete",
)

REQUIRED_GATE_EVIDENCE = {
    "blueprint_fidelity": {"EVID-BUILD-001", "EVID-BUILD-002", "EVID-BUILD-003", "EVID-BUILD-007"},
    "required_files_present": {"EVID-BUILD-004", "EVID-BUILD-005", "EVID-BUILD-006"},
    "no_undeclared_files": {"EVID-BUILD-004", "EVID-BUILD-005", "EVID-BUILD-025"},
    "no_unauthorized_features": {"EVID-BUILD-008", "EVID-BUILD-009", "EVID-BUILD-011"},
    "excluded_capabilities_absent": {"EVID-BUILD-010", "EVID-BUILD-011", "EVID-BUILD-012", "EVID-BUILD-013"},
    "origin_policy_honored": {"EVID-BUILD-026", "EVID-BUILD-027", "EVID-BUILD-028"},
    "no_reference_contamination": {"EVID-BUILD-008", "EVID-BUILD-012", "EVID-BUILD-013"},
    "schema_conformance": {"EVID-BUILD-014", "EVID-BUILD-023", "EVID-BUILD-024"},
    "deterministic_acceptance_passed": {"EVID-BUILD-014", "EVID-BUILD-015", "EVID-BUILD-024"},
    "repeatability_passed": {"EVID-BUILD-016", "EVID-BUILD-017", "EVID-BUILD-018"},
    "zero_external_activity": {"EVID-BUILD-008", "EVID-BUILD-009", "EVID-BUILD-010", "EVID-BUILD-011"},
    "staging_boundary_preserved": {"EVID-BUILD-019", "EVID-BUILD-020", "EVID-BUILD-021"},
    "authority_boundary_preserved": {"EVID-BUILD-019", "EVID-BUILD-020", "EVID-BUILD-021", "EVID-BUILD-022"},
    "evidence_chain_complete": {"EVID-BUILD-001", "EVID-BUILD-007", "EVID-BUILD-023", "EVID-BUILD-025", "EVID-BUILD-030", "EVID-BUILD-031"},
}


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def pointer_get(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {pointer}")
    current = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(f"JSON pointer does not resolve: {pointer}")
    return current


def evidence_entry(evidence_id: str, semantic_type: str, allowed_gates: list[str], assertion: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "semantic_type": semantic_type,
        "allowed_gates": allowed_gates,
        "assertion": assertion,
        "references": references,
    }


def exact(pointer: str, expected: Any) -> dict[str, Any]:
    return {"json_pointer": pointer, "expected": expected}


def present(pointer: str) -> dict[str, Any]:
    return {"json_pointer": pointer}


def make_catalog() -> dict[str, Any]:
    outputs = list(phase2.EXPECTED_OUTPUTS)
    entries = [
        evidence_entry("EVID-BUILD-001", "HASH_MATCH", ["blueprint_fidelity", "evidence_chain_complete"], "The payload binds the exact frozen blueprint hash.", [exact("/frozen_specification/blueprint_sha256", phase2.BLUEPRINT_SHA)]),
        evidence_entry("EVID-BUILD-002", "EXACT_VALUE", ["blueprint_fidelity"], "The frozen specification verdict is ready for build.", [exact("/frozen_specification/specification_evaluation/verdict", "SPECIFICATION_READY_FOR_BUILD")]),
        evidence_entry("EVID-BUILD-003", "EXACT_VALUE", ["blueprint_fidelity"], "No deviation from the frozen blueprint is declared.", [exact("/build_evidence/deviations_from_blueprint", [])]),
        evidence_entry("EVID-BUILD-004", "EXACT_VALUE", ["required_files_present", "no_undeclared_files"], "The actual candidate path set is exactly the approved five paths.", [exact("/candidate/actual_paths", outputs)]),
        evidence_entry("EVID-BUILD-005", "EXACT_VALUE", ["required_files_present", "no_undeclared_files"], "The expected candidate path set is exactly the approved five paths.", [exact("/candidate/expected_paths", outputs)]),
        evidence_entry("EVID-BUILD-006", "EXACT_VALUE", ["required_files_present"], "The independent deterministic verifier confirmed the seed five-path set.", [exact("/build_evidence/independent_verification/checks/seed_exact_five_paths", True)]),
        evidence_entry("EVID-BUILD-007", "EXACT_VALUE", ["blueprint_fidelity", "evidence_chain_complete"], "Implementation sources are hash-bound.", [exact("/build_evidence/independent_verification/checks/implementation_sources_bound", True)]),
        evidence_entry("EVID-BUILD-008", "EXACT_VALUE", ["no_unauthorized_features", "no_reference_contamination", "zero_external_activity"], "Independent verification recorded zero external activity.", [exact("/build_evidence/independent_verification/checks/zero_external_activity_recorded", True)]),
        evidence_entry("EVID-BUILD-009", "EXACT_VALUE", ["no_unauthorized_features", "zero_external_activity"], "The sanitized build record reports zero external actions.", [exact("/build_evidence/sanitized_build_record/implementation/external_actions", 0)]),
        evidence_entry("EVID-BUILD-010", "EXACT_VALUE", ["excluded_capabilities_absent", "zero_external_activity"], "The sanitized build record reports zero network attempts.", [exact("/build_evidence/sanitized_build_record/implementation/network_attempts", 0)]),
        evidence_entry("EVID-BUILD-011", "EXACT_VALUE", ["no_unauthorized_features", "excluded_capabilities_absent", "zero_external_activity"], "The sanitized build record reports zero provider calls.", [exact("/build_evidence/sanitized_build_record/implementation/provider_calls", 0)]),
        evidence_entry("EVID-BUILD-012", "EXACT_VALUE", ["excluded_capabilities_absent", "no_reference_contamination"], "The credential-rejection negative test passed.", [exact("/build_evidence/independent_verification/negative_tests/credential_rejected", True)]),
        evidence_entry("EVID-BUILD-013", "EXACT_VALUE", ["excluded_capabilities_absent", "no_reference_contamination"], "The runtime network guard blocked socket access.", [exact("/build_evidence/independent_verification/negative_tests/network_runtime_guard_blocks_socket", True)]),
        evidence_entry("EVID-BUILD-014", "EXACT_VALUE", ["schema_conformance", "deterministic_acceptance_passed"], "The controlled build acceptance status is PASS.", [exact("/build_evidence/sanitized_build_record/acceptance/status", "PASS")]),
        evidence_entry("EVID-BUILD-015", "EXACT_VALUE", ["deterministic_acceptance_passed"], "All six deterministic assertions passed.", [exact("/build_evidence/independent_verification/checks/all_six_assertions_pass", True)]),
        evidence_entry("EVID-BUILD-016", "EXACT_VALUE", ["repeatability_passed"], "Repeated candidate bytes are equal.", [exact("/build_evidence/repeatability_report/bytes_equal", True)]),
        evidence_entry("EVID-BUILD-017", "EXACT_VALUE", ["repeatability_passed"], "Repeated candidate file sets are equal.", [exact("/build_evidence/repeatability_report/file_sets_equal", True)]),
        evidence_entry("EVID-BUILD-018", "EXACT_VALUE", ["repeatability_passed"], "Repeated candidate root digests are equal.", [exact("/build_evidence/repeatability_report/root_digests_equal", True)]),
        evidence_entry("EVID-BUILD-019", "EXACT_VALUE", ["staging_boundary_preserved", "authority_boundary_preserved"], "Live-factory installation remains unauthorized.", [exact("/authority/install_to_live_factory_authorized", False)]),
        evidence_entry("EVID-BUILD-020", "EXACT_VALUE", ["staging_boundary_preserved", "authority_boundary_preserved"], "Deployment remains unauthorized.", [exact("/authority/deployment_authorized", False)]),
        evidence_entry("EVID-BUILD-021", "EXACT_VALUE", ["staging_boundary_preserved", "authority_boundary_preserved"], "Production remains unapproved.", [exact("/authority/production_approved", False)]),
        evidence_entry("EVID-BUILD-022", "EXACT_VALUE", ["authority_boundary_preserved"], "Independent deterministic verification confirmed false authority.", [exact("/build_evidence/independent_verification/checks/authority_remains_false", True)]),
        evidence_entry("EVID-BUILD-023", "EXACT_VALUE", ["schema_conformance", "evidence_chain_complete"], "The final manifest self-hash was independently verified.", [exact("/build_evidence/independent_verification/checks/seed_manifest_self_hash_matches", True)]),
        evidence_entry("EVID-BUILD-024", "EXACT_VALUE", ["schema_conformance", "deterministic_acceptance_passed"], "The independent acceptance rerun passed.", [exact("/build_evidence/independent_verification/checks/independent_acceptance_rerun_passes", True)]),
        evidence_entry("EVID-BUILD-025", "EXACT_VALUE", ["no_undeclared_files", "evidence_chain_complete"], "The complete evidence path set is exact.", [exact("/build_evidence/independent_verification/checks/evidence_path_set_exact", True)]),
        evidence_entry("EVID-BUILD-026", "REFERENCE_ONLY", ["origin_policy_honored"], "The exact frozen deterministic-generation contract contains the declared origin policy.", [present("/frozen_specification/contracts/deterministic_generation/origin_policy")]),
        evidence_entry("EVID-BUILD-027", "REFERENCE_ONLY", ["origin_policy_honored"], "The exact frozen deterministic-generation contract contains the field mappings governed by that policy.", [present("/frozen_specification/contracts/deterministic_generation/blueprint_field_mappings")]),
        evidence_entry("EVID-BUILD-028", "DERIVED_FROM", ["origin_policy_honored"], "Conformance to the frozen deterministic contract is supported by bound implementation sources and the passing independent acceptance rerun.", [exact("/build_evidence/independent_verification/checks/implementation_sources_bound", True), exact("/build_evidence/independent_verification/checks/independent_acceptance_rerun_passes", True)]),
        evidence_entry("EVID-BUILD-029", "EXACT_VALUE", ["repeatability_passed"], "The seed candidate matches the repeated fixture candidate.", [exact("/build_evidence/independent_verification/checks/seed_matches_fixture", True)]),
        evidence_entry("EVID-BUILD-030", "HASH_MATCH", ["evidence_chain_complete"], "The evidence chain binds the exact controlled-build record.", [exact("/build_evidence/build_record_sha256", phase2.BUILD_RECORD_SHA)]),
        evidence_entry("EVID-BUILD-031", "HASH_MATCH", ["evidence_chain_complete"], "The evidence chain binds the exact candidate root digest.", [exact("/candidate/candidate_root_digest", phase2.CANDIDATE_ROOT)]),
    ]
    return {
        "schema_version": "0.1",
        "catalog_id": "EVIDENCE-CATALOG-CONTROLLED-BUILD-004-V1",
        "model_may_select_ids_only": True,
        "broker_owns_pointer_and_claim_semantics": True,
        "allowed_semantic_types": ["EXACT_VALUE", "PRESENCE", "HASH_MATCH", "SCHEMA_VALID", "DERIVED_FROM", "REFERENCE_ONLY"],
        "entries": entries,
        "required_gate_evidence": {gate: sorted(ids) for gate, ids in REQUIRED_GATE_EVIDENCE.items()},
    }


def validate_catalog(payload: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    ids: set[str] = set()
    checks: dict[str, bool] = {}
    for entry in catalog["entries"]:
        evidence_id = entry["evidence_id"]
        if evidence_id in ids:
            raise ValueError(f"Duplicate evidence ID: {evidence_id}")
        ids.add(evidence_id)
        if not set(entry["allowed_gates"]) <= set(GATES):
            raise ValueError(f"Unknown allowed gate for {evidence_id}")
        for reference in entry["references"]:
            resolved = pointer_get(payload, reference["json_pointer"])
            if "expected" in reference and resolved != reference["expected"]:
                raise ValueError(f"Evidence value mismatch for {evidence_id}: {reference['json_pointer']}")
        checks[evidence_id] = True
    for gate, required in REQUIRED_GATE_EVIDENCE.items():
        if not required <= ids:
            raise ValueError(f"Required evidence missing from catalog for {gate}")
        for evidence_id in required:
            entry = next(item for item in catalog["entries"] if item["evidence_id"] == evidence_id)
            if gate not in entry["allowed_gates"]:
                raise ValueError(f"Evidence {evidence_id} is not claim-compatible with {gate}")
    return {"catalog_entries": len(ids), "all_ids_unique": True, "all_json_pointers_resolve": True, "all_expected_values_match": True, "all_gate_compatibility_rules_pass": True, "entry_checks": checks}


def validate_model_evidence(evaluation: dict[str, Any], catalog: dict[str, Any], payload_hash: str, catalog_hash: str) -> dict[str, Any]:
    entries = {entry["evidence_id"]: entry for entry in catalog["entries"]}
    errors: list[str] = []
    if evaluation["evaluated_payload_sha256"] != payload_hash:
        errors.append("evaluated_payload_sha256 mismatch")
    if evaluation["evidence_catalog_sha256"] != catalog_hash:
        errors.append("evidence_catalog_sha256 mismatch")
    for gate in GATES:
        selected = evaluation["gates"][gate]["evidence_ids"]
        if len(selected) != len(set(selected)):
            errors.append(f"{gate}: duplicate evidence IDs")
        for evidence_id in selected:
            if evidence_id not in entries:
                errors.append(f"{gate}: unknown evidence ID {evidence_id}")
            elif gate not in entries[evidence_id]["allowed_gates"]:
                errors.append(f"{gate}: incompatible evidence ID {evidence_id}")
        if evaluation["gates"][gate]["status"] == "PASS" and not REQUIRED_GATE_EVIDENCE[gate] <= set(selected):
            missing = sorted(REQUIRED_GATE_EVIDENCE[gate] - set(selected))
            errors.append(f"{gate}: missing required evidence {missing}")
    for defect in evaluation["defects"]:
        for evidence_id in defect["evidence_ids"]:
            if evidence_id not in entries:
                errors.append(f"{defect['id']}: unknown evidence ID {evidence_id}")
    if evaluation["verdict"] == "BUILD_VERIFIED":
        if evaluation["defects"]:
            errors.append("BUILD_VERIFIED with nonempty defects")
        failed = [gate for gate in GATES if evaluation["gates"][gate]["status"] != "PASS"]
        if failed:
            errors.append(f"BUILD_VERIFIED with failed gates: {failed}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "schema_valid": True,
        "payload_hash_bound": evaluation["evaluated_payload_sha256"] == payload_hash,
        "catalog_hash_bound": evaluation["evidence_catalog_sha256"] == catalog_hash,
        "evidence_ids_exist": not any("unknown evidence ID" in error for error in errors),
        "json_pointers_prevalidated": True,
        "claim_compatibility_valid": not any("incompatible evidence ID" in error for error in errors),
        "required_gate_evidence_complete": not any("missing required evidence" in error for error in errors),
        "candidate_identity_bound": evaluation["evaluated_candidate_root_digest"] == phase2.CANDIDATE_ROOT,
        "errors": errors,
    }


def approval_path(root: Path, manifest_hash: str) -> Path:
    suffix = manifest_hash.removeprefix("sha256:")[:12]
    return root / "approvals" / "approved" / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.{suffix}.approval.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--runtime-profile-root", type=Path, default=Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "profiles")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.execute:
        raise ValueError("Choose exactly one of --prepare or --execute")
    root = args.factory_root.resolve()

    evaluation_schema_path = root / "contracts" / "build_verification_evaluation.v0.2.schema.json"
    evaluation_schema = phase2.load_json(evaluation_schema_path)
    manifest_schema = phase2.load_json(root / "contracts" / "build_verification_disclosure_manifest.v0.2.schema.json")
    approval_schema = phase2.load_json(root / "contracts" / "build_verification_approval.v0.2.schema.json")
    record_schema = phase2.load_json(root / "contracts" / "contained_build_verification_record.v0.2.schema.json")
    for schema in (evaluation_schema, manifest_schema, approval_schema, record_schema):
        Draft202012Validator.check_schema(schema)

    profile_hash = phase2.verify_vera_profile(root, args.runtime_profile_root.resolve())
    payload, _ = phase2.make_payload(root)
    prior_evaluation_path = root / "runs" / "contained" / "contained-vera-build-verification-001" / "vera" / "build-evaluation.v0.1.json"
    post_validation_path = root / "verification" / "contained-vera-build-verification-001" / "post-run-semantic-validation.json"
    phase2.assert_hash(prior_evaluation_path, PRIOR_EVALUATION_SHA, "Prior Vera evaluation")
    phase2.assert_hash(post_validation_path, POST_VALIDATION_SHA, "Post-run semantic validation")
    catalog = make_catalog()
    payload["phase2_1_revision_context"] = {
        "prior_vera_evaluation_sha256": PRIOR_EVALUATION_SHA,
        "prior_vera_evaluation": phase2.load_json(prior_evaluation_path),
        "post_run_validation_sha256": POST_VALIDATION_SHA,
        "post_run_validation": phase2.load_json(post_validation_path),
        "candidate_must_remain_unchanged": True,
        "revision_scope": "VERIFICATION_ARTIFACT_ONLY",
    }
    payload["evidence_catalog"] = catalog
    payload["evaluation_rules"] = {
        "model_selects_evidence_ids_only": True,
        "broker_validates_pointer_resolution_and_claim_compatibility": True,
        "all_fourteen_gates_must_pass_for_build_verified": True,
        "any_post_evaluation_validation_failure_yields": "VERIFICATION_ARTIFACT_INVALID",
        "do_not_rewrite_candidate": True,
        "do_not_grant_install_deployment_or_production_authority": True,
    }
    catalog_validation = validate_catalog(payload, catalog)
    catalog_hash = canonical_hash(catalog)
    if phase2.WINDOWS_PATH.search(json.dumps(payload, ensure_ascii=False, sort_keys=True)):
        raise PermissionError("Sanitized Phase 2.1 payload contains an absolute Windows path")

    pending = root / "approvals" / "pending"
    payload_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.payload.json"
    phase2.write_json(payload_path, payload)
    payload_hash = phase2.sha256_file(payload_path)
    bound_hashes = {
        "blueprint": phase2.BLUEPRINT_SHA,
        "build_record": phase2.BUILD_RECORD_SHA,
        "candidate_root_digest": phase2.CANDIDATE_ROOT,
        "prior_vera_evaluation": PRIOR_EVALUATION_SHA,
        "post_run_validation": POST_VALIDATION_SHA,
        "evaluation_schema": phase2.sha256_file(evaluation_schema_path),
    }
    manifest = {
        "schema_version": "0.2",
        "manifest_id": "DISCLOSURE-CONTROLLED-BUILD-004-VERA-V2",
        "approval_id": "APPROVAL-CONTROLLED-BUILD-004-VERA-V2",
        "purpose": "Permit one contained Vera revision proof using only broker-owned evidence IDs and machine-resolvable claim mappings for unchanged controlled-build-004",
        "build_id": phase2.BUILD_ID,
        "payload_sha256": payload_hash,
        "evidence_catalog_sha256": catalog_hash,
        "bound_hashes": bound_hashes,
        "provider": phase2.PROVIDER,
        "model": phase2.MODEL,
        "profiles": [phase2.PROFILE],
        "profile_config_hashes": {phase2.PROFILE: profile_hash},
        "scope": SCOPE,
        "execution_mode": phase2.EXECUTION_MODE,
        "tool_policy": phase2.TOOL_POLICY,
        "authority": payload["authority"],
    }
    phase2.validate(manifest, manifest_schema, "Phase 2.1 disclosure manifest")
    manifest_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.disclosure-manifest.json"
    phase2.write_json(manifest_path, manifest)
    manifest_hash = phase2.sha256_file(manifest_path)
    required_approval = approval_path(root, manifest_hash)
    preview = {
        "schema_version": "0.2",
        "provider": phase2.PROVIDER,
        "model": phase2.MODEL,
        "profiles": [phase2.PROFILE],
        "tool_policy": phase2.TOOL_POLICY,
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "evidence_catalog_sha256": catalog_hash,
        "catalog_validation": catalog_validation,
        "exact_disclosure_manifest": manifest,
        "exact_catalog_bound_payload": payload,
        "approval_record_required": str(required_approval.relative_to(root)),
        "provider_transmission_performed": False,
    }
    preview_path = pending / f"{phase2.BUILD_ID}.vera-build-verification-phase2-1.payload-preview.json"
    phase2.write_json(preview_path, preview)
    if args.prepare:
        print(json.dumps({"status": "APPROVAL_REQUIRED", "disclosure_manifest_sha256": manifest_hash, "payload_sha256": payload_hash, "evidence_catalog_sha256": catalog_hash, "payload_preview": str(preview_path), "approval_record_required": str(required_approval), "provider_transmission_performed": False}, indent=2))
        return 2

    if not required_approval.is_file():
        raise PermissionError(f"Exact Phase 2.1 approval is missing: {required_approval}")
    approval = phase2.load_json(required_approval)
    phase2.validate(approval, approval_schema, "Phase 2.1 approval")
    if approval["disclosure_manifest_sha256"] != manifest_hash or approval["payload_sha256"] != payload_hash or approval["evidence_catalog_sha256"] != catalog_hash:
        raise PermissionError("Approval does not bind the exact Phase 2.1 manifest, payload, and evidence catalog")
    approval_hash = phase2.sha256_file(required_approval)
    run_dir = root / "runs" / "contained" / RUN_ID
    if run_dir.exists():
        raise FileExistsError(f"Phase 2.1 run directory already exists: {run_dir}")

    preflight = phase2.runtime_zero_tools_preflight(root)
    governance = {"governed_run_marker": MARKER, "execution_mode": phase2.EXECUTION_MODE, "disclosure_manifest_sha256": manifest_hash, "payload_sha256": payload_hash, "evidence_catalog_sha256": catalog_hash, "approval_sha256": approval_hash}
    prompt = (
        "X-AGENT FACTORY PHASE 2.1 CONTAINED BUILD VERIFICATION REVISION. You are Vera, an independent evaluator. "
        "You have zero tools and may use only the inline approved JSON. The candidate is frozen and must not be rewritten. "
        "For each gate, select evidence_id values only from PAYLOAD.evidence_catalog. Do not invent paths, prose citations, or evidence IDs. "
        "A PASS gate must include every ID listed for that gate in required_gate_evidence. The broker, not you, owns pointer resolution and claim compatibility. "
        "Return one JSON object only, valid against OUTPUT_SCHEMA. BUILD_VERIFIED requires all gates PASS and defects empty. "
        "Authority is verification only and cannot authorize installation, deployment, production, or live-factory mutation.\n"
        "GOVERNANCE=" + json.dumps(governance, sort_keys=True, separators=(",", ":")) + "\n"
        "PAYLOAD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        "OUTPUT_SCHEMA=" + json.dumps(evaluation_schema, sort_keys=True, separators=(",", ":"))
    )
    evaluation, raw, session_id = phase2.run_vera(prompt, root)
    tool_calls = phase2.session_tool_count(session_id, root)
    phase2.validate(evaluation, evaluation_schema, "Phase 2.1 Vera evaluation")
    if evaluation["evaluated_blueprint_sha256"] != phase2.BLUEPRINT_SHA or evaluation["evaluated_build_record_sha256"] != phase2.BUILD_RECORD_SHA or evaluation["evaluated_candidate_root_digest"] != phase2.CANDIDATE_ROOT:
        raise PermissionError("Vera result does not bind the unchanged candidate identity")

    run_dir.mkdir(parents=True)
    evaluation_path = run_dir / "vera" / "build-evaluation.v0.2.json"
    raw_path = run_dir / "vera" / "raw-response.txt"
    phase2.write_json(evaluation_path, evaluation)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8", newline="\n")
    promotion = validate_model_evidence(evaluation, catalog, payload_hash, catalog_hash)
    promotion_path = run_dir / "broker" / "promotion-validation.v0.1.json"
    phase2.write_json(promotion_path, promotion)
    lifecycle = evaluation["verdict"] if promotion["status"] == "PASS" else "VERIFICATION_ARTIFACT_INVALID"
    record = {
        "schema_version": "0.2", "run_id": RUN_ID, "governed_run_marker": MARKER,
        "execution_mode": phase2.EXECUTION_MODE, "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash, "evidence_catalog_sha256": catalog_hash,
        "approval_sha256": approval_hash, "provider": phase2.PROVIDER, "model": phase2.MODEL,
        "profiles": [phase2.PROFILE], "tool_policy": phase2.TOOL_POLICY,
        "runtime_preflight": preflight, "session": {"session_id": session_id, "virgin_session": True, "tool_call_count": tool_calls},
        "artifacts": {"evaluation_sha256": phase2.sha256_file(evaluation_path), "promotion_validation_sha256": phase2.sha256_file(promotion_path), "raw_verdict": evaluation["verdict"], "completed_at": datetime.now(timezone.utc).isoformat()},
        "promotion_validation": promotion, "lifecycle_status": lifecycle, "authority": payload["authority"],
    }
    phase2.validate(record, record_schema, "Phase 2.1 run record")
    phase2.write_json(run_dir / "contained_build_verification_record.v0.2.json", record)
    print(json.dumps({"status": "COMPLETE", "raw_verdict": evaluation["verdict"], "lifecycle_status": lifecycle, "run_dir": str(run_dir), "record": record}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
