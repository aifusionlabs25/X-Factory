#!/usr/bin/env python3
"""Prepare the exact, inactive Luna-to-ANAM visual canary packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "runs" / "interactive"
REVIEWS = ROOT / "reviews"
CANARIES = ROOT / "canaries" / "anam"
SCHEMA_PATH = ROOT / "contracts" / "anam_luna_spoken_response.v0.1.schema.json"
CERTIFICATION_PATH = ROOT / "verification" / "mission-control" / "hermes-semantic-certification.v0.1.json"
ANAM_ENV_PATH = Path("C:/AI Fusion Labs/X AGENTS/REPOS/X-LINK/.env")
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
REVIEW_ID = re.compile(r"^review-[0-9]{8}-[0-9]{6}$")


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


def credential_metadata() -> dict[str, Any]:
    exists = ANAM_ENV_PATH.is_file()
    key_declared = False
    if exists:
        for line in ANAM_ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            if re.match(r"^\s*ANAM_API_KEY\s*=", line):
                key_declared = True
                break
    return {
        "path": str(ANAM_ENV_PATH),
        "file_exists": exists,
        "key_name": "ANAM_API_KEY",
        "key_declared": key_declared,
        "credential_contents_read_during_activation_only": True,
        "credential_contents_persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--canary-id", default="mia-luna-visual-canary-002")
    args = parser.parse_args()
    if not MISSION_ID.fullmatch(args.mission_id) or not REVIEW_ID.fullmatch(args.review_id):
        raise SystemExit("Invalid mission or review ID")
    if not MISSION_ID.fullmatch(args.canary_id):
        raise SystemExit("Invalid canary ID")

    mission = (MISSIONS / args.mission_id).resolve(strict=True)
    review = (REVIEWS / args.mission_id / args.review_id).resolve(strict=True)
    certification = load(CERTIFICATION_PATH)
    summary_path = review / "semantic-review-summary.json"
    summary = load(summary_path)
    if certification["mission_id"] != args.mission_id or certification["review_id"] != args.review_id:
        raise PermissionError("Certification does not bind this mission and review")
    if summary["status"] != "HERMES_SEMANTIC_REVIEW_PASS" or set(summary["verdicts"].values()) != {"PASS"}:
        raise PermissionError("A unanimous semantic PASS is required")
    if digest(summary_path.read_bytes()) != "sha256:" + certification["evidence"]["summary_sha256"]:
        raise PermissionError("Semantic certification summary drifted")

    blueprint = load(mission / "artifacts" / "aria-blueprint.v0.2.json")
    persona = load(mission / "experience" / "persona-binding.v0.1.json")
    faqs = blueprint["implementation_inputs"]["approved_faqs"]
    if not isinstance(faqs, list) or len(faqs) != 1:
        raise PermissionError("Canary requires exactly one approved FAQ")
    faq = faqs[0]
    question = faq["question"]
    answer = faq["answer"]
    schema = load(SCHEMA_PATH)
    if schema["properties"]["input_question"]["const"] != question:
        raise PermissionError("Question is not bound to the response schema")
    if schema["properties"]["spoken_text"]["const"] != answer:
        raise PermissionError("Approved answer is not bound to the response schema")
    if persona["presence_mode"] != "EXISTING_ANAM":
        raise PermissionError("Canary requires an existing ANAM persona binding")

    payload = {
        "schema_version": "0.1",
        "stage": "CONTAINED_LUNA_RESPONSE_CANARY",
        "authority": "SPEECH_CANARY_ONLY_NO_EXTERNAL_ACTION_OR_PRODUCTION_AUTHORITY",
        "mission_id": args.mission_id,
        "certified_review": {
            "review_id": args.review_id,
            "summary_sha256": digest(summary_path.read_bytes()),
            "verdicts": summary["verdicts"],
        },
        "input_question": question,
        "approved_answer": answer,
        "constraints": {
            "return_approved_answer_verbatim": True,
            "no_tools": True,
            "no_external_facts": True,
            "no_external_actions": True,
            "text_fallback_must_equal_spoken_text": True,
        },
    }
    prompt = (
        "You are the contained runtime voice-response canary for one certified X-Agent candidate. "
        "Use only PAYLOAD and return exactly one JSON object satisfying OUTPUT_SCHEMA. "
        "The spoken_text and text_fallback must reproduce the approved answer verbatim. "
        "Do not use tools, memory, external knowledge, or unstated assumptions.\n"
        f"PAYLOAD\n{json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
        f"OUTPUT_SCHEMA\n{json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
    ).encode("utf-8")
    session_request = {
        "personaConfig": {
            "name": "Mia - X-Factory Canary",
            "avatarId": persona["avatar"]["existing_avatar_id"],
            "voiceId": persona["voice"]["voice_id"],
            "llmId": "CUSTOMER_CLIENT_V1",
            "systemPrompt": "Contained speech canary only. Speak only text supplied by the client.",
        }
    }
    public_config = {
        "schema_version": "0.1",
        "canary_id": args.canary_id,
        "mission_id": args.mission_id,
        "persona": "Mia",
        "question": question,
        "expected_spoken_text": answer,
        "text_fallback": answer,
        "model": "openai-codex / gpt-5.6-luna",
        "sdk_version": "@anam-ai/js-sdk@4.25.0",
        "maximum_luna_calls": 1,
        "maximum_anam_sessions": 1,
        "production": False,
    }
    implementation_paths = {
        "runner": ROOT / "scripts" / "run_anam_luna_canary_v0_1.py",
        "hermes_bridge": ROOT / "scripts" / "anam_luna_canary_bridge_v0_1.py",
        "html": ROOT / "apps" / "anam-canary" / "index.html",
        "javascript": ROOT / "apps" / "anam-canary" / "app.js",
        "styles": ROOT / "apps" / "anam-canary" / "styles.css",
        "package_lock": ROOT / "apps" / "anam-canary" / "package-lock.json",
        "sdk_umd": ROOT / "apps" / "anam-canary" / "node_modules" / "@anam-ai" / "js-sdk" / "dist" / "umd" / "anam.js",
    }
    for label, path in implementation_paths.items():
        if not path.is_file():
            raise PermissionError(f"Required canary implementation is missing: {label}")
    manifest = {
        "schema_version": "0.1",
        "canary_id": args.canary_id,
        "mission_id": args.mission_id,
        "status": "PREPARED_INACTIVE",
        "purpose": "Verify one schema-bound Luna response is rendered unchanged as both visible text and Mia speech.",
        "provider_transactions": [
            {
                "sequence": 1,
                "provider": "openai-codex",
                "model": "gpt-5.6-luna",
                "reasoning": "low",
                "profile": "aria",
                "prompt_sha256": digest(prompt),
                "payload_sha256": digest(canonical(payload)),
            },
            {
                "sequence": 2,
                "provider": "ANAM",
                "operation": "EPHEMERAL_SESSION_TOKEN_AND_ONE_TALK_COMMAND",
                "session_request_sha256": digest(canonical(session_request)),
                "spoken_text_sha256": digest(answer.encode("utf-8")),
            },
        ],
        "credential": credential_metadata(),
        "authentication": {
            "hermes_auth_path": "C:/Users/AI Fusion Labs/AppData/Local/hermes/auth.json",
            "hermes_auth_access": "READ_ONLY_CONTENTS_MUST_REMAIN_UNCHANGED",
            "codex_cli_authentication": "NONPARTICIPATING_MAY_NOT_BE_READ_IMPORTED_OR_MUTATED",
            "aria_runtime_path": "C:/Users/AI Fusion Labs/AppData/Local/hermes/profiles/aria",
            "aria_runtime_writes": "ORDINARY_SESSION_DATABASE_CACHE_LOG_AND_LOCK_STATE_ONLY",
        },
        "runtime": {
            "local_origin": "http://127.0.0.1:8899",
            "sdk": "@anam-ai/js-sdk@4.25.0",
            "disable_input_audio": True,
            "text_fallback_visible_before_session": True,
            "session_token_persisted": False,
            "api_key_sent_to_browser": False,
        },
        "implementation_sha256": {label: digest(path.read_bytes()) for label, path in implementation_paths.items()},
        "ceilings": {"luna_calls": 1, "anam_sessions": 1, "talk_commands": 1, "retries": 0},
        "authorized_writes": [
            f"canaries/anam/{args.canary_id}",
            "C:/Users/AI Fusion Labs/AppData/Local/hermes/profiles/aria",
        ],
        "prohibited": [
            "ANAM persona creation or mutation",
            "credential mutation or disclosure",
            "Hermes authentication mutation or OAuth refresh",
            "microphone capture",
            "tools, MCP, memory, or delegation",
            "candidate mutation",
            "X-Link repository writes",
            "deployment, release, or production",
            "any retry after a consumed provider slot",
        ],
    }

    root = CANARIES / args.canary_id
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "luna-payload.v0.1.json", payload)
    write_new(root / "luna-prompt.txt", prompt)
    write_new(root / "anam-session-request.v0.1.json", session_request)
    write_new(root / "public-config.v0.1.json", public_config)
    write_new(root / "activation-manifest.v0.1.json", manifest)
    manifest_sha = digest((root / "activation-manifest.v0.1.json").read_bytes())
    approval = (
        f"# Mia/Luna contained visual canary approval packet\n\n"
        f"Canary: `{args.canary_id}`  \nMission: `{args.mission_id}`  \n"
        f"Activation manifest: `{manifest_sha.removeprefix('sha256:')}`  \n"
        f"Exact Luna payload: `{digest(canonical(payload)).removeprefix('sha256:')}`  \n"
        f"Exact Luna prompt: `{digest(prompt).removeprefix('sha256:')}`  \n"
        f"Exact ANAM session request: `{digest(canonical(session_request)).removeprefix('sha256:')}`  \n"
        f"Exact spoken text: `{answer}`\n\n"
        "This packet remains inactive until separately approved. It permits one Luna call, one ephemeral ANAM session, "
        "and one exact talk command, with no retries, microphone capture, persona mutation, credential mutation, "
        "X-Link writes, deployment, release, or production.\n"
    )
    write_new(root / "APPROVAL_PACKET.md", approval.encode("utf-8"))
    print(json.dumps({
        "canary_id": args.canary_id,
        "status": "PREPARED_INACTIVE",
        "activation_manifest_sha256": manifest_sha,
        "luna_payload_sha256": digest(canonical(payload)),
        "luna_prompt_sha256": digest(prompt),
        "anam_session_request_sha256": digest(canonical(session_request)),
        "credential_declared": manifest["credential"]["key_declared"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
