#!/usr/bin/env python3
"""Build a provider-free recovery draft from accepted Aria output and Vera defects."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator
from x_factory.mission_control_preview_generator_v0_1 import generate as generate_preview

SOURCE_MISSION = ROOT / "runs/contained/phase4-governed-draft-001"
RECOVERY_ID = "phase4-governed-draft-001-local-recovery-005"
RECOVERY_ROOT = ROOT / "runs/contained" / RECOVERY_ID
OWNER_SOURCE = ROOT / "approvals/pending/phase4-governed-draft-001-bootstrap/starting-inputs/owner_intake.json"
CONTRACTS = ROOT / "contracts/phase1_3"


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def decode_response(transaction: int) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = json.loads((SOURCE_MISSION / f"control/transaction-{transaction:02d}.bridge-evidence.json").read_text(encoding="utf-8"))
    response = base64.b64decode(evidence["response_base64"], validate=True)
    if sha256(response) != evidence["response_sha256"]:
        raise PermissionError("Accepted response evidence hash mismatch")
    return json.loads(response), evidence


def file_map(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}


def main() -> int:
    if RECOVERY_ROOT.exists():
        raise PermissionError("Recovery root already exists; overwrite prohibited")
    ledger = json.loads((SOURCE_MISSION / "control/transaction-ledger.json").read_text(encoding="utf-8"))
    entries = ledger.get("entries", [])
    if [e.get("status") for e in entries] != ["ACCEPTED", "ACCEPTED", "FAILED_TERMINAL_SLOT_CONSUMED"]:
        raise PermissionError("Source mission ledger is not the expected immutable terminal chain")
    blueprint, aria_evidence = decode_response(2)
    vera, vera_evidence = decode_response(3)
    if vera.get("verdict") != "REVISION_REQUIRED":
        raise PermissionError("Vera recovery requires an explicit REVISION_REQUIRED verdict")

    # Deterministic correction of Vera's two linked hard defects: the collected
    # issue_summary value is the exact source of the handoff request_summary.
    handoff = blueprint["implementation_inputs"]["handoff_contract"]
    handoff["field_mappings"] = {
        "request_summary": {
            "source_field": "issue_summary",
            "transform": "IDENTITY_TRIM",
            "empty_behavior": "BLOCK_HANDOFF",
        }
    }
    handoff["required_source_fields"] = ["issue_summary"]
    for requirement in blueprint["requirements"]:
        if requirement.get("id") == "REQ-005":
            requirement["statement"] += " The request_summary value shall be the trimmed issue_summary value without semantic rewriting."
            requirement["acceptance_test"] += " Verify request_summary exactly equals issue_summary after leading and trailing whitespace is removed."
    blueprint["implementation_handoff"]["new_work_required"].append(
        "Map issue_summary to request_summary using IDENTITY_TRIM and block handoff when issue_summary is empty."
    )
    blueprint["authority"]["specification_status"] = "SPECIFICATION_READY_FOR_BUILD"
    blueprint["run_id"] = RECOVERY_ID
    blueprint["raw_intake"]["recovery_provenance"] = {
        "source_mission": "phase4-governed-draft-001",
        "source_aria_output_sha256": entries[1]["output_sha256"],
        "source_vera_response_sha256": vera_evidence["response_sha256"],
        "remediation": "VERA_DEFECTS_ONLY",
    }
    experience_shell = {
        "schema_version": "0.1",
        "presence_mode": "EXISTING_ANAM",
        "selection_status": "FACTORY_RECOMMENDED",
        "avatar": {
            "provider": "ANAM",
            "existing_avatar_id": "edf6fdcb-acab-44b8-b974-ded72665ee26",
            "creation_brief": None,
            "stock_asset_id": "ANAM-STOCK-MIA-SUPPORT-GUIDE",
            "display_name": "Mia",
        },
        "voice": {"voice_id": "8cc80a30-4fc0-11f1-84b0-52bacf74fa75", "style": "Dana - Balanced Spirit (Sonic 3.5); patient, upbeat, and reassuring", "pace": "BALANCED", "fallback_to_text": True},
        "visual_environment": {"background_brief": "Use Mia's ANAM stock portrait in a clean, warm home-services welcome environment", "brand_alignment": "Neutral draft styling until client-approved colors and marks are supplied", "framing": "PORTRAIT"},
        "channels": ["WEB", "MOBILE_WEB", "TEXT_FALLBACK"],
        "fallback": {"mode": "STOCK_IMAGE_AND_TEXT", "preserve_conversation_state": True, "user_message": "The visual assistant is unavailable, so we have continued in text mode."},
        "disclosure": {"identify_as_ai": True, "visible_label": "AI concierge", "opening_disclosure": "I am an AI concierge helping prepare your request for staff review."},
        "integration": {"connector": "X_LINK_ANAM_ADAPTER", "agent_core_transport": "NOT_CONFIGURED", "credentials_required": True, "compatibility_status": "NOT_CHECKED"},
        "authority": {"provider_creation_authorized": False, "provider_mutation_authorized": False, "deployment_authorized": False, "production_approved": False},
    }
    experience_schema = json.loads((ROOT / "contracts/phase4/experience_shell.v0.1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(experience_schema).validate(experience_shell)
    blueprint["raw_intake"]["experience_shell"] = experience_shell
    blueprint["implementation_inputs"]["experience_shell"] = experience_shell
    blueprint["capabilities"]["required"].append("Selectable ANAM, stock-image, or text-only experience shell with graceful fallback")
    blueprint["implementation_handoff"]["new_work_required"].extend([
        "Present a lightweight presence choice after the core owner brief: existing ANAM avatar, create new ANAM avatar, stock image, or text-only.",
        "Keep the X-Agent core independent from the experience shell and connect them through the X-Link ANAM adapter.",
        "Preserve a stock-image-and-text fallback when ANAM is unavailable or not yet configured.",
    ])
    schema = json.loads((ROOT / "contracts/x_agent_blueprint.v0.2.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(blueprint)

    owner = json.loads(OWNER_SOURCE.read_text(encoding="utf-8"))
    owner["run_id"] = RECOVERY_ID
    owner["experience_shell"] = experience_shell
    owner["implementation_inputs"]["experience_shell"] = experience_shell
    owner["implementation_inputs"]["handoff_contract"]["field_mappings"] = handoff["field_mappings"]
    owner["implementation_inputs"]["handoff_contract"]["required_source_fields"] = ["issue_summary"]

    RECOVERY_ROOT.mkdir(parents=True)
    blueprint_path = RECOVERY_ROOT / "artifacts/aria-blueprint.remediated.v0.2.json"
    owner_path = RECOVERY_ROOT / "artifacts/owner-intake.remediated.v0.2.json"
    write_new(blueprint_path, canonical(blueprint))
    write_new(owner_path, canonical(owner))
    write_new(RECOVERY_ROOT / "artifacts/experience-shell.v0.1.json", canonical(experience_shell))
    presence_component = {
        "schema_version": "0.1",
        "component_id": "CMP-ANAM-PRESENCE-SHELL",
        "name": "ANAM avatar presence shell",
        "category": "experience-layer",
        "status": "COMPATIBILITY_CHECK_REQUIRED",
        "requirements_served": ["existing or new ANAM avatar", "stock-image fallback", "text fallback", "voice and visual environment", "AI disclosure"],
        "dependencies": ["ANAM provider compatibility review", "X-Link ANAM adapter", "owner acceptance or replacement of the Factory-recommended Mia stock persona", "client-approved brand assets"],
        "constraints": ["No provider creation or mutation without explicit approval", "No credentials in generated artifacts", "Agent core must remain usable without the avatar"],
        "evidence_status": "DESIGN_CONTRACT_ONLY_NOT_RUNTIME_PROVEN"
    }
    write_new(RECOVERY_ROOT / "artifacts/component-anam-presence-shell.v0.1.json", canonical(presence_component))

    builds = []
    env = os.environ.copy()
    env["X_FACTORY_NETWORK_DISABLED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    for key in ("ANTHROPIC_API_KEY", "HERMES_API_KEY", "NVIDIA_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)
    for number, label in ((1, "RUN_1"), (2, "RUN_2")):
        base = RECOVERY_ROOT / "build" / f"run-{number}"
        output, evidence = base / "output", base / "evidence"
        output.mkdir(parents=True)
        evidence.mkdir()
        process = subprocess.run(
            [sys.executable, "-m", "x_factory.bundle_generator_v0_4", "generate", "--blueprint", str(blueprint_path), "--contracts", str(CONTRACTS), "--output", str(output), "--evidence", str(evidence), "--run-label", label],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
        )
        if process.returncode:
            raise RuntimeError(f"{label} failed: {process.stderr.strip()}")
        builds.append({"label": label, "files": file_map(output), "evidence": file_map(evidence)})
    if builds[0]["files"] != builds[1]["files"]:
        raise PermissionError("Recovery builds are not deterministic")

    preview = RECOVERY_ROOT / "preview"
    preview.mkdir()
    previous = os.environ.get("X_FACTORY_NETWORK_DISABLED")
    os.environ["X_FACTORY_NETWORK_DISABLED"] = "1"
    try:
        generate_preview(owner_path, blueprint_path, preview)
    finally:
        if previous is None:
            os.environ.pop("X_FACTORY_NETWORK_DISABLED", None)
        else:
            os.environ["X_FACTORY_NETWORK_DISABLED"] = previous

    record = {
        "schema_version": "0.1",
        "recovery_id": RECOVERY_ID,
        "status": "LOCAL_REMEDIATED_DRAFT_READY",
        "source_mission_status": "FAILED_TERMINAL_SLOT_CONSUMED",
        "provider_transactions": 0,
        "network_attempts": 0,
        "external_actions": 0,
        "remediated_defects": vera["defects"],
        "aria_execution_sha256": sha256(canonical(aria_evidence)),
        "vera_execution_sha256": sha256(canonical(vera_evidence)),
        "repeatable": True,
        "builds": builds,
        "preview_files": file_map(preview),
        "preview": "preview/index.html",
        "experience_shell": "artifacts/experience-shell.v0.1.json",
        "presence_component": "artifacts/component-anam-presence-shell.v0.1.json",
        "limitations": ["Local deterministic remediation; not a passed five-stage Hermes mission", "Mia is a Factory recommendation from ANAM's stock library, not an owner-selected or deployed persona", "ANAM runtime compatibility and usage terms remain unchecked", "No installation, deployment, release, or production authority"],
    }
    write_new(RECOVERY_ROOT / "recovery-record.json", canonical(record))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
