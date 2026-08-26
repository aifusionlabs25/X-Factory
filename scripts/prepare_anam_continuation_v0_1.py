#!/usr/bin/env python3
"""Prepare an ANAM-only continuation using the accepted Luna canary response."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANARY_ID = "mia-mission-preview-009"
MISSION_ID = "draft-operational-qa-concierge-20260821-064103-a3e197"
SOURCE_RELATIVE = "canaries/anam/mia-luna-visual-canary-005/executions/execution-20260822-011413/luna-response.json"
SOURCE_RESPONSE = ROOT / SOURCE_RELATIVE
SOURCE_SESSION_REQUEST = ROOT / "canaries" / "anam" / "mia-luna-visual-canary-005" / "anam-session-request.v0.1.json"
SOURCE_PUBLIC_CONFIG = ROOT / "canaries" / "anam" / "mia-luna-visual-canary-005" / "public-config.v0.1.json"
ANAM_ENV_PATH = Path("C:/AI Fusion Labs/X AGENTS/REPOS/X-LINK/.env")


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


def key_metadata() -> dict[str, Any]:
    return {
        "path": str(ANAM_ENV_PATH),
        "key_name": "ANAM_API_KEY",
        "validated_at_activation": True,
        "contents_persisted_in_evidence": False,
    }


def main() -> int:
    root = ROOT / "canaries" / "anam" / CANARY_ID
    if root.exists():
        raise PermissionError("Continuation canary already exists")
    response = load(SOURCE_RESPONSE)
    expected_text = "Create a contained operational concierge that answers approved questions and prepares a structured local review handoff."
    if response.get("spoken_text") != expected_text or response.get("text_fallback") != expected_text:
        raise PermissionError("Accepted Luna response is not the certified text")
    session_request = load(SOURCE_SESSION_REQUEST)
    config = load(SOURCE_PUBLIC_CONFIG)
    config.update({
        "canary_id": CANARY_ID,
        "maximum_luna_calls": 0,
        "maximum_anam_sessions": 1,
        "accepted_luna_source_reused": True,
    })
    implementation_paths = {
        "runner": ROOT / "scripts" / "run_anam_luna_canary_v0_1.py",
        "html": ROOT / "apps" / "anam-canary" / "index.html",
        "javascript": ROOT / "apps" / "anam-canary" / "app.js",
        "styles": ROOT / "apps" / "anam-canary" / "styles.css",
        "package_lock": ROOT / "apps" / "anam-canary" / "package-lock.json",
        "sdk_umd": ROOT / "apps" / "anam-canary" / "node_modules" / "@anam-ai" / "js-sdk" / "dist" / "umd" / "anam.js",
    }
    for label, path in implementation_paths.items():
        if not path.is_file():
            raise PermissionError(f"Missing continuation implementation: {label}")
    manifest = {
        "schema_version": "0.1",
        "canary_id": CANARY_ID,
        "mission_id": MISSION_ID,
        "mode": "ANAM_ONLY_ACCEPTED_LUNA_REUSE",
        "status": "PREPARED_INACTIVE",
        "purpose": "Launch one governed Mission Control visual preview using the accepted exact Luna response.",
        "accepted_luna_source": {
            "path": SOURCE_RELATIVE,
            "sha256": digest(SOURCE_RESPONSE.read_bytes()),
            "prior_canary": "mia-luna-visual-canary-005",
            "prior_execution": "execution-20260822-011413",
            "schema_valid": True,
        },
        "provider_transactions": [{
            "sequence": 1,
            "provider": "ANAM",
            "operation": "EPHEMERAL_SESSION_TOKEN_AND_ONE_TALK_COMMAND",
            "session_request_sha256": digest(canonical(session_request)),
            "spoken_text_sha256": digest(expected_text.encode("utf-8")),
        }],
        "credential": key_metadata(),
        "runtime": {
            "local_origin": "http://127.0.0.1:8899",
            "sdk": "@anam-ai/js-sdk@4.25.0",
            "disable_input_audio": True,
            "text_fallback_visible_before_session": True,
            "session_token_persisted": False,
            "api_key_sent_to_browser": False,
        },
        "implementation_sha256": {label: digest(path.read_bytes()) for label, path in implementation_paths.items()},
        "ceilings": {"luna_calls": 0, "anam_sessions": 1, "talk_commands": 1, "retries": 0},
        "authorized_writes": [f"canaries/anam/{CANARY_ID}"],
        "prohibited": [
            "any additional Luna or other model call",
            "ANAM persona creation or mutation",
            "credential mutation or disclosure",
            "microphone capture",
            "tools, MCP, memory, or delegation",
            "candidate mutation",
            "X-Link repository writes",
            "deployment, release, or production",
            "any retry after the single ANAM session slot is consumed",
        ],
    }
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "anam-session-request.v0.1.json", session_request)
    write_new(root / "public-config.v0.1.json", config)
    write_new(root / "activation-manifest.v0.1.json", manifest)
    manifest_sha = digest((root / "activation-manifest.v0.1.json").read_bytes())
    packet = (
        "# ANAM-only continuation approval packet\n\n"
        f"Canary: `{CANARY_ID}`  \nMission: `{MISSION_ID}`  \n"
        f"Activation manifest: `{manifest_sha.removeprefix('sha256:')}`  \n"
        f"Accepted Luna response: `{digest(SOURCE_RESPONSE.read_bytes()).removeprefix('sha256:')}`  \n"
        f"Exact ANAM session request: `{digest(canonical(session_request)).removeprefix('sha256:')}`  \n"
        f"Exact spoken text: `{expected_text}`\n\n"
        "This continuation makes zero model calls. It permits one ephemeral ANAM session and one exact talk command, "
        "with no retries, microphone capture, persona mutation, credential mutation, X-Link writes, deployment, release, or production.\n"
    )
    write_new(root / "APPROVAL_PACKET.md", packet.encode("utf-8"))
    print(json.dumps({
        "canary_id": CANARY_ID,
        "status": "PREPARED_INACTIVE",
        "activation_manifest_sha256": manifest_sha,
        "accepted_luna_response_sha256": digest(SOURCE_RESPONSE.read_bytes()),
        "anam_session_request_sha256": digest(canonical(session_request)),
        "luna_calls": 0,
        "anam_sessions": 0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
