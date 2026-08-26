#!/usr/bin/env python3
"""Prepare or execute one approval-bound, zero-tool Mason runtime proof."""

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


PROFILE = "mason"
PROVIDER = "openai-codex"
MODEL = "gpt-5.6-luna"
RUN_ID = "contained-mason-runtime-proof-001"
GOVERNED_MARKER = "X_FACTORY_GOVERNED_MASON_RUNTIME_PROOF_V0_1"
SCOPE = "ONE_CONTAINED_MASON_ZERO_TOOL_RUNTIME_CANARY_NO_FACTORY_MISSION"
TOOL_POLICY = "ZERO_TOOLS_NO_MCP_NO_MEMORY_NO_DELEGATION"
INSTALL_MANIFEST_SHA = "sha256:80e912e2a80db9018d80d24d1cc034130224c52da7643d21bc52157b9f038bc4"
INSTALL_RECORD_SHA = "sha256:a47752f889f728146088bf746506ded99a54b1ea03f3bf4819edd20451ee9f6f"
CONFIG_SHA = "sha256:c58a1e0696442c0e588bc5e32628209dd74d6361db07dde2fcfbee898e6ab933"
SOUL_SHA = "sha256:7a91ff415ad19779509ed9065b7695c075da0c7f1dcbebb71372049c1a73c135"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SESSION_ID = re.compile(r"session_id:\s*([0-9]{8}_[0-9]{6}_[a-z0-9]+)")

DISABLED_TOOLSETS = {
    "a2a", "bfl", "browser", "clarify", "code_execution", "computer_use",
    "context_engine", "cronjob", "delegation", "desktop_ui", "discord",
    "discord_admin", "file", "homeassistant", "image_gen", "kanban", "memory",
    "project", "session_search", "skills", "spotify", "stt", "terminal", "todo",
    "tts", "video", "video_gen", "vision", "web", "x_search", "yuanbao",
}

EXPECTED_RESPONSE = {
    "authority": "RUNTIME_PROOF_ONLY_NO_FACTORY_MISSION_NO_BUILD_INSTALL_DEPLOYMENT_OR_PRODUCTION_AUTHORITY",
    "marker": "MASON_RUNTIME_READY",
    "role": "IMPLEMENTATION_STEWARD",
    "tool_policy": "ZERO_TOOLS",
}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "sha256": sha256_file(path),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def shared_hermes_state(shared_root: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    excluded_top = {"profiles", "hermes-agent"}
    for path in sorted(shared_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(shared_root)
        if relative.parts and relative.parts[0] in excluded_top:
            continue
        state[relative.as_posix()] = file_state(path)
    for required in ("auth.json", "auth.lock"):
        state.setdefault(required, file_state(shared_root / required))
    return state


def changed_paths(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def extract_last_json(text: str) -> dict[str, Any]:
    cleaned = ANSI.sub("", text)
    decoder = json.JSONDecoder()
    values: list[dict[str, Any]] = []
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    if not values:
        raise ValueError("Hermes response did not contain a JSON object")
    return values[-1]


def extract_session_id(text: str) -> str:
    matches = SESSION_ID.findall(ANSI.sub("", text))
    if not matches:
        raise ValueError("Hermes output did not include a session_id")
    return matches[-1]


def verify_profile(factory_root: Path, profile_root: Path) -> dict[str, str]:
    profile = profile_root / PROFILE
    paths = {
        "config": profile / "config.yaml",
        "soul": profile / "SOUL.md",
        "distribution": profile / "distribution.yaml",
    }
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Mason profile {label} is missing")
    if sha256_file(paths["config"]) != CONFIG_SHA:
        raise PermissionError("Mason config differs from the installed approved profile")
    if sha256_file(paths["soul"]) != SOUL_SHA:
        raise PermissionError("Mason SOUL differs from the installed approved profile")
    install_record = factory_root / "runs" / "installed" / "phase3-local-integration-controlled-build-004" / "install_record.v0.1.json"
    if sha256_file(install_record) != INSTALL_RECORD_SHA:
        raise PermissionError("Phase 3 install record differs from the approved installed state")
    config = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    disabled = set(config.get("agent", {}).get("disabled_toolsets", []))
    checks = (
        config.get("model", {}).get("provider") == PROVIDER,
        config.get("model", {}).get("default") == MODEL,
        config.get("platform_toolsets", {}).get("cli") == ["no_mcp"],
        DISABLED_TOOLSETS <= disabled,
        config.get("memory", {}).get("memory_enabled") is False,
        config.get("memory", {}).get("user_profile_enabled") is False,
        config.get("delegation", {}).get("orchestrator_enabled") is False,
        config.get("approvals", {}).get("cron_mode") == "deny",
    )
    if not all(checks):
        raise PermissionError("Mason is not the approved cognition-only Luna profile")
    return {label: sha256_file(path) for label, path in paths.items()}


def make_payload(profile_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "governed_run_marker": GOVERNED_MARKER,
        "purpose": "Prove that installed Mason can answer one fixed canary with zero runtime tools",
        "installed_state": {
            "phase3_install_manifest_sha256": INSTALL_MANIFEST_SHA,
            "phase3_install_record_sha256": INSTALL_RECORD_SHA,
            "profile_hashes": profile_hashes,
        },
        "runtime": {
            "profile": PROFILE,
            "provider": PROVIDER,
            "model": MODEL,
            "reasoning_effort": "low",
            "tool_policy": TOOL_POLICY,
            "virgin_session_required": True,
        },
        "instruction": "Return exactly the expected_response JSON object and nothing else. Do not call or request any tool. Do not perform, propose, or claim any Factory work.",
        "expected_response": EXPECTED_RESPONSE,
        "authority": {
            "runtime_canary_only": True,
            "factory_mission": False,
            "build": False,
            "install": False,
            "deployment": False,
            "production": False,
        },
    }


def make_prompt(payload: dict[str, Any]) -> str:
    return (
        "X-AGENT FACTORY CONTAINED MASON RUNTIME PROOF. Use only the inline approved JSON. "
        "You have zero tools. Do not request or claim access to files, repositories, credentials, memory, providers beyond this response, networks, MCP, plugins, or external systems. "
        "This is a runtime canary, not a Factory mission. Return exactly PAYLOAD.expected_response as one JSON object and nothing else.\n"
        "PAYLOAD=" + canonical(payload)
    )


def approval_path(root: Path, manifest_hash: str) -> Path:
    suffix = manifest_hash.removeprefix("sha256:")[:12]
    return root / "approvals" / "approved" / f"mason.runtime-proof-phase3-1.{suffix}.approval.json"


def verify_approval(value: dict[str, Any], manifest_hash: str, prompt_hash: str, payload_hash: str) -> None:
    expected = {
        "approval_type": "PHASE3_1_MASON_RUNTIME_PROOF",
        "approved": True,
        "disclosure_manifest_sha256": manifest_hash,
        "exact_prompt_sha256": prompt_hash,
        "payload_sha256": payload_hash,
        "provider": PROVIDER,
        "model": MODEL,
        "profile": PROFILE,
    }
    for key, required in expected.items():
        if value.get(key) != required:
            raise PermissionError(f"Approval field mismatch: {key}")
    authority = value.get("authority", {})
    if authority.get("one_contained_runtime_canary") is not True:
        raise PermissionError("Runtime-canary authority is absent")
    if authority.get("shared_auth_mutation_authorized") is not True:
        raise PermissionError("Shared-auth rotation authority is absent")
    for forbidden in ("factory_mission", "build", "install", "deployment", "production", "tools_or_mcp"):
        if authority.get(forbidden) is not False:
            raise PermissionError(f"Forbidden authority must remain false: {forbidden}")


def session_tool_count(executable: str, session_id: str, root: Path) -> int:
    completed = subprocess.run(
        [executable, "--profile", PROFILE, "sessions", "export", "-", "--format", "jsonl", "--session-id", session_id, "--max-tool-calls", "0", "--dry-run"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise PermissionError("Mason session did not satisfy max-tool-calls=0")
    count = int(json.loads(completed.stdout.splitlines()[0])["tool_call_count"])
    if count != 0:
        raise PermissionError(f"Mason session recorded {count} tool calls")
    return count


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
    profile_hashes = verify_profile(root, args.runtime_profile_root.resolve())
    payload = make_payload(profile_hashes)
    pending = root / "approvals" / "pending"
    payload_path = pending / "mason.runtime-proof-phase3-1.payload.json"
    write_json(payload_path, payload)
    payload_hash = sha256_file(payload_path)
    prompt = make_prompt(payload)
    prompt_path = pending / "mason.runtime-proof-phase3-1.exact-prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    prompt_hash = sha256_file(prompt_path)
    manifest = {
        "schema_version": "0.1",
        "manifest_id": "DISCLOSURE-MASON-RUNTIME-PROOF-PHASE3-1-V1",
        "purpose": "Permit one contained Mason zero-tool runtime canary and no Factory mission",
        "payload_sha256": payload_hash,
        "exact_prompt_sha256": prompt_hash,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "provider": PROVIDER,
        "model": MODEL,
        "profile": PROFILE,
        "profile_hashes": profile_hashes,
        "scope": SCOPE,
        "tool_policy": TOOL_POLICY,
        "authentication": {
            "existing_codex_oauth_may_be_read_by_hermes": True,
            "credential_contents_in_prompt": False,
            "credential_contents_visible_to_mason": False,
            "mason_profile_local_auth_state_may_be_written": True,
            "shared_hermes_auth_state_may_rotate_if_required": True,
            "codex_cli_auth_store_is_read_only_to_this_proof": True,
        },
        "authorized_side_effects": {
            "one_governed_inference_transaction_including_oauth_refresh_if_required": True,
            "writes_only_within_mason_profile": True,
            "shared_hermes_auth_json_and_auth_lock_are_the_only_write_exception": True,
            "temporary_prompt_files": False,
            "factory_runtime_run_record": True,
        },
        "shared_state_audit": {
            "shared_auth_mutation_authorized": True,
            "only_allowed_shared_write_paths": ["auth.json", "auth.lock"],
            "capture_pre_and_post_hash_existence_size_and_mtime": True,
            "codex_cli_auth_must_remain_byte_and_metadata_identical": True,
            "any_other_shared_hermes_change_invalidates_proof": True,
            "record_whether_oauth_rotation_occurred": True,
        },
        "authority": payload["authority"],
    }
    manifest_path = pending / "mason.runtime-proof-phase3-1.disclosure-manifest.json"
    write_json(manifest_path, manifest)
    manifest_hash = sha256_file(manifest_path)
    required_approval = approval_path(root, manifest_hash)
    preview = {
        "schema_version": "0.1",
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "exact_prompt_sha256": prompt_hash,
        "exact_disclosure_manifest": manifest,
        "exact_payload": payload,
        "exact_prompt": prompt,
        "approval_record_required": str(required_approval.relative_to(root)),
        "provider_transmission_performed": False,
    }
    preview_path = pending / "mason.runtime-proof-phase3-1.payload-preview.json"
    write_json(preview_path, preview)

    if args.prepare:
        print(json.dumps({
            "status": "APPROVAL_REQUIRED",
            "disclosure_manifest_sha256": manifest_hash,
            "payload_sha256": payload_hash,
            "exact_prompt_sha256": prompt_hash,
            "payload_preview": str(preview_path),
            "approval_record_required": str(required_approval),
            "provider_transmission_performed": False,
        }, indent=2))
        return 2

    if not required_approval.is_file():
        raise PermissionError(f"Exact Phase 3.1 approval is missing: {required_approval}")
    approval = load_json(required_approval)
    verify_approval(approval, manifest_hash, prompt_hash, payload_hash)
    approval_hash = sha256_file(required_approval)
    run_dir = root / "runs" / "contained" / RUN_ID
    if run_dir.exists():
        raise FileExistsError(f"Mason runtime-proof run directory already exists: {run_dir}")

    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    sandbox = root / "runtime-sandbox" / "mason-phase3-1"
    sandbox.mkdir(parents=True, exist_ok=True)
    shared_root = args.runtime_profile_root.resolve().parent
    codex_auth = Path.home() / ".codex" / "auth.json"
    shared_before = shared_hermes_state(shared_root)
    codex_auth_before = file_state(codex_auth)
    command = [
        executable, "--profile", PROFILE, "chat", "-Q", "-v", "--reasoning", "low",
        "--max-turns", "2", "--source", "tool", "--in", str(sandbox), "-q", prompt,
    ]
    completed = subprocess.run(
        command, cwd=sandbox, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False,
    )
    combined = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    if completed.returncode != 0:
        raise RuntimeError(f"Hermes Mason runtime proof failed with exit code {completed.returncode}: {combined[-2000:]}")
    runtime_checks = {
        "api_request_tools_zero": bool(re.search(r"API Request.*Tools:\s*0", combined)),
        "no_tools_selected": "No tools selected" in combined,
        "no_tools_loaded": "No tools loaded" in combined,
    }
    if not all(runtime_checks.values()):
        raise PermissionError(f"Mason runtime allow-none proof failed: {runtime_checks}")
    response = extract_last_json(completed.stdout)
    if response != EXPECTED_RESPONSE:
        raise PermissionError(f"Mason returned an unexpected canary response: {response}")
    session_id = extract_session_id(combined)
    tool_calls = session_tool_count(executable, session_id, sandbox)
    shared_after = shared_hermes_state(shared_root)
    codex_auth_after = file_state(codex_auth)
    shared_changes = changed_paths(shared_before, shared_after)
    allowed_shared_changes = {"auth.json", "auth.lock"}
    disallowed_shared_changes = sorted(set(shared_changes) - allowed_shared_changes)
    codex_auth_unchanged = codex_auth_before == codex_auth_after

    response_path = run_dir / "mason" / "response.json"
    raw_path = run_dir / "mason" / "raw-response.txt"
    write_json(response_path, response)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(combined, encoding="utf-8", newline="\n")
    shared_state_valid = not disallowed_shared_changes and codex_auth_unchanged
    lifecycle_status = "MASON_RUNTIME_READY_ZERO_TOOLS" if shared_state_valid else "RUNTIME_PROOF_INVALID_SHARED_STATE_MUTATION"
    record = {
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "governed_run_marker": GOVERNED_MARKER,
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "exact_prompt_sha256": prompt_hash,
        "approval_sha256": approval_hash,
        "provider": PROVIDER,
        "model": MODEL,
        "profile": PROFILE,
        "runtime_checks": runtime_checks,
        "shared_state_audit": {
            "shared_auth_mutation_authorized": True,
            "allowed_shared_paths": ["auth.json", "auth.lock"],
            "shared_auth_before": {key: shared_before[key] for key in ("auth.json", "auth.lock")},
            "shared_auth_after": {key: shared_after[key] for key in ("auth.json", "auth.lock")},
            "shared_changed_paths": shared_changes,
            "shared_auth_mutation_occurred": bool(set(shared_changes) & allowed_shared_changes),
            "disallowed_shared_changes": disallowed_shared_changes,
            "codex_cli_auth_before": codex_auth_before,
            "codex_cli_auth_after": codex_auth_after,
            "codex_cli_auth_unchanged": codex_auth_unchanged,
            "status": "PASS" if shared_state_valid else "FAIL",
        },
        "session": {"session_id": session_id, "virgin_session": True, "tool_call_count": tool_calls},
        "artifacts": {"response_sha256": sha256_file(response_path), "completed_at": datetime.now(timezone.utc).isoformat()},
        "lifecycle_status": lifecycle_status,
        "authority": payload["authority"],
    }
    write_json(run_dir / "contained_mason_runtime_record.v0.1.json", record)
    print(json.dumps({"status": "COMPLETE" if shared_state_valid else "INVALID", "lifecycle_status": record["lifecycle_status"], "record": record}, indent=2))
    return 0 if shared_state_valid else 3


if __name__ == "__main__":
    raise SystemExit(main())
