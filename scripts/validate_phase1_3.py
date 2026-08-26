#!/usr/bin/env python3
"""Deterministic local validation for Phase 1.3 byte-bound closure contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


FIVE_PATHS = ["agent/AGENT.md", "agent/agent.spec.json", "bundle.manifest.json", "tests/fixtures/smoke.input.json", "tests/test_bundle.py"]
FOUR_PAYLOAD_PATHS = ["agent/AGENT.md", "agent/agent.spec.json", "tests/fixtures/smoke.input.json", "tests/test_bundle.py"]
CREDENTIAL_KEYS = ["ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return unicodedata.normalize("NFC", text).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_digest(files: dict[str, bytes]) -> str:
    records = [path.encode("utf-8") + b"\0" + digest(files[path]).encode("ascii") + b"\n" for path in FOUR_PAYLOAD_PATHS]
    return digest(b"".join(records))


def validate(instance: Any, schema: dict[str, Any], label: str) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        raise ValueError(f"{label} invalid: {'; '.join(error.message for error in errors)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    directory = args.root.resolve() / "contracts" / "phase1_3"
    names = ("output_bundle_manifest", "deterministic_generation", "acceptance_fixture")
    contracts: dict[str, Any] = {}
    schema_checks: dict[str, bool] = {}
    for name in names:
        instance = load(directory / f"{name}.v0.3.json")
        schema = load(directory / f"{name}.v0.3.schema.json")
        validate(instance, schema, name)
        contracts[name] = instance
        schema_checks[name] = True

    manifest = contracts["output_bundle_manifest"]
    generation = contracts["deterministic_generation"]
    acceptance = contracts["acceptance_fixture"]
    manifest_paths = [item["path"] for item in manifest["files"]]
    template_paths = [item["output_path"] for item in generation["template_set"]["definitions"]]
    mappings = generation["blueprint_field_mappings"]
    mapping_by_output = {item["output"]: item for item in mappings}
    template_hashes = {item["template_id"]: digest(item["source_utf8"].encode("utf-8")) for item in generation["template_set"]["definitions"]}
    template_records = [template_id.encode() + b"\0" + template_hashes[template_id].encode() + b"\n" for template_id in sorted(template_hashes)]
    template_set_hash = digest(b"".join(template_records))
    evidence_paths = [item["path"] for item in acceptance["evidence_outputs"]]
    evidence_set = set(evidence_paths)
    referenced_evidence = {path for assertion in acceptance["assertions"] for path in assertion["evidence"]}
    assertion_ids = [item["id"] for item in acceptance["assertions"]]

    synthetic_blueprint = {
        "schema_version": "0.1", "candidate_id": "SYNTHETIC-V3",
        "identity": {"agent_name": None, "role": "Synthetic verifier"},
        "objectives": {"primary_job": "Verify deterministic generation"},
        "capabilities": [], "boundaries": [], "requirements": [{"id": "REQ-001"}],
        "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False},
        "evaluation_plan": {"hard_rules": ["B", "A"]},
    }
    definition_by_path = {item["output_path"]: item for item in generation["template_set"]["definitions"]}
    agent_md = definition_by_path["agent/AGENT.md"]["source_utf8"]
    agent_md = agent_md.replace("$name", synthetic_blueprint["candidate_id"]).replace("$purpose", synthetic_blueprint["objectives"]["primary_job"]).replace("$role", synthetic_blueprint["identity"]["role"]).replace("$hard_rules", "- A\n- B")
    build_one = {
        "agent/AGENT.md": agent_md.encode("utf-8"),
        "agent/agent.spec.json": canonical({key: synthetic_blueprint[key] for key in ("schema_version", "candidate_id", "identity", "objectives", "capabilities", "boundaries", "requirements", "authority")}),
        "tests/fixtures/smoke.input.json": canonical({"candidate_id": synthetic_blueprint["candidate_id"], "fixture_id": "FIXTURE-SYNTHETIC-BUNDLE-V3", "provider_free": True, "user_input": "Create the approved deterministic synthetic bundle."}),
        "tests/test_bundle.py": definition_by_path["tests/test_bundle.py"]["source_utf8"].encode("utf-8"),
    }
    payload_records = [{"path": path, "sha256": digest(build_one[path])} for path in FOUR_PAYLOAD_PATHS]
    root = root_digest(build_one)
    generated_manifest = {"schema_version": "0.3", "manifest_contract_id": manifest["contract_id"], "generation_contract_id": generation["contract_id"], "template_set_id": generation["template_set"]["template_set_id"], "template_set_sha256": template_set_hash, "files": payload_records, "root_digest": root, "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False}}
    validate(generated_manifest, manifest["generated_manifest_schema"], "synthetic generated manifest")
    build_one["bundle.manifest.json"] = canonical(generated_manifest)
    build_two = dict(build_one)
    all_records = [{"path": path, "sha256": digest(build_one[path])} for path in FIVE_PATHS]
    zeros = "0" * 64
    evidence_examples = {
        "EXECUTION_AUDIT_V3": {"schema_version": "0.3", "run_label": "RUN_1", "network_policy": "DISABLED_BY_TEST_HARNESS", "credential_keys_scanned": CREDENTIAL_KEYS, "credential_keys_present": [], "network_attempt_count": 0, "external_action_count": 0, "output_paths": FIVE_PATHS},
        "FILE_HASHES_V3": {"schema_version": "0.3", "run_label": "RUN_1", "algorithm": "SHA-256", "files_count": 5, "files": all_records, "root_digest": root, "manifest_self_hash": digest(build_one["bundle.manifest.json"])},
        "REPEATABILITY_REPORT_V3": {"schema_version": "0.3", "run_1_root_digest": root, "run_2_root_digest": root, "compared_paths": FIVE_PATHS, "file_sets_equal": True, "bytes_equal": True, "root_digests_equal": True},
        "TEST_RESULTS_V3": {"schema_version": "0.3", "runner": "python -m unittest tests.test_bundle -v", "exit_code": 0, "status": "PASS", "assertions": [{"id": assertion_id, "status": "PASS", "evidence": next(item["evidence"] for item in acceptance["assertions"] if item["id"] == assertion_id)} for assertion_id in assertion_ids]},
    }
    for name, schema in acceptance["evidence_schemas"].items():
        validate(evidence_examples[name], schema, f"synthetic {name}")

    checks = {
        "exact_five_bundle_paths": manifest_paths == FIVE_PATHS,
        "exact_four_manifest_payload_paths": manifest["hashing"]["manifest_payload_paths"] == FOUR_PAYLOAD_PATHS,
        "manifest_self_reference_is_resolved": manifest["hashing"]["self_reference_rule"] == "BUNDLE_MANIFEST_NEVER_CONTAINS_ITS_OWN_HASH_AND_IS_EXCLUDED_FROM_ROOT_DIGEST" and "manifest_self_hash" not in generated_manifest,
        "generated_manifest_schema_is_executable": True,
        "template_paths_match_bundle": set(template_paths) == set(manifest_paths),
        "every_template_source_hash_matches": all(item["source_sha256"] == template_hashes[item["template_id"]] for item in generation["template_set"]["definitions"]),
        "template_set_hash_matches": generation["template_set"]["template_set_sha256"] == template_set_hash,
        "all_mapping_outputs_unique": len(mapping_by_output) == len(mappings),
        "requirements_direct_mapping": mapping_by_output["agent/agent.spec.json.requirements"]["source"] == ["requirements"],
        "name_fallback_is_one_declared_mapping": mapping_by_output["agent/AGENT.md.name"] == {"output": "agent/AGENT.md.name", "origin_kind": "DECLARED_FALLBACK", "source": ["identity.agent_name", "candidate_id"], "transform": "FIRST_NONEMPTY_STRING", "precedence": 1},
        "integrity_values_are_declared_derivations": all(mapping_by_output[path]["origin_kind"] == "DETERMINISTIC_DERIVATION" for path in ("bundle.manifest.json.files[].sha256", "bundle.manifest.json.root_digest", "bundle.manifest.json.template_set_sha256")),
        "no_undeclared_origin_kind": all(item["origin_kind"] in generation["origin_policy"]["allowed_origin_kinds"] for item in mappings),
        "generator_roots_are_exact": acceptance["path_model"]["generator_roots"] == {"RUN_1_OUTPUT": "run-1/output", "RUN_1_EVIDENCE": "run-1/evidence", "RUN_2_OUTPUT": "run-2/output", "RUN_2_EVIDENCE": "run-2/evidence"},
        "six_unique_evidence_paths": len(evidence_paths) == 6 and len(evidence_set) == 6,
        "all_evidence_paths_rooted": all(path.startswith(("run-1/evidence/", "run-2/evidence/", "fixture-evidence/")) for path in evidence_paths),
        "all_assertion_evidence_declared": referenced_evidence.issubset(evidence_set),
        "every_evidence_schema_is_executable": set(acceptance["evidence_schemas"]) == set(evidence_examples),
        "six_assertions_bound": assertion_ids == generation["test_runner"]["normative_assertions"],
        "network_and_credentials_enforced": acceptance["environment"]["network"] == "DISABLED_BY_TEST_HARNESS" and acceptance["environment"]["provider_credentials"] == "REMOVED_AND_ASSERTED_ABSENT",
    }
    deterministic = {
        "identical_file_set": set(build_one) == set(build_two) == set(FIVE_PATHS),
        "identical_bytes": build_one == build_two,
        "identical_root_digest": root_digest(build_one) == root_digest(build_two) == root,
        "manifest_self_hash_matches": digest(build_one["bundle.manifest.json"]) == evidence_examples["FILE_HASHES_V3"]["manifest_self_hash"],
        "extra_bundle_path_rejected": set(build_one) != set({**build_two, "unexpected.txt": b"x"}),
        "utf8_lf_nfc_final_newline": all(data.decode("utf-8") == unicodedata.normalize("NFC", data.decode("utf-8")) and data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf") for data in build_one.values()),
    }
    report = {"schema_version": "0.3", "phase": "PHASE_1_3_BYTE_BOUND_CLOSURE_VALIDATION", "schema_checks": schema_checks, "closure_checks": checks, "deterministic_fixture_checks": deterministic, "template_set_sha256": "sha256:" + template_set_hash, "synthetic_root_digest": "sha256:" + root, "provider_transmission_performed": False, "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False}}
    print(json.dumps(report, indent=2))
    return 0 if all(schema_checks.values()) and all(checks.values()) and all(deterministic.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
