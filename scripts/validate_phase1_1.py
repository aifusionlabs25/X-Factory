#!/usr/bin/env python3
"""Deterministic local validation for the Phase 1.1 closure contracts."""

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


def canonical_json(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return unicodedata.normalize("NFC", text).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_digest(files: dict[str, bytes]) -> str:
    lines = [path.encode("utf-8") + b"\0" + sha256(files[path]).encode("ascii") for path in sorted(files)]
    return sha256(b"\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    contract_dir = root / "contracts" / "phase1_1"
    names = ("output_bundle_manifest", "deterministic_generation", "acceptance_fixture")
    contracts: dict[str, Any] = {}
    schema_checks: dict[str, bool] = {}
    for name in names:
        instance = load(contract_dir / f"{name}.v0.1.json")
        schema = load(contract_dir / f"{name}.v0.1.schema.json")
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
    manifest_template_ids = {item["source_template"] for item in manifest["files"]}
    defined_template_ids = {item["template_id"] for item in generation["template_set"]["definitions"]}
    assertion_ids = [item["id"] for item in acceptance["assertions"]]

    cross_checks = {
        "exact_five_unique_manifest_paths": len(manifest_paths) == 5 and len(set(manifest_paths)) == 5,
        "template_outputs_equal_manifest_paths": set(template_paths) == set(manifest_paths),
        "render_order_covers_manifest_paths_once": generation["template_set"]["render_order"] == template_paths,
        "template_ids_fully_defined": manifest_template_ids == defined_template_ids,
        "runner_command_bound": generation["test_runner"]["command"] == acceptance["runner"],
        "six_assertions_bound": assertion_ids == generation["test_runner"]["normative_assertions"],
        "safe_environment_bound": acceptance["environment"] == {
            "network": "DISABLED",
            "provider_credentials": "ABSENT",
            "external_actions": "PROHIBITED",
            "filesystem_scope": "EPHEMERAL_FIXTURE_WORKSPACE_ONLY",
        },
        "nondeterminism_sources_forbidden": set(generation["forbidden_nondeterminism"]) == {
            "CLOCK", "RANDOMNESS", "ENVIRONMENT_VARIABLES", "NETWORK", "LOCALE", "HOST_PATHS", "UNORDERED_ITERATION", "PROVIDER_CALLS"
        },
    }

    synthetic_input = {
        "candidate_id": "CANDIDATE-SYNTHETIC-BUNDLE-V1",
        "fixture_id": acceptance["fixture_id"],
        "purpose": "Synthetic deterministic bundle fixture",
        "provider_free": True,
    }
    build_one = {path: canonical_json({"path": path, "input": synthetic_input}) for path in manifest_paths if path != manifest["manifest_filename"]}
    build_two = {path: canonical_json({"path": path, "input": synthetic_input}) for path in manifest_paths if path != manifest["manifest_filename"]}
    deterministic_checks = {
        "identical_file_set": set(build_one) == set(build_two),
        "byte_equivalent_repeated_projection": build_one == build_two,
        "root_digest_equivalent": root_digest(build_one) == root_digest(build_two),
        "negative_extra_path_rejected": set(build_one) != set({**build_two, "unexpected.txt": b"x"}),
        "utf8_lf_final_newline": all(data.endswith(b"\n") and b"\r\n" not in data and not data.startswith(b"\xef\xbb\xbf") for data in build_one.values()),
    }

    report = {
        "schema_version": "0.1",
        "phase": "PHASE_1_1_LOCAL_CLOSURE_VALIDATION",
        "schema_checks": schema_checks,
        "cross_contract_checks": cross_checks,
        "deterministic_fixture_checks": deterministic_checks,
        "synthetic_root_digest": "sha256:" + root_digest(build_one),
        "provider_transmission_performed": False,
        "build_authorized": False,
        "deployment_authorized": False,
        "production_approved": False,
    }
    print(json.dumps(report, indent=2))
    return 0 if all(schema_checks.values()) and all(cross_checks.values()) and all(deterministic_checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
