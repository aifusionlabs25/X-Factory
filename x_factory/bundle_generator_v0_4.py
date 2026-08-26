"""Deterministic, provider-free bundle generator for governed blueprint v0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONTRACT_FILES = {
    "output_bundle_manifest": "output_bundle_manifest.v0.3.json",
    "deterministic_generation": "deterministic_generation.v0.3.json",
    "acceptance_fixture": "acceptance_fixture.v0.3.json",
}
CONTRACT_HASHES = {
    "output_bundle_manifest": "737ce9dc75f49a0a463f6fc50495caa73703812b3b635ec9fcb6d2451b56f20d",
    "deterministic_generation": "1f72d796d40b0310e81775b6588c598a37d3c93386ed805d4c4ff02e8fe7f62c",
    "acceptance_fixture": "34537cda455215b9f3e61e8d6c0bed0d9cd017b6ac05b386c24a5fca7ac67d49",
}
CREDENTIAL_KEYS = (
    "ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY",
    "OPENAI_API_KEY", "OPENROUTER_API_KEY",
)
FIVE_PATHS = (
    "agent/AGENT.md", "agent/agent.spec.json", "bundle.manifest.json",
    "tests/fixtures/smoke.input.json", "tests/test_bundle.py",
)
FOUR_PAYLOAD_PATHS = (
    "agent/AGENT.md", "agent/agent.spec.json",
    "tests/fixtures/smoke.input.json", "tests/test_bundle.py",
)


class InvalidInputError(ValueError):
    pass


class BoundaryError(PermissionError):
    pass


class DeterminismError(RuntimeError):
    pass


@dataclass(frozen=True)
class GenerationResult:
    status: str
    run_label: str
    output_paths: tuple[str, ...]
    root_digest: str
    manifest_self_hash: str


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return unicodedata.normalize("NFC", text).encode("utf-8")


def normalized_scalar(value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidInputError("Expected a string blueprint value")
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def root_digest(files: Mapping[str, bytes]) -> str:
    records = [path.encode("utf-8") + b"\0" + sha256(files[path]).encode("ascii") + b"\n" for path in FOUR_PAYLOAD_PATHS]
    return sha256(b"".join(records))


def _load_json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
        if text.startswith("\ufeff"):
            raise InvalidInputError(f"{label} contains a UTF-8 BOM")
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidInputError(f"{label} is not valid UTF-8 JSON") from error


def _require_empty_directory(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise BoundaryError(f"{label} must be an existing directory")
    if any(resolved.iterdir()):
        raise BoundaryError(f"{label} must be empty")
    return resolved


def _safe_target(root: Path, relative: str) -> Path:
    target = (root / Path(relative)).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise BoundaryError(f"Path escapes declared root: {relative}") from error
    return target


def _install_runtime_guard() -> None:
    if os.environ.get("X_FACTORY_NETWORK_DISABLED") != "1":
        raise BoundaryError("X_FACTORY_NETWORK_DISABLED=1 is required")
    present = [key for key in CREDENTIAL_KEYS if os.environ.get(key)]
    if present:
        raise BoundaryError("Provider credential keys must be absent")

    def audit(event: str, _args: tuple[Any, ...]) -> None:
        if event.startswith("socket.") or event.startswith("subprocess.") or event in {"os.system", "os.exec", "os.spawn"}:
            raise BoundaryError(f"Blocked runtime action: {event}")

    sys.addaudithook(audit)


def _validate_roots(output_dir: Path, evidence_dir: Path, run_label: str) -> tuple[Path, Path]:
    if run_label not in {"RUN_1", "RUN_2"}:
        raise InvalidInputError("run_label must be RUN_1 or RUN_2")
    output = _require_empty_directory(output_dir, "output_dir")
    evidence = _require_empty_directory(evidence_dir, "evidence_dir")
    if output == evidence or output.parent != evidence.parent:
        raise BoundaryError("Output and evidence roots must be distinct siblings")
    expected_parent = "run-1" if run_label == "RUN_1" else "run-2"
    if output.name != "output" or evidence.name != "evidence" or output.parent.name != expected_parent:
        raise BoundaryError("Roots do not match the declared run-N/output and run-N/evidence model")
    return output, evidence


def _validate_contracts(contract_bytes_by_name: Mapping[str, bytes]) -> dict[str, Any]:
    if set(contract_bytes_by_name) != set(CONTRACT_FILES):
        raise InvalidInputError("Exactly the three named Phase 1.3 contract instances are required")
    contracts: dict[str, Any] = {}
    for name in CONTRACT_FILES:
        data = contract_bytes_by_name[name]
        if sha256(data) != CONTRACT_HASHES[name]:
            raise InvalidInputError(f"Approved contract hash mismatch: {name}")
        contracts[name] = _load_json_bytes(data, name)
    if contracts["output_bundle_manifest"].get("contract_id") != "CONTRACT-OUTPUT-BUNDLE-MANIFEST-V3":
        raise InvalidInputError("Output manifest contract ID mismatch")
    if contracts["deterministic_generation"].get("contract_id") != "CONTRACT-DETERMINISTIC-GENERATION-V3":
        raise InvalidInputError("Generation contract ID mismatch")
    if contracts["acceptance_fixture"].get("contract_id") != "CONTRACT-ACCEPTANCE-FIXTURE-V3":
        raise InvalidInputError("Acceptance contract ID mismatch")
    return contracts


def _validate_blueprint(blueprint: Any) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        raise InvalidInputError("Blueprint must be an object")
    required = {"schema_version", "candidate_id", "identity", "objectives", "capabilities", "boundaries", "requirements", "authority", "evaluation_plan"}
    if not required.issubset(blueprint):
        raise InvalidInputError("Blueprint is missing generator-required fields")
    if blueprint["schema_version"] not in {"0.1", "0.2"} or not isinstance(blueprint["candidate_id"], str):
        raise InvalidInputError("Blueprint identity is invalid")
    if not isinstance(blueprint["requirements"], list) or not isinstance(blueprint["evaluation_plan"].get("hard_rules"), list):
        raise InvalidInputError("Blueprint requirements and hard rules must be arrays")
    authority = blueprint["authority"]
    if not isinstance(authority, dict) or any(authority.get(key) is not False for key in ("build_authorized", "deployment_authorized", "production_approved")):
        raise InvalidInputError("Blueprint authority must remain false")
    return blueprint


def _validate_templates(generation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions = generation["template_set"]["definitions"]
    by_path = {item["output_path"]: item for item in definitions}
    if set(by_path) != set(FIVE_PATHS) or len(definitions) != 5:
        raise DeterminismError("Template paths do not match the five governed outputs")
    records: list[bytes] = []
    for item in sorted(definitions, key=lambda value: value["template_id"]):
        actual = sha256(item["source_utf8"].encode("utf-8"))
        if actual != item["source_sha256"]:
            raise DeterminismError(f"Template source hash mismatch: {item['template_id']}")
        records.append(item["template_id"].encode("utf-8") + b"\0" + actual.encode("ascii") + b"\n")
    if sha256(b"".join(records)) != generation["template_set"]["template_set_sha256"]:
        raise DeterminismError("Template-set hash mismatch")
    return by_path


def _render(blueprint: dict[str, Any], contracts: dict[str, Any]) -> dict[str, bytes]:
    generation = contracts["deterministic_generation"]
    manifest_contract = contracts["output_bundle_manifest"]
    templates = _validate_templates(generation)
    agent_name_raw = blueprint["identity"].get("agent_name")
    agent_name = agent_name_raw if isinstance(agent_name_raw, str) and agent_name_raw.strip() else blueprint["candidate_id"]
    hard_rules = sorted(normalized_scalar(item) for item in blueprint["evaluation_plan"]["hard_rules"])
    agent_md = templates["agent/AGENT.md"]["source_utf8"]
    replacements = {
        "$name": normalized_scalar(agent_name),
        "$purpose": normalized_scalar(blueprint["objectives"]["primary_job"]),
        "$role": normalized_scalar(blueprint["identity"]["role"]),
        "$hard_rules": "\n".join(f"- {item}" for item in hard_rules),
    }
    for token, value in replacements.items():
        agent_md = agent_md.replace(token, value)
    outputs: dict[str, bytes] = {
        "agent/AGENT.md": unicodedata.normalize("NFC", agent_md).encode("utf-8"),
        "agent/agent.spec.json": canonical_json({key: blueprint[key] for key in ("schema_version", "candidate_id", "identity", "objectives", "capabilities", "boundaries", "requirements", "authority")}),
        "tests/fixtures/smoke.input.json": canonical_json({"candidate_id": blueprint["candidate_id"], "fixture_id": "FIXTURE-SYNTHETIC-BUNDLE-V3", "provider_free": True, "user_input": "Create the approved deterministic synthetic bundle."}),
        "tests/test_bundle.py": templates["tests/test_bundle.py"]["source_utf8"].encode("utf-8"),
    }
    payload_hashes = [{"path": path, "sha256": sha256(outputs[path])} for path in FOUR_PAYLOAD_PATHS]
    manifest = {
        "schema_version": "0.3",
        "manifest_contract_id": manifest_contract["contract_id"],
        "generation_contract_id": generation["contract_id"],
        "template_set_id": generation["template_set"]["template_set_id"],
        "template_set_sha256": generation["template_set"]["template_set_sha256"],
        "files": payload_hashes,
        "root_digest": root_digest(outputs),
        "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    outputs["bundle.manifest.json"] = canonical_json(manifest)
    if tuple(sorted(outputs)) != FIVE_PATHS:
        raise DeterminismError("Rendered output set is not the exact five-path set")
    return outputs


def generate(blueprint_bytes: bytes, contract_bytes_by_name: Mapping[str, bytes], output_dir: Path, evidence_dir: Path, run_label: str) -> GenerationResult:
    _install_runtime_guard()
    output_root, evidence_root = _validate_roots(Path(output_dir), Path(evidence_dir), run_label)
    contracts = _validate_contracts(contract_bytes_by_name)
    blueprint = _validate_blueprint(_load_json_bytes(blueprint_bytes, "blueprint"))
    outputs = _render(blueprint, contracts)
    for relative in FIVE_PATHS:
        target = _safe_target(output_root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(outputs[relative])
    file_records = [{"path": path, "sha256": sha256(outputs[path])} for path in FIVE_PATHS]
    root = root_digest(outputs)
    manifest_hash = sha256(outputs["bundle.manifest.json"])
    audit = {
        "schema_version": "0.3", "run_label": run_label,
        "network_policy": "DISABLED_BY_TEST_HARNESS",
        "credential_keys_scanned": list(CREDENTIAL_KEYS), "credential_keys_present": [],
        "network_attempt_count": 0, "external_action_count": 0, "output_paths": list(FIVE_PATHS),
    }
    hashes = {"schema_version": "0.3", "run_label": run_label, "algorithm": "SHA-256", "files_count": 5, "files": file_records, "root_digest": root, "manifest_self_hash": manifest_hash}
    _safe_target(evidence_root, "execution-audit.json").write_bytes(canonical_json(audit))
    _safe_target(evidence_root, "file-hashes.json").write_bytes(canonical_json(hashes))
    return GenerationResult("SUCCESS", run_label, FIVE_PATHS, root, manifest_hash)


def _read_contracts(directory: Path) -> dict[str, bytes]:
    return {name: (directory / filename).read_bytes() for name, filename in CONTRACT_FILES.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--blueprint", type=Path, required=True)
    generate_parser.add_argument("--contracts", type=Path, required=True)
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--evidence", type=Path, required=True)
    generate_parser.add_argument("--run-label", choices=("RUN_1", "RUN_2"), required=True)
    args = parser.parse_args()
    try:
        result = generate(args.blueprint.read_bytes(), _read_contracts(args.contracts), args.output, args.evidence, args.run_label)
    except InvalidInputError as error:
        print(str(error), file=sys.stderr)
        return 2
    except BoundaryError as error:
        print(str(error), file=sys.stderr)
        return 3
    except DeterminismError as error:
        print(str(error), file=sys.stderr)
        return 4
    print(json.dumps({"status": result.status, "run_label": result.run_label, "output_paths": result.output_paths, "root_digest": result.root_digest, "manifest_self_hash": result.manifest_self_hash}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
