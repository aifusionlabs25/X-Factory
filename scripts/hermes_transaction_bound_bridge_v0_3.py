#!/usr/bin/env python3
"""One-stage Hermes bridge with strict machine-response extraction."""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.phase4_transport_guard_v0_4 import install_into_hermes


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".next")
    if path.exists() or temporary.exists():
        raise PermissionError("Execution evidence path must be new")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def extract_single_json_suffix(raw: bytes) -> tuple[bytes, int]:
    """Return the unique JSON object whose suffix contains only whitespace."""
    text = raw.decode("utf-8")
    candidates: list[tuple[int, int]] = []
    decoder = json.JSONDecoder()
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, end = decoder.raw_decode(text, offset)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and not text[end:].strip():
            candidates.append((offset, end))
    if len(candidates) != 1:
        raise PermissionError(f"Expected one terminal JSON object; found {len(candidates)}")
    offset, end = candidates[0]
    if "{" in text[:offset] or "}" in text[:offset]:
        raise PermissionError("Terminal presentation contained an earlier JSON-shaped fragment")
    return text[offset:end].encode("utf-8"), offset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("atlas", "aria", "mason", "vera"), required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--transaction", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--stage", choices=("ATLAS_TRIAGE", "ARIA_BLUEPRINT", "VERA_SPEC_REVIEW", "MASON_PLAN", "VERA_BUILD_REVIEW"), required=True)
    parser.add_argument("--mission-root", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--prompt-sha256", required=True)
    parser.add_argument("--payload-sha256", required=True)
    parser.add_argument("--bridge-sha256", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    mission_root = args.mission_root.resolve(strict=True)
    expected_root = (ROOT / "runs" / "contained" / args.mission_id).resolve()
    if mission_root != expected_root:
        raise PermissionError("Mission root is not the exact contained mission directory")
    control_root = (mission_root / "control").resolve(strict=True)
    prompt_file = args.prompt_file.resolve(strict=True)
    evidence_file = args.evidence_file.resolve(strict=False)
    prompt_file.relative_to(control_root)
    evidence_file.relative_to(control_root)
    if prompt_file.name != f"transaction-{args.transaction:02d}.prompt.txt":
        raise PermissionError("Prompt filename does not match transaction")
    if evidence_file.name != f"transaction-{args.transaction:02d}.bridge-evidence.json":
        raise PermissionError("Evidence filename does not match transaction")

    bridge_bytes = Path(__file__).resolve().read_bytes()
    if digest(bridge_bytes) != args.bridge_sha256:
        raise PermissionError("Bridge byte hash mismatch")
    prompt_bytes = prompt_file.read_bytes()
    if digest(prompt_bytes) != args.prompt_sha256:
        raise PermissionError("Prompt byte hash mismatch")

    guard = install_into_hermes()
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = 0
    error_type = None
    error_message = None
    sys.argv = [
        "hermes", "--profile", args.profile, "chat", "-Q",
        "--provider", "openai-codex", "--model", "gpt-5.6-luna",
        "--reasoning", "low", "--max-turns", "1", "--source", "tool",
        "--in", str(mission_root), "-q", prompt_bytes.decode("utf-8"),
    ]
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_module("hermes_cli.main", run_name="__main__")
    except SystemExit as error:
        exit_code = int(error.code or 0) if isinstance(error.code, (int, type(None))) else 1
    except BaseException as error:
        exit_code = 1
        error_type = type(error).__name__
        error_message = str(error)

    stdout_bytes = stdout.getvalue().encode("utf-8")
    stderr_bytes = stderr.getvalue().encode("utf-8")
    response_bytes = b""
    response_offset = None
    extraction_error = None
    if exit_code == 0:
        try:
            response_bytes, response_offset = extract_single_json_suffix(stdout_bytes)
        except BaseException as error:
            exit_code = 1
            extraction_error = str(error)
    record = {
        "schema_version": "0.3",
        "mission_id": args.mission_id,
        "transaction": args.transaction,
        "stage": args.stage,
        "profile": args.profile,
        "prompt_sha256": args.prompt_sha256,
        "payload_sha256": args.payload_sha256,
        "bridge_sha256": args.bridge_sha256,
        "exit_code": exit_code,
        "physical_requests": guard.physical_requests,
        "tool_attempts": guard.tool_attempts,
        "oauth_refresh_attempts": guard.oauth_refresh_attempts,
        "auth_write_attempts": guard.auth_write_attempts,
        "codex_cli_import_attempts": guard.codex_cli_import_attempts,
        "stdout_sha256": digest(stdout_bytes),
        "stderr_sha256": digest(stderr_bytes),
        "stdout_base64": base64.b64encode(stdout_bytes).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr_bytes).decode("ascii"),
        "response_sha256": digest(response_bytes),
        "response_base64": base64.b64encode(response_bytes).decode("ascii"),
        "response_offset": response_offset,
        "response_extraction": "UNIQUE_TERMINAL_JSON_OBJECT",
        "extraction_error": extraction_error,
        "error_type": error_type,
        "error_message": error_message,
    }
    atomic_json(evidence_file, record)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
