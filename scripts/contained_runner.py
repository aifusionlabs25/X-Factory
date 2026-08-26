#!/usr/bin/env python3
"""Broker approved payloads to cognition-only Hermes profiles with zero tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PROFILES = ("atlas", "aria", "vera")
PROVIDER = "openai-codex"
MODEL = "gpt-5.6-luna"
EXECUTION_MODE = "BROKERED_NO_TOOLS"
TOOL_POLICY = "ZERO_TOOLS_NO_MCP_NO_DESKTOP_UI"
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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} must remain inside the factory root") from error
    return resolved


def validate(instance: Any, schema: Any, label: str) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        raise ValueError(f"{label} schema validation failed: " + "; ".join(error.message for error in errors))


def verify_profile_configs(factory_root: Path, runtime_profile_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for profile in PROFILES:
        mirror = factory_root / "profiles" / profile / "config.yaml"
        runtime = runtime_profile_root / profile / "config.yaml"
        if not mirror.is_file() or not runtime.is_file():
            raise ValueError(f"Missing contained config for {profile}")
        if mirror.read_bytes() != runtime.read_bytes():
            raise ValueError(f"Runtime config for {profile} differs from the factory-controlled mirror")
        config = yaml.safe_load(runtime.read_text(encoding="utf-8"))
        if config.get("platform_toolsets", {}).get("cli") != ["no_mcp"]:
            raise ValueError(f"{profile} CLI tool surface is not the explicit no_mcp sentinel")
        disabled = set(config.get("agent", {}).get("disabled_toolsets", []))
        missing = sorted(DISABLED_TOOLSETS - disabled)
        if missing:
            raise ValueError(f"{profile} is missing disabled toolsets: {', '.join(missing)}")
        if config.get("memory", {}).get("memory_enabled") is not False:
            raise ValueError(f"{profile} memory must be disabled")
        if config.get("delegation", {}).get("orchestrator_enabled") is not False:
            raise ValueError(f"{profile} delegation must be disabled")
        if config.get("approvals", {}).get("cron_mode") != "deny":
            raise ValueError(f"{profile} cron approvals must be denied")
        hashes[profile] = sha256_file(runtime)
    return hashes


def approval_path(factory_root: Path, card: dict[str, Any], manifest_hash: str) -> Path:
    suffix = manifest_hash.removeprefix("sha256:")[:12]
    return factory_root / "approvals" / "approved" / f"{card['card_id']}.{suffix}.approval.json"


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


def runtime_zero_tools_preflight(profile: str, factory_root: Path) -> dict[str, Any]:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    command = [
        executable,
        "--profile", profile,
        "chat", "-Q", "-v",
        "--reasoning", "low",
        "--max-turns", "2",
        "--source", "tool",
        "--in", str(factory_root),
        "-q", "GOVERNED FACTORY PREFLIGHT. Return exactly PREFLIGHT_ZERO_TOOLS. Do not use a tool.",
    ]
    completed = subprocess.run(
        command,
        cwd=factory_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0:
        raise RuntimeError(f"Runtime tool preflight failed for {profile}")
    checks = {
        "api_request_tools_zero": bool(re.search(r"API Request.*Tools:\s*0", combined)),
        "no_tools_selected": "No tools selected" in combined,
        "no_tools_loaded": "No tools loaded" in combined,
    }
    if not all(checks.values()):
        raise PermissionError(f"Runtime allow-none assertion failed for {profile}: {checks}")
    return {
        "profile": profile,
        "session_id": extract_session_id(combined),
        "runtime_tool_count": 0,
        "checks": checks,
    }


def session_tool_count(profile: str, session_id: str, factory_root: Path) -> int:
    executable = shutil.which("hermes")
    command = [
        executable,
        "--profile", profile,
        "sessions", "export", "-",
        "--format", "jsonl",
        "--session-id", session_id,
        "--max-tool-calls", "0",
        "--dry-run",
    ]
    completed = subprocess.run(command, cwd=factory_root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
    if completed.returncode != 0 or not completed.stdout.strip():
        raise PermissionError(f"Session {session_id} for {profile} did not satisfy max-tool-calls=0")
    metadata = json.loads(completed.stdout.splitlines()[0])
    count = int(metadata["tool_call_count"])
    if count != 0:
        raise PermissionError(f"Session {session_id} for {profile} recorded {count} tool calls")
    return count


def run_profile(profile: str, reasoning: str, prompt: str, factory_root: Path) -> tuple[dict[str, Any], str, str]:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    command = [
        executable,
        "--profile", profile,
        "chat", "-Q",
        "--reasoning", reasoning,
        "--max-turns", "4",
        "--source", "tool",
        "--in", str(factory_root),
        "-q", prompt,
    ]
    runtime_env = os.environ.copy()
    runtime_env["HERMES_API_CALL_STALE_TIMEOUT"] = "480"
    completed = subprocess.run(
        command,
        cwd=factory_root,
        env=runtime_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    combined = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    if completed.returncode != 0:
        raise RuntimeError(f"Hermes {profile} failed with exit code {completed.returncode}: {combined[-2000:]}")
    return extract_last_json(completed.stdout), combined, extract_session_id(combined)


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stage_prompt(role: str, payload: dict[str, Any], schema: dict[str, Any]) -> str:
    common = (
        "X-AGENT FACTORY CONTAINED PROOF. execution_mode=BROKERED_NO_TOOLS. "
        "You have zero tools and must not request or infer any local path, repository, credential, private client identity, or raw source. "
        "Use only the inline JSON. Return one JSON object only, with no Markdown or commentary. "
        "Build, deployment, production, provider actions, and external actions are not authorized. "
    )
    if role == "atlas":
        instruction = (
            "Act as Atlas. Preserve the intake exactly, normalize only formatting, invent nothing, and return an object valid against the supplied intake schema. "
            "The component card is context for safe routing, not authority to add requirements."
        )
    elif role == "aria":
        instruction = (
            "Act as Aria. Produce the smallest complete blueprint valid against the supplied blueprint schema. "
            "Select the component only where its capabilities support an explicit requirement; cite only its safe evidence_id. "
            "Set specification_status to FROZEN_FOR_REVIEW and every authority boolean to false."
        )
    else:
        instruction = (
            "Act as Vera. Independently evaluate the frozen blueprint against the intake, safe card, blueprint hash, and evaluation schema. "
            "Do not rewrite the blueprint. Return the strictest evidence-supported verdict."
        )
    return common + instruction + "\nPAYLOAD=" + compact(payload) + "\nOUTPUT_SCHEMA=" + compact(schema)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--runtime-profile-root", type=Path, default=Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "profiles")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.execute:
        raise ValueError("Choose exactly one of --prepare or --execute")

    root = args.factory_root.resolve()
    card_path = require_within(args.card, root, "card")
    intake_path = require_within(args.intake, root, "intake")
    allowed_card_root = (root / "cards" / "pending").resolve()
    allowed_intake_root = (root / "intakes" / "approved").resolve()
    card_path.relative_to(allowed_card_root)
    intake_path.relative_to(allowed_intake_root)

    card = load_json(card_path)
    intake = load_json(intake_path)
    card_schema = load_json(root / "contracts" / "model_safe_component_card.v0.1.schema.json")
    approval_schema = load_json(root / "contracts" / "component_card_approval.v0.1.schema.json")
    disclosure_schema = load_json(root / "contracts" / "disclosure_manifest.v0.1.schema.json")
    intake_schema = load_json(root / "contracts" / "intake.v0.1.schema.json")
    blueprint_schema = load_json(root / "contracts" / "x_agent_blueprint.v0.1.schema.json")
    evaluation_schema = load_json(root / "contracts" / "evaluation_contract.v0.1.schema.json")
    run_schema = load_json(root / "contracts" / "contained_run_record.v0.1.schema.json")
    validate(card, card_schema, "component card")
    validate(intake, intake_schema, "intake")
    card_hash = sha256_file(card_path)
    intake_hash = sha256_file(intake_path)
    report_path = card_path.with_name(card_path.stem + ".sanitization-report.json")
    if not report_path.is_file():
        raise ValueError("Sanitization report is missing beside the pending card")
    disclosure_report = load_json(report_path)
    disclosure_report_hash = sha256_file(report_path)
    if disclosure_report.get("output_card_sha256") != card_hash:
        raise ValueError("Sanitization report does not bind the exact card bytes")
    mapping = disclosure_report.get("mapping_summary", {})
    if mapping.get("unmapped_source_capabilities") != 0 or mapping.get("unmapped_source_limitations") != 0:
        raise ValueError("Sanitization report contains unmapped source statements")
    if any(value != "none" for value in disclosure_report.get("semantic_privacy_classification", {}).values()):
        raise ValueError("Semantic privacy classification is not clean")
    profile_hashes = verify_profile_configs(root, args.runtime_profile_root.resolve())

    disclosure_manifest = {
        "schema_version": "0.1",
        "manifest_id": "DISCLOSURE-DETERMINISTIC-BUNDLE-GENERATOR-V1",
        "approval_id": "APPROVAL-DETERMINISTIC-BUNDLE-GENERATOR-V1",
        "purpose": "Prove one sanitized real-derived component card can traverse Atlas to Aria to Vera without exposing sealed source material",
        "card_id": card["card_id"],
        "card_sha256": card_hash,
        "card_schema_version": card["schema_version"],
        "disclosure_report_sha256": disclosure_report_hash,
        "sanitizer_version": disclosure_report["sanitizer"],
        "sealed_source_record_hash": disclosure_report["sealed_record_hash"],
        "intake_sha256": intake_hash,
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": list(PROFILES),
        "profile_config_hashes": profile_hashes,
        "scope": "EXACT_CARD_AND_MODEL_GENERATED_DERIVATIVES_FOR_ONE_CONTAINED_ATLAS_ARIA_VERA_PROOF",
        "execution_mode": EXECUTION_MODE,
        "tool_policy": TOOL_POLICY,
        "governed_run_rule": "ONLY_A_BROKER_RUN_RECORD_BOUND_TO_THIS_MANIFEST_CAN_ASSERT_FACTORY_LIFECYCLE_AUTHORITY",
    }
    validate(disclosure_manifest, disclosure_schema, "disclosure manifest")
    disclosure_dir = root / "disclosures" / "pending"
    manifest_path = disclosure_dir / f"{card['card_id']}.{card_hash[-12:]}.disclosure-manifest.json"
    write_json(manifest_path, disclosure_manifest)
    manifest_hash = sha256_file(manifest_path)
    required_approval = approval_path(root, card, manifest_hash)

    preview = {
        "schema_version": "0.1",
        "execution_mode": EXECUTION_MODE,
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": list(PROFILES),
        "tool_policy": TOOL_POLICY,
        "card_sha256": card_hash,
        "disclosure_report_sha256": disclosure_report_hash,
        "disclosure_manifest_sha256": manifest_hash,
        "intake_sha256": intake_hash,
        "exact_model_safe_card": card,
        "exact_sanitization_report": disclosure_report,
        "exact_disclosure_manifest": disclosure_manifest,
        "synthetic_proof_intake": intake,
        "allowed_payload_scope": "EXACT_CARD_AND_MODEL_GENERATED_DERIVATIVES_FOR_ONE_CONTAINED_ATLAS_ARIA_VERA_PROOF",
        "approval_record_required": str(required_approval.relative_to(root)),
        "provider_transmission_performed": False,
        "profile_config_hashes": profile_hashes,
    }
    preview_path = root / "approvals" / "pending" / f"{card['card_id']}.{manifest_hash[-12:]}.payload-preview.json"
    write_json(preview_path, preview)
    if args.prepare:
        print(json.dumps({"status": "APPROVAL_REQUIRED", "disclosure_manifest_sha256": manifest_hash, "card_sha256": card_hash, "payload_preview": str(preview_path), "approval_record_required": str(required_approval)}, indent=2))
        return 2

    if not required_approval.is_file():
        raise PermissionError(f"Exact payload approval is missing: {required_approval}")
    approval = load_json(required_approval)
    validate(approval, approval_schema, "approval")
    if approval["approval_id"] != disclosure_manifest["approval_id"]:
        raise PermissionError("Approval ID does not match the disclosure manifest")
    if approval["disclosure_manifest_sha256"] != manifest_hash:
        raise PermissionError("Approval does not match the exact disclosure manifest bytes")
    if approval["card_id"] != card["card_id"] or approval["card_sha256"] != card_hash:
        raise PermissionError("Approval does not match the exact card bytes")
    if approval["disclosure_report_sha256"] != disclosure_report_hash:
        raise PermissionError("Approval does not match the exact disclosure report bytes")
    approval_hash = sha256_file(required_approval)

    run_id = intake["run_id"]
    run_dir = root / "runs" / "contained" / run_id
    atlas_intake_path = run_dir / "atlas" / "intake.v0.1.json"
    atlas_raw_path = run_dir / "atlas" / "raw-response.txt"
    if run_dir.exists():
        existing_files = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()}
        allowed_partial_files = {"atlas/intake.v0.1.json", "atlas/raw-response.txt"}
        if not existing_files or not existing_files.issubset(allowed_partial_files) or not allowed_partial_files.issubset(existing_files):
            raise FileExistsError(f"Contained run directory is not a resumable Atlas-only partial run: {run_dir}")

    runtime_preflight = {
        profile: runtime_zero_tools_preflight(profile, root)
        for profile in PROFILES
    }
    run_dir.mkdir(parents=True, exist_ok=True)

    governed = {"governed_run_marker": "X_FACTORY_GOVERNED_RUN_V0_1", "execution_mode": EXECUTION_MODE, "disclosure_manifest_hash": manifest_hash, "approval_hash": approval_hash}
    if atlas_intake_path.is_file() and atlas_raw_path.is_file():
        atlas = load_json(atlas_intake_path)
        atlas_raw = atlas_raw_path.read_text(encoding="utf-8")
        atlas_session = extract_session_id(atlas_raw)
        atlas_tool_calls = session_tool_count("atlas", atlas_session, root)
        validate(atlas, intake_schema, "Resumed Atlas intake")
    else:
        atlas_payload = {**governed, "card": card, "intake": intake}
        atlas, atlas_raw, atlas_session = run_profile("atlas", "medium", stage_prompt("atlas", atlas_payload, intake_schema), root)
        atlas_tool_calls = session_tool_count("atlas", atlas_session, root)
        validate(atlas, intake_schema, "Atlas intake")
        write_json(atlas_intake_path, atlas)
        atlas_raw_path.parent.mkdir(parents=True, exist_ok=True)
        atlas_raw_path.write_text(atlas_raw, encoding="utf-8")

    aria_payload = {**governed, "card": card, "normalized_intake": atlas}
    blueprint, aria_raw, aria_session = run_profile("aria", "high", stage_prompt("aria", aria_payload, blueprint_schema), root)
    aria_tool_calls = session_tool_count("aria", aria_session, root)
    validate(blueprint, blueprint_schema, "Aria blueprint")
    blueprint_path = run_dir / "aria" / "x_agent_blueprint.v0.1.json"
    write_json(blueprint_path, blueprint)
    (run_dir / "aria" / "raw-response.txt").write_text(aria_raw, encoding="utf-8")
    blueprint_hash = sha256_file(blueprint_path)

    vera_payload = {**governed, "card": card, "normalized_intake": atlas, "blueprint": blueprint, "blueprint_hash": blueprint_hash}
    evaluation, vera_raw, vera_session = run_profile("vera", "high", stage_prompt("vera", vera_payload, evaluation_schema), root)
    vera_tool_calls = session_tool_count("vera", vera_session, root)
    validate(evaluation, evaluation_schema, "Vera evaluation")
    if evaluation["evaluated_blueprint_hash"] != blueprint_hash:
        raise ValueError("Vera evaluation hash does not match the frozen blueprint bytes")
    evaluation_path = run_dir / "vera" / "evaluation.v0.1.json"
    write_json(evaluation_path, evaluation)
    (run_dir / "vera" / "raw-response.txt").write_text(vera_raw, encoding="utf-8")

    record = {
        "schema_version": "0.1",
        "run_id": run_id,
        "governed_run_marker": "X_FACTORY_GOVERNED_RUN_V0_1",
        "execution_mode": EXECUTION_MODE,
        "disclosure_manifest_sha256": manifest_hash,
        "card_sha256": card_hash,
        "approval_sha256": approval_hash,
        "intake_sha256": intake_hash,
        "provider": PROVIDER,
        "model": MODEL,
        "profiles": list(PROFILES),
        "tool_policy": TOOL_POLICY,
        "runtime_preflight": runtime_preflight,
        "sessions": {
            "atlas": {"session_id": atlas_session, "virgin_session": True, "tool_call_count": atlas_tool_calls},
            "aria": {"session_id": aria_session, "virgin_session": True, "tool_call_count": aria_tool_calls},
            "vera": {"session_id": vera_session, "virgin_session": True, "tool_call_count": vera_tool_calls},
        },
        "artifacts": {
            "atlas_intake_sha256": sha256_file(run_dir / "atlas" / "intake.v0.1.json"),
            "aria_blueprint_sha256": blueprint_hash,
            "vera_evaluation_sha256": sha256_file(evaluation_path),
            "vera_verdict": evaluation["verdict"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "authority": {"build_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    validate(record, run_schema, "contained run record")
    write_json(run_dir / "contained_run_record.v0.1.json", record)
    print(json.dumps({"status": "COMPLETE", "run_dir": str(run_dir), "verdict": evaluation["verdict"], "record": record}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
