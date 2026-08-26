#!/usr/bin/env python3
"""Prepare or execute one Phase 3.2 approval-bound Mason runtime proof.

This revision treats shared background Hermes activity as diagnostic evidence,
while making the three authentication files hard, frozen pre/post gates.  It
also records the governed subprocess tree without claiming unavailable global
kernel file-write attribution.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import phase3_1_mason_runtime_proof as base


PROFILE = "mason"
PROVIDER = "openai-codex"
MODEL = "gpt-5.6-luna"
RUN_ID = "contained-mason-runtime-proof-002"
GOVERNED_MARKER = "X_FACTORY_GOVERNED_MASON_RUNTIME_PROOF_V0_2"
SCOPE = "ONE_CONTAINED_MASON_ZERO_TOOL_RUNTIME_CANARY_NO_FACTORY_MISSION"
TOOL_POLICY = "ZERO_TOOLS_NO_MCP_NO_MEMORY_NO_DELEGATION"
PHASE3_1_INVALID_RECORD_SHA = "sha256:0e76a090f4f48b95344fc9ead3516f8f3919404ff6ec83d99cd1b980cc0d9382"
INSTALL_MANIFEST_SHA = base.INSTALL_MANIFEST_SHA
INSTALL_RECORD_SHA = base.INSTALL_RECORD_SHA
CONFIG_SHA = base.CONFIG_SHA
SOUL_SHA = base.SOUL_SHA
DISTRIBUTION_SHA = "sha256:ea6b2df2debfd0c10f00885d010e3cc88c5c35367bfab77c72458d5bd29ed0e4"
EXPECTED_RESPONSE = base.EXPECTED_RESPONSE


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


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


def profile_file_state(profile: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(profile).as_posix(): file_state(path)
        for path in sorted(profile.rglob("*"))
        if path.is_file()
    }


def changed_paths(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def verify_installed_state(factory_root: Path, profile_root: Path) -> dict[str, str]:
    hashes = base.verify_profile(factory_root, profile_root)
    distribution = profile_root / PROFILE / "distribution.yaml"
    if sha256_file(distribution) != DISTRIBUTION_SHA:
        raise PermissionError("Mason distribution differs from the installed approved profile")
    hashes["distribution"] = DISTRIBUTION_SHA
    return hashes


def auth_paths(profile_root: Path) -> dict[str, Path]:
    return {
        "shared_hermes_auth_json": profile_root.parent / "auth.json",
        "shared_hermes_auth_lock": profile_root.parent / "auth.lock",
        "codex_cli_auth_json": Path.home() / ".codex" / "auth.json",
    }


def auth_state(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    return {name: file_state(path) for name, path in paths.items()}


def process_snapshot() -> dict[int, dict[str, Any]]:
    if os.name != "nt":
        return {}
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        return {}
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found: dict[int, dict[str, Any]] = {}
    try:
        ok = kernel32.Process32FirstW(handle, ctypes.byref(entry))
        while ok:
            found[int(entry.th32ProcessID)] = {
                "pid": int(entry.th32ProcessID),
                "parent_pid": int(entry.th32ParentProcessID),
                "image": entry.szExeFile,
            }
            ok = kernel32.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(handle)
    return found


def descendants(snapshot: dict[int, dict[str, Any]], root_pid: int) -> dict[int, dict[str, Any]]:
    selected = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, item in snapshot.items():
            if item["parent_pid"] in selected and pid not in selected:
                selected.add(pid)
                changed = True
    return {pid: snapshot[pid] for pid in selected if pid in snapshot}


def run_with_process_tree(command: list[str], cwd: Path, timeout: int) -> tuple[subprocess.CompletedProcess[str], list[dict[str, Any]]]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    seen: dict[int, dict[str, Any]] = {
        process.pid: {"pid": process.pid, "parent_pid": os.getpid(), "image": Path(command[0]).name}
    }
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.20):
            seen.update(descendants(process_snapshot(), process.pid))

    sampler = threading.Thread(target=sample, name="phase3-2-process-tree-sampler", daemon=True)
    sampler.start()
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise RuntimeError(f"Governed process timed out after {timeout} seconds")
    finally:
        stop.set()
        sampler.join(timeout=2)
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    return completed, sorted(seen.values(), key=lambda item: item["pid"])


def make_payload(profile_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "0.2",
        "governed_run_marker": GOVERNED_MARKER,
        "purpose": "Prove installed Mason can answer one fixed canary with zero runtime tools under frozen no-refresh authentication gates",
        "revision_context": {
            "phase3_1_invalid_record_sha256": PHASE3_1_INVALID_RECORD_SHA,
            "phase3_1_remains_invalid": True,
            "correction": "Ambient shared-service changes are diagnostic; authentication changes remain hard failures",
        },
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
        "X-AGENT FACTORY CONTAINED MASON RUNTIME PROOF PHASE 3.2. Use only the inline approved JSON. "
        "You have zero tools. Do not request or claim access to files, repositories, credentials, memory, providers beyond this response, networks, MCP, plugins, or external systems. "
        "This is a runtime canary, not a Factory mission. Return exactly PAYLOAD.expected_response as one JSON object and nothing else.\n"
        "PAYLOAD=" + canonical(payload)
    )


def approval_path(root: Path, manifest_hash: str) -> Path:
    suffix = manifest_hash.removeprefix("sha256:")[:12]
    return root / "approvals" / "approved" / f"mason.runtime-proof-phase3-2.{suffix}.approval.json"


def verify_approval(value: dict[str, Any], manifest_hash: str, prompt_hash: str, payload_hash: str) -> None:
    expected = {
        "approval_type": "PHASE3_2_MASON_RUNTIME_PROOF",
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
    required_true = ("one_contained_runtime_canary", "mason_profile_runtime_writes")
    required_false = (
        "oauth_refresh", "shared_auth_mutation", "factory_mission", "build", "install",
        "deployment", "production", "tools_or_mcp",
    )
    for key in required_true:
        if authority.get(key) is not True:
            raise PermissionError(f"Required authority is absent: {key}")
    for key in required_false:
        if authority.get(key) is not False:
            raise PermissionError(f"Forbidden authority must remain false: {key}")


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
    profile_root = args.runtime_profile_root.resolve()
    profile_hashes = verify_installed_state(root, profile_root)
    frozen_auth = auth_state(auth_paths(profile_root))
    if not all(state.get("exists") for state in frozen_auth.values()):
        raise FileNotFoundError("All three frozen authentication baseline files must exist")
    payload = make_payload(profile_hashes)
    pending = root / "approvals" / "pending"
    payload_path = pending / "mason.runtime-proof-phase3-2.payload.json"
    write_json(payload_path, payload)
    payload_hash = sha256_file(payload_path)
    prompt = make_prompt(payload)
    prompt_path = pending / "mason.runtime-proof-phase3-2.exact-prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    prompt_hash = sha256_file(prompt_path)
    manifest = {
        "schema_version": "0.2",
        "manifest_id": "DISCLOSURE-MASON-RUNTIME-PROOF-PHASE3-2-V1",
        "purpose": "Permit one contained Mason zero-tool runtime canary with frozen, no-refresh authentication",
        "payload_sha256": payload_hash,
        "exact_prompt_sha256": prompt_hash,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "provider": PROVIDER,
        "model": MODEL,
        "profile": PROFILE,
        "profile_hashes": profile_hashes,
        "frozen_authentication_baseline": frozen_auth,
        "scope": SCOPE,
        "tool_policy": TOOL_POLICY,
        "authentication": {
            "existing_codex_oauth_may_be_read_by_hermes": True,
            "credential_contents_in_prompt": False,
            "credential_contents_visible_to_mason": False,
            "oauth_refresh_authorized": False,
            "shared_hermes_auth_writes_authorized": False,
            "codex_cli_auth_store_is_read_only": True,
            "baseline_drift_before_transmission_blocks_without_provider_call": True,
            "any_post_call_auth_change_blocks_promotion_and_forbids_retry": True,
        },
        "authorized_side_effects": {
            "one_governed_inference_transaction": True,
            "ordinary_runtime_writes_only_within_mason_profile": True,
            "factory_runtime_run_record": True,
            "shared_auth_writes": False,
            "temporary_prompt_files": False,
        },
        "mutation_audit": {
            "process_tree_recorded": True,
            "kernel_file_io_attribution_available": False,
            "attribution_scope": "Governed process tree plus contract-bound Mason profile, shared Hermes, and Codex-auth surfaces",
            "mason_profile_changes_are_expected_runtime_diagnostics": True,
            "broad_shared_hermes_snapshot_is_diagnostic_only": True,
            "ambient_cron_kanban_gateway_changes_do_not_invalidate": True,
            "auth_surfaces_are_hard_pre_and_post_gates": True,
            "promotion_requires_unauthorized_proof_process_changes_empty": True,
            "unauthorized_change_semantics": "Any auth-surface change inside the governed proof window is disqualifying; kernel PID-to-file attribution is not claimed",
            "global_filesystem_non-mutation_is_not_claimed": True,
        },
        "revision_context": payload["revision_context"],
        "authority": payload["authority"],
    }
    manifest_path = pending / "mason.runtime-proof-phase3-2.disclosure-manifest.json"
    write_json(manifest_path, manifest)
    manifest_hash = sha256_file(manifest_path)
    required_approval = approval_path(root, manifest_hash)
    preview = {
        "schema_version": "0.2",
        "disclosure_manifest_sha256": manifest_hash,
        "payload_sha256": payload_hash,
        "exact_prompt_sha256": prompt_hash,
        "exact_disclosure_manifest": manifest,
        "exact_payload": payload,
        "exact_prompt": prompt,
        "approval_record_required": str(required_approval.relative_to(root)),
        "provider_transmission_performed": False,
    }
    preview_path = pending / "mason.runtime-proof-phase3-2.payload-preview.json"
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
        raise PermissionError(f"Exact Phase 3.2 approval is missing: {required_approval}")
    approval = json.loads(required_approval.read_text(encoding="utf-8"))
    verify_approval(approval, manifest_hash, prompt_hash, payload_hash)
    approval_hash = sha256_file(required_approval)
    run_dir = root / "runs" / "contained" / RUN_ID
    if run_dir.exists():
        raise FileExistsError(f"Mason runtime-proof run directory already exists: {run_dir}")

    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI is not available on PATH")
    current_auth = auth_state(auth_paths(profile_root))
    if current_auth != frozen_auth:
        raise PermissionError("RUNTIME_PROOF_BLOCKED_BASELINE_DRIFT: frozen authentication baseline changed; provider call not made")
    sandbox = root / "runtime-sandbox" / "mason-phase3-2"
    if sandbox.exists() and any(sandbox.iterdir()):
        raise PermissionError("Phase 3.2 runtime sandbox is not empty; provider call not made")
    sandbox.mkdir(parents=True, exist_ok=True)
    profile = profile_root / PROFILE
    shared_root = profile_root.parent
    shared_before = base.shared_hermes_state(shared_root)
    profile_before = profile_file_state(profile)
    command = [
        executable, "--profile", PROFILE, "chat", "-Q", "-v", "--reasoning", "low",
        "--max-turns", "2", "--source", "tool", "--in", str(sandbox), "-q", prompt,
    ]
    completed, chat_tree = run_with_process_tree(command, sandbox, 600)
    combined = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    immediate_auth_after = auth_state(auth_paths(profile_root))
    if immediate_auth_after != frozen_auth:
        unauthorized = [name for name in frozen_auth if frozen_auth[name] != immediate_auth_after[name]]
        raw_path = run_dir / "mason" / "raw-response.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(combined, encoding="utf-8", newline="\n")
        blocked_record = {
            "schema_version": "0.2",
            "run_id": RUN_ID,
            "governed_run_marker": GOVERNED_MARKER,
            "disclosure_manifest_sha256": manifest_hash,
            "payload_sha256": payload_hash,
            "exact_prompt_sha256": prompt_hash,
            "approval_sha256": approval_hash,
            "provider": PROVIDER,
            "model": MODEL,
            "profile": PROFILE,
            "mutation_audit": {
                "process_tree": {"chat": chat_tree},
                "kernel_file_io_attribution_available": False,
                "frozen_authentication_baseline": frozen_auth,
                "authentication_after_chat": immediate_auth_after,
                "authentication_unchanged": False,
                "unauthorized_proof_process_changes": unauthorized,
                "status": "FAIL",
            },
            "provider_return_code": completed.returncode,
            "retry_authorized": False,
            "lifecycle_status": "RUNTIME_PROOF_BLOCKED_AUTH_REFRESH_REQUIRED",
            "authority": payload["authority"],
        }
        write_json(run_dir / "contained_mason_runtime_record.v0.2.json", blocked_record)
        print(json.dumps({"status": "BLOCKED", "lifecycle_status": blocked_record["lifecycle_status"], "record": blocked_record}, indent=2))
        return 4
    if completed.returncode != 0:
        raise RuntimeError(f"Hermes Mason runtime proof failed with exit code {completed.returncode}: {combined[-2000:]}")
    runtime_checks = {
        "api_request_tools_zero": bool(re.search(r"API Request.*Tools:\s*0", combined)),
        "no_tools_selected": "No tools selected" in combined,
        "no_tools_loaded": "No tools loaded" in combined,
    }
    if not all(runtime_checks.values()):
        raise PermissionError(f"Mason runtime allow-none proof failed: {runtime_checks}")
    response = base.extract_last_json(completed.stdout)
    if response != EXPECTED_RESPONSE:
        raise PermissionError(f"Mason returned an unexpected canary response: {response}")
    session_id = base.extract_session_id(combined)
    export_command = [
        executable, "--profile", PROFILE, "sessions", "export", "-", "--format", "jsonl",
        "--session-id", session_id, "--max-tool-calls", "0", "--dry-run",
    ]
    exported, export_tree = run_with_process_tree(export_command, sandbox, 60)
    if exported.returncode != 0 or not exported.stdout.strip():
        raise PermissionError("Mason session did not satisfy max-tool-calls=0")
    tool_calls = int(json.loads(exported.stdout.splitlines()[0])["tool_call_count"])
    if tool_calls != 0:
        raise PermissionError(f"Mason session recorded {tool_calls} tool calls")

    auth_after = auth_state(auth_paths(profile_root))
    auth_unchanged = auth_after == frozen_auth
    shared_after = base.shared_hermes_state(shared_root)
    profile_after = profile_file_state(profile)
    shared_changes = changed_paths(shared_before, shared_after)
    profile_changes = changed_paths(profile_before, profile_after)
    unauthorized_proof_process_changes = [] if auth_unchanged else [
        name for name in frozen_auth if frozen_auth[name] != auth_after[name]
    ]

    response_path = run_dir / "mason" / "response.json"
    raw_path = run_dir / "mason" / "raw-response.txt"
    write_json(response_path, response)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(combined, encoding="utf-8", newline="\n")
    lifecycle_status = "MASON_RUNTIME_READY_ZERO_TOOLS" if auth_unchanged else "RUNTIME_PROOF_BLOCKED_AUTH_REFRESH_REQUIRED"
    record = {
        "schema_version": "0.2",
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
        "mutation_audit": {
            "process_tree": {"chat": chat_tree, "session_export": export_tree},
            "kernel_file_io_attribution_available": False,
            "attribution_scope": manifest["mutation_audit"]["attribution_scope"],
            "frozen_authentication_baseline": frozen_auth,
            "authentication_after": auth_after,
            "authentication_unchanged": auth_unchanged,
            "unauthorized_proof_process_changes": unauthorized_proof_process_changes,
            "shared_hermes_changed_paths_diagnostic": shared_changes,
            "mason_profile_changed_paths_expected_runtime": profile_changes,
            "global_filesystem_non_mutation_claimed": False,
            "status": "PASS" if auth_unchanged else "FAIL",
        },
        "session": {"session_id": session_id, "virgin_session": True, "tool_call_count": tool_calls},
        "artifacts": {"response_sha256": sha256_file(response_path), "completed_at": datetime.now(timezone.utc).isoformat()},
        "retry_authorized": False,
        "lifecycle_status": lifecycle_status,
        "authority": payload["authority"],
    }
    write_json(run_dir / "contained_mason_runtime_record.v0.2.json", record)
    print(json.dumps({"status": "COMPLETE" if auth_unchanged else "BLOCKED", "lifecycle_status": lifecycle_status, "record": record}, indent=2))
    return 0 if auth_unchanged else 4


if __name__ == "__main__":
    raise SystemExit(main())
