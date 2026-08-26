#!/usr/bin/env python3
"""Prepare or execute one approval-bound, zero-tool Vera build verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PROVIDER = "openai-codex"
MODEL = "gpt-5.6-luna"
PROFILE = "vera"
RUN_ID = "contained-vera-build-verification-001"
BUILD_ID = "controlled-build-004"
EXECUTION_MODE = "BROKERED_NO_TOOLS"
TOOL_POLICY = "ZERO_TOOLS_NO_MCP_NO_DESKTOP_UI"
SCOPE = "EXACT_SANITIZED_CONTROLLED_BUILD_004_PAYLOAD_FOR_ONE_CONTAINED_VERA_BUILD_VERIFICATION"
GOVERNED_MARKER = "X_FACTORY_GOVERNED_BUILD_VERIFICATION_V0_1"
BLUEPRINT_SHA = "sha256:3d2302ae05794d06d6a527a43fcf1515cc3e2a87f094afa2398d84c0c07e908a"
SPEC_EVALUATION_SHA = "sha256:f80c28f2465a22cb26524ec46136f8692cd871ced0636e06ebd4acaee8cef78f"
BUILD_RECORD_SHA = "sha256:a13f57baa8608a8e1b612cc29f823fcba8e15d68ec75f7a1ef4edb0fd3927b76"
CANDIDATE_ROOT = "sha256:379e7cdd8fab6df6fda8a9fb74d5f5a087effa0562fd5f5f585b8afe07db7e79"
CONTRACT_HASHES = {
    "output_bundle_manifest": "sha256:737ce9dc75f49a0a463f6fc50495caa73703812b3b635ec9fcb6d2451b56f20d",
    "deterministic_generation": "sha256:1f72d796d40b0310e81775b6588c598a37d3c93386ed805d4c4ff02e8fe7f62c",
    "acceptance_fixture": "sha256:34537cda455215b9f3e61e8d6c0bed0d9cd017b6ac05b386c24a5fca7ac67d49",
}
EXPECTED_OUTPUTS = (
    "agent/AGENT.md",
    "agent/agent.spec.json",
    "bundle.manifest.json",
    "tests/fixtures/smoke.input.json",
    "tests/test_bundle.py",
)
DISABLED_TOOLSETS = {
    "a2a", "bfl", "browser", "clarify", "code_execution", "computer_use",
    "context_engine", "cronjob", "delegation", "desktop_ui", "discord",
    "discord_admin", "file", "homeassistant", "image_gen", "kanban",
    "memory", "project", "session_search", "skills", "spotify", "stt",
    "terminal", "todo", "tts", "video", "video_gen", "vision", "web",
    "x_search", "yuanbao",
}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SESSION_ID = re.compile(r"session_id:\s*([0-9]{8}_[0-9]{6}_[a-z0-9]+)")
WINDOWS_PATH = re.compile(r"(?i)[a-z]:\\\\")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate(value: Any, schema: Any, label: str) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{label} schema validation failed: " + "; ".join(error.message for error in errors))


def assert_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise PermissionError(f"{label} hash mismatch: expected {expected}, received {actual}")


def extract_last_json(text: str) -> dict[str, Any]:
    cleaned = ANSI.sub("", text)
    decoder = json.JSONDecoder()
    values: list[dict[str, Any]] = []
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    if not values:
        raise ValueError("Hermes response did not contain a JSON object")
    return max(values, key=lambda value: len(json.dumps(value, sort_keys=True)))


def extract_session_id(text: str) -> str:
    matches = SESSION_ID.findall(ANSI.sub("", text))
    if not matches:
        raise ValueError("Hermes output did not include a session_id")
    return matches[-1]


def verify_vera_profile(root: Path, runtime_profile_root: Path) -> str:
    mirror = root / "profiles" / PROFILE / "config.yaml"
    runtime = runtime_profile_root / PROFILE / "config.yaml"
    if not mirror.is_file() or not runtime.is_file() or mirror.read_bytes() != runtime.read_bytes():
        raise PermissionError("Vera runtime profile is missing or differs from the factory mirror")
    config = yaml.safe_load(runtime.read_text(encoding="utf-8"))
    disabled = set(config.get("agent", {}).get("disabled_toolsets", []))
    checks = (
        config.get("model", {}).get("provider") == PROVIDER,
        config.get("model", {}).get("default") == MODEL,
        config.get("platform_toolsets", {}).get("cli") == ["no_mcp"],
        DISABLED_TOOLSETS <= disabled,
        config.get("memory", {}).get("memory_enabled") is False,
        config.get("delegation", {}).get("orchestrator_enabled") is False,
        config.get("approvals", {}).get("cron_mode") == "deny",
    )
    if not all(checks):
        raise PermissionError("Vera profile is not the approved cognition-only Luna configuration")
    return sha256_file(runtime)


def runtime_zero_tools_preflight(root: Path) -> dict[str, Any]:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    command = [
        executable, "--profile", PROFILE, "chat", "-Q", "-v", "--reasoning", "low",
        "--max-turns", "2", "--source", "tool", "--in", str(root), "-q",
        "GOVERNED BUILD VERIFICATION PREFLIGHT. Return exactly PREFLIGHT_ZERO_TOOLS. Do not use a tool.",
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    combined = completed.stdout + "\n" + completed.stderr
    checks = {
        "api_request_tools_zero": bool(re.search(r"API Request.*Tools:\s*0", combined)),
        "no_tools_selected": "No tools selected" in combined,
        "no_tools_loaded": "No tools loaded" in combined,
    }
    if completed.returncode != 0 or not all(checks.values()):
        raise PermissionError(f"Vera runtime allow-none preflight failed: {checks}")
    return {"profile": PROFILE, "session_id": extract_session_id(combined), "runtime_tool_count": 0, "checks": checks}


def session_tool_count(session_id: str, root: Path) -> int:
    executable = shutil.which("hermes")
    completed = subprocess.run(
        [executable, "--profile", PROFILE, "sessions", "export", "-", "--format", "jsonl", "--session-id", session_id, "--max-tool-calls", "0", "--dry-run"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise PermissionError("Vera session did not satisfy max-tool-calls=0")
    count = int(json.loads(completed.stdout.splitlines()[0])["tool_call_count"])
    if count != 0:
        raise PermissionError(f"Vera session recorded {count} tool calls")
    return count


def run_vera(prompt: str, root: Path) -> tuple[dict[str, Any], str, str]:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    hermes_python = Path(executable).with_name("python.exe")
    bridge = root / "scripts" / "hermes_prompt_bridge.py"
    if not hermes_python.is_file() or not bridge.is_file():
        raise RuntimeError("Hermes prompt bridge prerequisites are missing")
    prompt_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", prefix="hermes-approved-build-verification-", delete=False) as handle:
            handle.write(prompt)
            prompt_path = Path(handle.name)
        env = os.environ.copy()
        env["HERMES_API_CALL_STALE_TIMEOUT"] = "480"
        completed = subprocess.run(
            [str(hermes_python), str(bridge), "--profile", PROFILE, "--reasoning", "high", "--factory-root", str(root), "--prompt-file", str(prompt_path)],
            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False,
        )
    finally:
        if prompt_path is not None:
            prompt_path.unlink(missing_ok=True)
    combined = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    if completed.returncode != 0:
        raise RuntimeError(f"Hermes Vera failed with exit code {completed.returncode}: {combined[-2000:]}")
    return extract_last_json(completed.stdout), combined, extract_session_id(combined)


def make_payload(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    build_dir = root / "builds" / "controlled" / BUILD_ID
    record_path = build_dir / "controlled_build_record.v0.1.json"
    verification_path = root / "verification" / "controlled-build-004-attempt-1" / "verification-report.v0.1.json"
    blueprint_path = root / "runs" / "contained" / "contained-real-card-proof-004" / "aria" / "x_agent_blueprint.v0.1.json"
    spec_evaluation_path = root / "runs" / "contained" / "contained-real-card-proof-004" / "vera" / "evaluation.v0.1.json"
    evaluation_schema_path = root / "contracts" / "build_verification_evaluation.v0.1.schema.json"
    assert_hash(blueprint_path, BLUEPRINT_SHA, "Frozen blueprint")
    assert_hash(spec_evaluation_path, SPEC_EVALUATION_SHA, "Specification evaluation")
    assert_hash(record_path, BUILD_RECORD_SHA, "Controlled build record")
    record = load_json(record_path)
    verification = load_json(verification_path)
    if record.get("build_id") != BUILD_ID or record.get("acceptance", {}).get("status") != "PASS":
        raise PermissionError("Controlled build record is not the approved passing build")
    if verification.get("build_record_sha256") != BUILD_RECORD_SHA or verification.get("status") != "PASS":
        raise PermissionError("Independent verification does not bind the approved passing build")
    if any(value is not False for value in record.get("authority", {}).values()):
        raise PermissionError("Controlled build record contains unexpected authority")
    if any(value is not False for value in verification.get("authority", {}).values()):
        raise PermissionError("Independent verification contains unexpected authority")

    output_root = build_dir / "seed" / "run-1" / "output"
    actual_paths = tuple(sorted(path.relative_to(output_root).as_posix() for path in output_root.rglob("*") if path.is_file()))
    if actual_paths != tuple(sorted(EXPECTED_OUTPUTS)):
        raise PermissionError(f"Candidate output path set differs from the frozen five-file set: {actual_paths}")
    candidate_files: dict[str, Any] = {}
    for relative in EXPECTED_OUTPUTS:
        path = output_root / Path(relative)
        digest = sha256_file(path)
        if record["seed"]["output_files"].get(relative) != digest:
            raise PermissionError(f"Candidate file hash mismatch: {relative}")
        candidate_files[relative] = {
            "sha256": digest,
            "content": load_json(path) if path.suffix == ".json" else path.read_text(encoding="utf-8"),
        }

    contract_specs = {
        "output_bundle_manifest": "output_bundle_manifest.v0.3.json",
        "deterministic_generation": "deterministic_generation.v0.3.json",
        "acceptance_fixture": "acceptance_fixture.v0.3.json",
    }
    contracts: dict[str, Any] = {}
    for key, name in contract_specs.items():
        path = root / "contracts" / "phase1_3" / name
        assert_hash(path, CONTRACT_HASHES[key], key)
        contracts[key] = load_json(path)

    repeatability_path = build_dir / "fixture" / "fixture-evidence" / "repeatability-report.json"
    test_results_path = build_dir / "fixture" / "fixture-evidence" / "test-results.json"
    hashes = {
        "blueprint": BLUEPRINT_SHA,
        "specification_evaluation": SPEC_EVALUATION_SHA,
        "build_record": BUILD_RECORD_SHA,
        "independent_verification": sha256_file(verification_path),
        "candidate_root_digest": CANDIDATE_ROOT,
        "evaluation_schema": sha256_file(evaluation_schema_path),
    }
    payload = {
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "governed_run_marker": GOVERNED_MARKER,
        "build_id": BUILD_ID,
        "authority": {
            "verification_only": True,
            "install_to_live_factory_authorized": False,
            "deployment_authorized": False,
            "production_approved": False,
        },
        "frozen_specification": {
            "blueprint_sha256": BLUEPRINT_SHA,
            "blueprint": load_json(blueprint_path),
            "specification_evaluation_sha256": SPEC_EVALUATION_SHA,
            "specification_evaluation": load_json(spec_evaluation_path),
            "contract_hashes": CONTRACT_HASHES,
            "contracts": contracts,
        },
        "candidate": {
            "candidate_root_digest": CANDIDATE_ROOT,
            "expected_paths": list(EXPECTED_OUTPUTS),
            "actual_paths": list(actual_paths),
            "files": candidate_files,
        },
        "build_evidence": {
            "build_record_sha256": BUILD_RECORD_SHA,
            "sanitized_build_record": {
                "schema_version": record["schema_version"],
                "build_id": record["build_id"],
                "source": record["source"],
                "implementation": record["implementation"],
                "seed_output_files": record["seed"]["output_files"],
                "seed_evidence_files": record["seed"]["evidence_files"],
                "acceptance": record["acceptance"],
                "authority": record["authority"],
            },
            "independent_verification_sha256": hashes["independent_verification"],
            "independent_verification": verification,
            "repeatability_report_sha256": sha256_file(repeatability_path),
            "repeatability_report": load_json(repeatability_path),
            "test_results_sha256": sha256_file(test_results_path),
            "test_results": load_json(test_results_path),
            "deviations_from_blueprint": [],
        },
        "evaluation_rules": {
            "all_fourteen_gates_must_pass_for_build_verified": True,
            "any_blocking_defect_requires_revision": True,
            "do_not_rewrite_candidate": True,
            "do_not_grant_install_deployment_or_production_authority": True,
            "required_semantic_questions": [
                "Did the candidate implement the frozen blueprint without unauthorized additions, omissions, or semantic substitutions?",
                "Did the builder obey the declared origin policy and deterministic contracts?",
                "Is the evidence chain sufficient to prove the candidate evaluated is exactly the candidate built and accepted?",
                "Did any action occur outside the authorized local-staging implementation scope?",
            ],
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if WINDOWS_PATH.search(serialized):
        raise PermissionError("Sanitized Vera payload contains an absolute Windows path")
    return payload, hashes


def approval_path(root: Path, manifest_hash: str) -> Path:
    suffix = manifest_hash.removeprefix("sha256:")[:12]
    return root / "approvals" / "approved" / f"{BUILD_ID}.vera-build-verification.{suffix}.approval.json"


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

    evaluation_schema_path = root / "contracts" / "build_verification_evaluation.v0.1.schema.json"
    manifest_schema = load_json(root / "contracts" / "build_verification_disclosure_manifest.v0.1.schema.json")
    approval_schema = load_json(root / "contracts" / "build_verification_approval.v0.1.schema.json")
    record_schema = load_json(root / "contracts" / "contained_build_verification_record.v0.1.schema.json")
    evaluation_schema = load_json(evaluation_schema_path)
    Draft202012Validator.check_schema(evaluation_schema)
    profile_hash = verify_vera_profile(root, args.runtime_profile_root.resolve())
    payload, bound_hashes = make_payload(root)

    pending_dir = root / "approvals" / "pending"
    payload_path = pending_dir / f"{BUILD_ID}.vera-build-verification.payload.json"
    write_json(payload_path, payload)
    payload_hash = sha256_file(payload_path)
    manifest = {
        "schema_version": "0.1",
        "manifest_id": "DISCLOSURE-CONTROLLED-BUILD-004-VERA-V1",
        "approval_id": "APPROVAL-CONTROLLED-BUILD-004-VERA-V1",
        "purpose": "Permit one contained, cognition-only Vera evaluation of the exact sanitized controlled-build-004 candidate and evidence",
        "build_id": BUILD_ID,
        "payload_sha256": payload_hash,
        "bound_hashes": bound_hashes,
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": [PROFILE],
        "profile_config_hashes": {PROFILE: profile_hash},
        "scope": SCOPE,
        "execution_mode": EXECUTION_MODE,
        "tool_policy": TOOL_POLICY,
        "authority": payload["authority"],
    }
    validate(manifest, manifest_schema, "Disclosure manifest")
    manifest_path = pending_dir / f"{BUILD_ID}.vera-build-verification.disclosure-manifest.json"
    write_json(manifest_path, manifest)
    manifest_hash = sha256_file(manifest_path)
    required_approval = approval_path(root, manifest_hash)
    preview = {
        "schema_version": "0.1",
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": [PROFILE],
        "tool_policy": TOOL_POLICY,
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "exact_disclosure_manifest": manifest,
        "exact_sanitized_payload": payload,
        "evaluation_schema_sha256": bound_hashes["evaluation_schema"],
        "approval_record_required": str(required_approval.relative_to(root)),
        "provider_transmission_performed": False,
    }
    preview_path = pending_dir / f"{BUILD_ID}.vera-build-verification.payload-preview.json"
    write_json(preview_path, preview)
    if args.prepare:
        print(json.dumps({
            "status": "APPROVAL_REQUIRED",
            "disclosure_manifest_sha256": manifest_hash,
            "payload_sha256": payload_hash,
            "payload_preview": str(preview_path),
            "approval_record_required": str(required_approval),
            "provider_transmission_performed": False,
        }, indent=2))
        return 2

    if not required_approval.is_file():
        raise PermissionError(f"Exact build-verification approval is missing: {required_approval}")
    approval = load_json(required_approval)
    validate(approval, approval_schema, "Build-verification approval")
    if approval["disclosure_manifest_sha256"] != manifest_hash or approval["payload_sha256"] != payload_hash:
        raise PermissionError("Approval does not bind the exact disclosure manifest and sanitized payload")
    approval_hash = sha256_file(required_approval)

    run_dir = root / "runs" / "contained" / RUN_ID
    if run_dir.exists():
        raise FileExistsError(f"Build-verification run directory already exists: {run_dir}")
    preflight = runtime_zero_tools_preflight(root)
    governed = {
        "governed_run_marker": GOVERNED_MARKER,
        "execution_mode": EXECUTION_MODE,
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "approval_sha256": approval_hash,
    }
    prompt = (
        "X-AGENT FACTORY CONTAINED BUILD VERIFICATION. You are Vera, an independent evaluator. "
        "You have zero tools. Use only the inline approved JSON. Do not request, infer, or claim access to any local path, repository, credential, source, provider, network, or external system. "
        "Do not rewrite or repair the candidate. Evaluate all fourteen gates strictly from evidence. "
        "Return one JSON object only, valid against OUTPUT_SCHEMA. BUILD_VERIFIED requires every gate PASS and defects empty. "
        "Your authority is verification only and cannot authorize installation, deployment, or production.\n"
        "GOVERNANCE=" + json.dumps(governed, sort_keys=True, separators=(",", ":")) + "\n"
        "PAYLOAD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        "OUTPUT_SCHEMA=" + json.dumps(evaluation_schema, sort_keys=True, separators=(",", ":"))
    )
    evaluation, raw, session_id = run_vera(prompt, root)
    tool_calls = session_tool_count(session_id, root)
    validate(evaluation, evaluation_schema, "Vera build evaluation")
    if evaluation["evaluated_build_record_sha256"] != BUILD_RECORD_SHA:
        raise PermissionError("Vera result does not bind the exact controlled build record")
    if evaluation["evaluated_blueprint_sha256"] != BLUEPRINT_SHA:
        raise PermissionError("Vera result does not bind the exact frozen blueprint")
    if evaluation["evaluated_candidate_root_digest"] != CANDIDATE_ROOT:
        raise PermissionError("Vera result does not bind the exact candidate root digest")

    run_dir.mkdir(parents=True)
    evaluation_path = run_dir / "vera" / "build-evaluation.v0.1.json"
    raw_path = run_dir / "vera" / "raw-response.txt"
    write_json(evaluation_path, evaluation)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8", newline="\n")
    record = {
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "governed_run_marker": GOVERNED_MARKER,
        "execution_mode": EXECUTION_MODE,
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "approval_sha256": approval_hash,
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": [PROFILE],
        "tool_policy": TOOL_POLICY,
        "runtime_preflight": preflight,
        "session": {"session_id": session_id, "virgin_session": True, "tool_call_count": tool_calls},
        "artifacts": {"evaluation_sha256": sha256_file(evaluation_path), "verdict": evaluation["verdict"], "completed_at": datetime.now(timezone.utc).isoformat()},
        "authority": payload["authority"],
    }
    validate(record, record_schema, "Contained build-verification record")
    write_json(run_dir / "contained_build_verification_record.v0.1.json", record)
    print(json.dumps({"status": "COMPLETE", "verdict": evaluation["verdict"], "run_dir": str(run_dir), "record": record}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
