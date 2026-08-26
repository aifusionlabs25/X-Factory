#!/usr/bin/env python3
"""Prepare or execute a three-profile Hermes review of one local candidate."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE = ROOT / "runs" / "interactive"
REVIEWS = ROOT / "reviews"
SCHEMA = ROOT / "contracts" / "hermes_semantic_stage_review.v0.1.schema.json"
BRIDGE = ROOT / "scripts" / "interactive_hermes_stage_bridge_v0_1.py"
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else canonical(value)
    with path.open("xb") as handle:
        handle.write(data)


def auth_metadata() -> dict[str, Any]:
    auth = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes/auth.json")
    if not auth.is_file():
        return {"path": str(auth), "exists": False, "sha256": None, "size": None, "mtime_ns": None}
    stat = auth.stat()
    return {"path": str(auth), "exists": True, "sha256": digest(auth.read_bytes()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def stage_payload(stage: str, artifacts: dict[str, Any], predecessor: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "schema_version": "0.1",
        "stage": stage,
        "authority": "REVIEW_ONLY_NO_BUILD_INSTALL_DEPLOYMENT_OR_PRODUCTION_AUTHORITY",
        "owner_brief": artifacts["brief"],
        "candidate_blueprint": artifacts["blueprint"],
    }
    if stage != "ATLAS_INTENT_REVIEW":
        base["x_link_candidate"] = artifacts["x_link"]
    if predecessor is not None:
        base["validated_predecessor_review"] = predecessor
    return base


def prompt_for(stage: str, payload: dict[str, Any], schema: dict[str, Any]) -> str:
    role = {
        "ATLAS_INTENT_REVIEW": "Atlas, Factory Foreman",
        "ARIA_ARCHITECTURE_REVIEW": "Aria, X-Agent Architect",
        "VERA_SEMANTIC_CERTIFICATION": "Vera, Independent Inspector",
    }[stage]
    return (
        f"You are {role}. Perform only the bounded semantic review in PAYLOAD. "
        "Do not use tools, external knowledge, memory, or unstated assumptions. "
        "Return exactly one JSON object satisfying OUTPUT_SCHEMA. Use PASS only when the candidate is usable at this review gate; "
        "otherwise use REVISION_REQUIRED or OWNER_DECISION_REQUIRED and state precise findings.\n"
        f"PAYLOAD\n{json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
        f"OUTPUT_SCHEMA\n{json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
    )


def execute_stage(review_root: Path, sequence: int, profile: str, stage: str, artifacts: dict[str, Any], predecessor: dict[str, Any] | None, schema: dict[str, Any]) -> dict[str, Any]:
    payload = stage_payload(stage, artifacts, predecessor)
    prompt = prompt_for(stage, payload, schema)
    prompt_path = review_root / f"transaction-{sequence:02d}.prompt.txt"
    evidence_path = review_root / f"transaction-{sequence:02d}.evidence.json"
    write_new(prompt_path, prompt.encode("utf-8"))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    process = subprocess.run([
        sys.executable, "-B", str(BRIDGE), "--profile", profile,
        "--review-root", str(review_root), "--prompt-file", str(prompt_path),
        "--evidence-file", str(evidence_path), "--prompt-sha256", digest(prompt.encode("utf-8")),
        "--payload-sha256", digest(canonical(payload)),
    ], cwd=review_root, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=300, check=False)
    if process.stdout or process.stderr:
        raise PermissionError("Unexpected bridge output escaped the evidence channel")
    evidence = load(evidence_path)
    if process.returncode != 0 or evidence["exit_code"] != 0:
        raise RuntimeError(f"{stage} transport or extraction failed; no retry permitted")
    if evidence["physical_requests"] != 1 or evidence["tool_attempts"] or evidence["oauth_refresh_attempts"] or evidence["auth_write_attempts"]:
        raise PermissionError(f"{stage} violated its one-call, zero-tool, read-only-auth policy")
    response = json.loads(base64.b64decode(evidence["response_base64"], validate=True).decode("utf-8"))
    Draft202012Validator(schema).validate(response)
    if response["stage"] != stage:
        raise PermissionError("Review response stage mismatch")
    write_new(review_root / f"transaction-{sequence:02d}.review.json", response)
    return response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not MISSION_ID.fullmatch(args.mission_id):
        raise SystemExit("Invalid mission ID")
    mission = INTERACTIVE / args.mission_id
    record = load(mission / "mission-record.json")
    artifacts = {
        "brief": load(mission / record["artifacts"]["owner_brief"]),
        "blueprint": load(mission / record["artifacts"]["blueprint"]),
        "x_link": load(mission / record["artifacts"]["x_link_package"]),
    }
    schema = load(SCHEMA)
    plan = {
        "schema_version": "0.1",
        "mission_id": args.mission_id,
        "status": "READY_FOR_CONTAINED_REVIEW",
        "provider": "openai-codex",
        "model": "gpt-5.6-luna",
        "reasoning": "low",
        "stages": ["ATLAS_INTENT_REVIEW", "ARIA_ARCHITECTURE_REVIEW", "VERA_SEMANTIC_CERTIFICATION"],
        "maximum_calls": 3,
        "retries": 0,
        "tools": False,
        "authentication_mutation": False,
        "mission_mutation": False,
        "deployment": False,
        "production": False,
        "input_hashes": {name: digest(canonical(value)) for name, value in artifacts.items()},
    }
    if args.prepare_only:
        print(json.dumps(plan, indent=2))
        return 0
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required")
    review_id = datetime.now(timezone.utc).strftime("review-%Y%m%d-%H%M%S")
    review_root = REVIEWS / args.mission_id / review_id
    review_root.mkdir(parents=True, exist_ok=False)
    write_new(review_root / "review-plan.json", plan)
    before_auth = auth_metadata()
    try:
        atlas = execute_stage(review_root, 1, "atlas", "ATLAS_INTENT_REVIEW", artifacts, None, schema)
        aria = execute_stage(review_root, 2, "aria", "ARIA_ARCHITECTURE_REVIEW", artifacts, atlas, schema)
        vera = execute_stage(review_root, 3, "vera", "VERA_SEMANTIC_CERTIFICATION", artifacts, aria, schema)
        after_auth = auth_metadata()
        if before_auth != after_auth:
            raise PermissionError("Shared Hermes authentication changed during review")
        summary = {
            "schema_version": "0.1",
            "mission_id": args.mission_id,
            "review_id": review_id,
            "status": "HERMES_SEMANTIC_REVIEW_PASS" if all(item["verdict"] == "PASS" for item in (atlas, aria, vera)) else "HERMES_SEMANTIC_REVIEW_NEEDS_REVISION",
            "calls": 3,
            "retries": 0,
            "tool_attempts": 0,
            "auth_unchanged": True,
            "verdicts": {"atlas": atlas["verdict"], "aria": aria["verdict"], "vera": vera["verdict"]},
            "deployment_authorized": False,
            "production_approved": False,
        }
        write_new(review_root / "semantic-review-summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as error:
        failure = {"schema_version": "0.1", "mission_id": args.mission_id, "review_id": review_id, "status": "FAILED_TERMINAL_NO_RETRY", "error": str(error), "auth_before": before_auth, "auth_after": auth_metadata()}
        write_new(review_root / "terminal-failure.json", failure)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
