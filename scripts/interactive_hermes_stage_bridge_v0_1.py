#!/usr/bin/env python3
"""Single-call, zero-tool Hermes bridge for an interactive Factory review."""

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


def extract_single_json_suffix(raw: bytes) -> bytes:
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
    return text[offset:end].encode("utf-8")


def atomic_json(path: Path, value: dict) -> None:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    temporary = path.with_name(path.name + ".next")
    if path.exists() or temporary.exists():
        raise PermissionError("Evidence output must be new")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("atlas", "aria", "vera"), required=True)
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--prompt-sha256", required=True)
    parser.add_argument("--payload-sha256", required=True)
    args = parser.parse_args()

    review_root = args.review_root.resolve(strict=True)
    expected_parent = (ROOT / "reviews").resolve()
    review_root.relative_to(expected_parent)
    prompt_file = args.prompt_file.resolve(strict=True)
    evidence_file = args.evidence_file.resolve(strict=False)
    prompt_file.relative_to(review_root)
    evidence_file.relative_to(review_root)
    prompt_bytes = prompt_file.read_bytes()
    if digest(prompt_bytes) != args.prompt_sha256:
        raise PermissionError("Prompt hash mismatch")
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required")

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
        "--in", str(review_root), "-q", prompt_bytes.decode("utf-8"),
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
    extraction_error = None
    if exit_code == 0:
        try:
            response_bytes = extract_single_json_suffix(stdout_bytes)
        except BaseException as error:
            exit_code = 1
            extraction_error = str(error)
    evidence = {
        "schema_version": "0.1",
        "profile": args.profile,
        "prompt_sha256": args.prompt_sha256,
        "payload_sha256": args.payload_sha256,
        "exit_code": exit_code,
        "physical_requests": guard.physical_requests,
        "tool_attempts": guard.tool_attempts,
        "oauth_refresh_attempts": guard.oauth_refresh_attempts,
        "auth_write_attempts": guard.auth_write_attempts,
        "codex_cli_import_attempts": guard.codex_cli_import_attempts,
        "stdout_sha256": digest(stdout_bytes),
        "stderr_sha256": digest(stderr_bytes),
        "response_sha256": digest(response_bytes),
        "stdout_base64": base64.b64encode(stdout_bytes).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr_bytes).decode("ascii"),
        "response_base64": base64.b64encode(response_bytes).decode("ascii"),
        "extraction_error": extraction_error,
        "error_type": error_type,
        "error_message": error_message,
    }
    atomic_json(evidence_file, evidence)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
