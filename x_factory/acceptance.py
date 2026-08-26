"""Two-run deterministic acceptance harness for Phase 1.3 bundles."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import unicodedata
from typing import Any


FIVE_PATHS = [
    "agent/AGENT.md", "agent/agent.spec.json", "bundle.manifest.json",
    "tests/fixtures/smoke.input.json", "tests/test_bundle.py",
]
FOUR_PAYLOAD_PATHS = [
    "agent/AGENT.md", "agent/agent.spec.json",
    "tests/fixtures/smoke.input.json", "tests/test_bundle.py",
]
CREDENTIAL_KEYS = [
    "ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY",
    "OPENAI_API_KEY", "OPENROUTER_API_KEY",
]
CONTRACT_FILENAMES = [
    "acceptance_fixture.v0.3.json", "deterministic_generation.v0.3.json",
    "output_bundle_manifest.v0.3.json",
]


def _canonical(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return unicodedata.normalize("NFC", text).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _root_digest(files: dict[str, bytes]) -> str:
    records = [path.encode("utf-8") + b"\0" + _digest(files[path]).encode("ascii") + b"\n" for path in FOUR_PAYLOAD_PATHS]
    return _digest(b"".join(records))


def _read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise AssertionError(f"Unsupported schema reference: {reference}")
    value: Any = root
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(value, dict):
        raise AssertionError(f"Schema reference is not an object: {reference}")
    return value


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate_schema(value: Any, schema: dict[str, Any], label: str, root: dict[str, Any] | None = None) -> None:
    root_schema = schema if root is None else root
    if "$ref" in schema:
        _validate_schema(value, _resolve_ref(root_schema, schema["$ref"]), label, root_schema)
    for subschema in schema.get("allOf", []):
        _validate_schema(value, subschema, label, root_schema)
    if "const" in schema and value != schema["const"]:
        raise AssertionError(f"{label}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise AssertionError(f"{label}: enum mismatch")
    expected_type = schema.get("type")
    if expected_type and not _type_matches(value, expected_type):
        raise AssertionError(f"{label}: expected {expected_type}")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        if not required.issubset(value):
            raise AssertionError(f"{label}: missing required fields")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise AssertionError(f"{label}: additional properties")
        for key, subschema in properties.items():
            if key in value:
                _validate_schema(value[key], subschema, f"{label}.{key}", root_schema)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise AssertionError(f"{label}: array length")
        prefix = schema.get("prefixItems", [])
        for index, subschema in enumerate(prefix):
            if index < len(value):
                _validate_schema(value[index], subschema, f"{label}[{index}]", root_schema)
        item_schema = schema.get("items")
        if item_schema is False and len(value) > len(prefix):
            raise AssertionError(f"{label}: extra array items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value[len(prefix):], start=len(prefix)):
                _validate_schema(item, item_schema, f"{label}[{index}]", root_schema)
    if isinstance(value, str) and schema.get("pattern") == "^[0-9a-f]{64}$":
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise AssertionError(f"{label}: digest format")


def _files(root: pathlib.Path) -> dict[str, bytes]:
    result = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if sorted(result) != FIVE_PATHS:
        raise AssertionError("ASSERT-001 failed: output path set differs from contract")
    return result


def _validate_normalization(path: str, data: bytes) -> None:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n") or data.endswith(b"\n\n"):
        raise AssertionError(f"ASSERT-006 failed: byte normalization for {path}")
    text = data.decode("utf-8")
    if text != unicodedata.normalize("NFC", text):
        raise AssertionError(f"ASSERT-006 failed: NFC for {path}")
    if path.endswith(".json"):
        json.loads(text)
    elif path.endswith(".py"):
        compile(text, path, "exec")


def _make_fixture_root() -> tuple[pathlib.Path, tempfile.TemporaryDirectory[str] | None]:
    explicit = os.environ.get("X_FACTORY_FIXTURE_ROOT")
    if explicit:
        root = pathlib.Path(explicit).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise AssertionError("Fixture root must be empty")
        return root, None
    temporary = tempfile.TemporaryDirectory(prefix="x-factory-phase1-3-")
    return pathlib.Path(temporary.name).resolve(), temporary


def run_contract_fixture(_bundle_root: pathlib.Path) -> dict[str, Any]:
    blueprint_path = pathlib.Path(os.environ["X_FACTORY_BLUEPRINT_PATH"]).resolve()
    contracts_dir = pathlib.Path(os.environ["X_FACTORY_CONTRACTS_DIR"]).resolve()
    fixture_root, temporary = _make_fixture_root()
    try:
        roots = {
            "RUN_1": (fixture_root / "run-1" / "output", fixture_root / "run-1" / "evidence"),
            "RUN_2": (fixture_root / "run-2" / "output", fixture_root / "run-2" / "evidence"),
        }
        fixture_evidence = fixture_root / "fixture-evidence"
        for output, evidence in roots.values():
            output.mkdir(parents=True)
            evidence.mkdir(parents=True)
        fixture_evidence.mkdir()
        child_env = os.environ.copy()
        for key in CREDENTIAL_KEYS:
            child_env.pop(key, None)
        child_env["X_FACTORY_NETWORK_DISABLED"] = "1"
        if any(child_env.get(key) for key in CREDENTIAL_KEYS):
            raise AssertionError("Credential sanitization failed")
        for run_label, (output, evidence) in roots.items():
            command = [
                "python", "-m", "x_factory.bundle_generator", "generate",
                "--blueprint", str(blueprint_path), "--contracts", str(contracts_dir),
                "--output", str(output), "--evidence", str(evidence), "--run-label", run_label,
            ]
            completed = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=120, env=child_env, check=False)
            if completed.returncode != 0:
                raise AssertionError(f"Generator {run_label} failed: {completed.stderr[-1000:]}")

        acceptance = _read_json(contracts_dir / "acceptance_fixture.v0.3.json")
        manifest_contract = _read_json(contracts_dir / "output_bundle_manifest.v0.3.json")
        run_files = {label: _files(output) for label, (output, _evidence) in roots.items()}
        assertion_status: dict[str, str] = {"ASSERT-001": "PASS"}
        if run_files["RUN_1"] != run_files["RUN_2"]:
            raise AssertionError("ASSERT-002 failed: output bytes differ")
        assertion_status["ASSERT-002"] = "PASS"

        evidence_docs: dict[str, Any] = {}
        for label, (_output, evidence) in roots.items():
            audit = _read_json(evidence / "execution-audit.json")
            hashes = _read_json(evidence / "file-hashes.json")
            _validate_schema(audit, acceptance["evidence_schemas"]["EXECUTION_AUDIT_V3"], f"{label} audit")
            _validate_schema(hashes, acceptance["evidence_schemas"]["FILE_HASHES_V3"], f"{label} hashes")
            evidence_docs[f"{label}_audit"] = audit
            evidence_docs[f"{label}_hashes"] = hashes
            expected_hashes = [{"path": path, "sha256": _digest(run_files[label][path])} for path in FIVE_PATHS]
            if hashes["files"] != expected_hashes or hashes["manifest_self_hash"] != _digest(run_files[label]["bundle.manifest.json"]):
                raise AssertionError("ASSERT-003 failed: file hashes")
            manifest = json.loads(run_files[label]["bundle.manifest.json"].decode("utf-8"))
            _validate_schema(manifest, manifest_contract["generated_manifest_schema"], f"{label} manifest")
            if manifest["files"] != expected_hashes[:2] + expected_hashes[3:] or manifest["root_digest"] != _root_digest(run_files[label]):
                raise AssertionError("ASSERT-003 failed: manifest records")
        assertion_status["ASSERT-003"] = "PASS"

        run_1_root = _root_digest(run_files["RUN_1"])
        run_2_root = _root_digest(run_files["RUN_2"])
        if run_1_root != run_2_root or any(evidence_docs[f"{label}_hashes"]["root_digest"] != run_1_root for label in roots):
            raise AssertionError("ASSERT-004 failed: root digest")
        assertion_status["ASSERT-004"] = "PASS"
        repeatability = {"schema_version": "0.3", "run_1_root_digest": run_1_root, "run_2_root_digest": run_2_root, "compared_paths": FIVE_PATHS, "file_sets_equal": True, "bytes_equal": True, "root_digests_equal": True}
        _validate_schema(repeatability, acceptance["evidence_schemas"]["REPEATABILITY_REPORT_V3"], "repeatability report")
        (fixture_evidence / "repeatability-report.json").write_bytes(_canonical(repeatability))

        for label in roots:
            audit = evidence_docs[f"{label}_audit"]
            if audit["credential_keys_present"] or audit["network_attempt_count"] or audit["external_action_count"] or audit["output_paths"] != FIVE_PATHS:
                raise AssertionError("ASSERT-005 failed: execution audit")
        assertion_status["ASSERT-005"] = "PASS"
        for files in run_files.values():
            for path, data in files.items():
                _validate_normalization(path, data)
        assertion_status["ASSERT-006"] = "PASS"

        evidence_by_assertion = {item["id"]: item["evidence"] for item in acceptance["assertions"]}
        results = {"schema_version": "0.3", "runner": "python -m unittest tests.test_bundle -v", "exit_code": 0, "status": "PASS", "assertions": [{"id": assertion_id, "status": assertion_status[assertion_id], "evidence": evidence_by_assertion[assertion_id]} for assertion_id in sorted(assertion_status)]}
        _validate_schema(results, acceptance["evidence_schemas"]["TEST_RESULTS_V3"], "test results")
        (fixture_evidence / "test-results.json").write_bytes(_canonical(results))
        return {"status": "PASS", "fixture_root": str(fixture_root), "root_digest": run_1_root, "assertions": assertion_status}
    finally:
        if temporary is not None:
            temporary.cleanup()
