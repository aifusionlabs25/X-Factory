"""Read-only Mission Control view of governed ANAM presence readiness."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE_ROOT = ROOT / "runs" / "interactive"
CANARIES_ROOT = ROOT / "canaries" / "anam"
SEMANTIC_CERTIFICATE = ROOT / "verification" / "mission-control" / "hermes-semantic-certification.v0.1.json"
TRANSPORT_CERTIFICATE = ROOT / "verification" / "mission-control" / "anam-continuation-live-008.v0.1.json"
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
CANARY_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
MIA_AVATAR_ID = "edf6fdcb-acab-44b8-b974-ded72665ee26"
MIA_VOICE_ID = "8cc80a30-4fc0-11f1-84b0-52bacf74fa75"


class PresencePreviewError(ValueError):
    """The requested mission cannot produce a governed presence preview."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PresencePreviewError(f"Expected an object: {path.name}")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mission_root(mission_id: str) -> Path:
    if not MISSION_ID.fullmatch(mission_id):
        raise PresencePreviewError("Invalid mission ID")
    root = (INTERACTIVE_ROOT / mission_id).resolve()
    try:
        root.relative_to(INTERACTIVE_ROOT.resolve())
    except ValueError as error:
        raise PresencePreviewError("Invalid mission path") from error
    if not (root / "mission-record.json").is_file():
        raise PresencePreviewError("Mission not found")
    return root


def _semantic_gate(mission_id: str) -> dict[str, Any]:
    if not SEMANTIC_CERTIFICATE.is_file():
        return {"status": "PENDING", "review_id": None, "model": "gpt-5.6-luna"}
    certificate = _load(SEMANTIC_CERTIFICATE)
    passed = (
        certificate.get("mission_id") == mission_id
        and certificate.get("status") == "HERMES_SEMANTIC_REVIEW_PASS"
        and certificate.get("verdicts") == {"atlas": "PASS", "aria": "PASS", "vera": "PASS"}
    )
    return {
        "status": "PASS" if passed else "PENDING",
        "review_id": certificate.get("review_id") if passed else None,
        "model": certificate.get("model", "gpt-5.6-luna"),
    }


def _transport_gate(record: dict[str, Any]) -> dict[str, Any]:
    if not TRANSPORT_CERTIFICATE.is_file():
        return {"status": "PENDING", "proof_id": None}
    certificate = _load(TRANSPORT_CERTIFICATE)
    proved = (
        certificate.get("status") == "CANARY_PASS_SESSION_CLOSED"
        and certificate.get("result") == "MIA_VISUAL_TRANSPORT_PROVEN"
        and certificate.get("exact_spoken_text") == record["agent"]["purpose"]
        and record.get("anam", {}).get("avatar_id") == MIA_AVATAR_ID
        and record.get("anam", {}).get("voice_id") == MIA_VOICE_ID
    )
    return {
        "status": "PASS" if proved else "PENDING",
        "proof_id": certificate.get("canary_id") if proved else None,
    }


def _consumed(canary_root: Path) -> bool:
    executions = canary_root / "executions"
    if not executions.is_dir():
        return False
    for state_path in executions.glob("*/runtime-state.json"):
        try:
            if _load(state_path).get("anam_session_slot_consumed") is True:
                return True
        except (OSError, json.JSONDecodeError, PresencePreviewError):
            return True
    return False


def _prepared_activation(mission_id: str) -> dict[str, Any] | None:
    if not CANARIES_ROOT.is_dir():
        return None
    matches: list[tuple[str, Path, dict[str, Any]]] = []
    for manifest_path in CANARIES_ROOT.glob("*/activation-manifest.v0.1.json"):
        try:
            manifest = _load(manifest_path)
        except (OSError, json.JSONDecodeError, PresencePreviewError):
            continue
        canary_id = str(manifest.get("canary_id", ""))
        if (
            manifest.get("mission_id") == mission_id
            and manifest.get("status") == "PREPARED_INACTIVE"
            and manifest.get("mode") == "ANAM_ONLY_ACCEPTED_LUNA_REUSE"
            and CANARY_ID.fullmatch(canary_id)
            and not _consumed(manifest_path.parent)
        ):
            matches.append((canary_id, manifest_path, manifest))
    if not matches:
        return None
    canary_id, manifest_path, manifest = sorted(matches, key=lambda item: item[0])[-1]
    source_sha = str(manifest["accepted_luna_source"]["sha256"]).removeprefix("sha256:")
    session_sha = str(manifest["provider_transactions"][0]["session_request_sha256"]).removeprefix("sha256:")
    manifest_sha = _digest(manifest_path)
    approval_text = (
        f"I approve activation manifest {manifest_sha} for Mission Control ANAM preview {canary_id}. "
        "I authorize read-only use of the existing ANAM_API_KEY, "
        f"transmission of exact session request {session_sha}, one ephemeral Mia session, and one talk command "
        f"using accepted Luna response {source_sha}. Zero model calls, maximum one ANAM session, no retries, "
        "microphone capture, credential mutation, persona mutation, X-Link writes, deployment, release, or production. "
        "Codex may start the governed local preview server; the owner will launch and end the session from Mission Control."
    )
    return {
        "status": "PREPARED_INACTIVE",
        "canary_id": canary_id,
        "manifest_sha256": manifest_sha,
        "accepted_luna_response_sha256": source_sha,
        "session_request_sha256": session_sha,
        "approval_text": approval_text,
        "runtime_url": "http://127.0.0.1:8899/",
    }


def preview_descriptor(mission_id: str) -> dict[str, Any]:
    mission_root = _mission_root(mission_id)
    record = _load(mission_root / "mission-record.json")
    binding = _load(mission_root / "experience" / "persona-binding.v0.1.json")
    semantic = _semantic_gate(mission_id)
    transport = _transport_gate(record)
    activation = _prepared_activation(mission_id)
    existing_mia = (
        binding.get("presence_mode") == "EXISTING_ANAM"
        and binding.get("avatar", {}).get("existing_avatar_id") == MIA_AVATAR_ID
        and binding.get("voice", {}).get("voice_id") == MIA_VOICE_ID
    )
    live_ready = existing_mia and semantic["status"] == "PASS" and transport["status"] == "PASS" and activation is not None
    agent = record["agent"]
    public_role = agent.get("public_role_title")
    if agent.get("derived_from_chassis") and not public_role:
        from x_factory.chassis_depot_v0_1 import derive_public_role

        chassis = agent.get("derived_from_chassis") or {}
        public_role = derive_public_role(
            agent.get("purpose", ""),
            chassis.get("chassis_role_title") or chassis.get("role_title") or "Concierge",
        )
    public_display_name = (
        f"{agent['agent_name']} — {public_role}"
        if agent.get("derived_from_chassis") and public_role
        else agent.get("agent_name", agent.get("display_name", "X-Agent")) if agent.get("derived_from_chassis") else agent.get("display_name", agent.get("agent_name", "X-Agent"))
    )
    return {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "status": "LIVE_ACTIVATION_PREPARED" if live_ready else "STATIC_PREVIEW_ONLY",
        "agent": {
            "display_name": public_display_name,
            "agent_name": agent.get("agent_name", agent.get("display_name", "X-Agent")),
            "public_role_title": public_role,
            "purpose": record["agent"]["purpose"],
            "persona": binding.get("avatar", {}).get("display_name") or "Text presence",
            "presence_mode": binding.get("presence_mode", "TEXT_ONLY"),
        },
        "persona": {
            "portrait_url": f"/api/missions/{mission_id}/files/experience/portrait.webp" if (mission_root / "experience" / "portrait.webp").is_file() else None,
            "avatar_id": binding.get("avatar", {}).get("existing_avatar_id"),
            "voice_id": binding.get("voice", {}).get("voice_id"),
            "voice_style": binding.get("voice", {}).get("style"),
        },
        "speech": {
            "question": "What can this agent help with?",
            "text_fallback": record["agent"]["purpose"],
            "source": "ACCEPTED_LUNA_RESPONSE" if transport["status"] == "PASS" else "LOCAL_DRAFT_PURPOSE",
        },
        "gates": {
            "local_build": {"status": "PASS", "detail": record.get("status")},
            "semantic_review": semantic,
            "anam_transport": transport,
            "activation_packet": {"status": "PASS" if activation else "PENDING"},
        },
        "activation": activation,
        "authority": {
            "provider_active": False,
            "microphone_capture": False,
            "persona_mutation": False,
            "deployment": False,
            "production": False,
        },
    }


def runtime_status(expected_canary_id: str | None) -> dict[str, Any]:
    if not expected_canary_id or not CANARY_ID.fullmatch(expected_canary_id):
        return {"status": "NOT_PREPARED", "launch_enabled": False}
    try:
        request = urllib.request.Request("http://127.0.0.1:8899/api/config", method="GET")
        with urllib.request.urlopen(request, timeout=0.4) as response:
            config = json.loads(response.read(32 * 1024).decode("utf-8"))
        matches = config.get("canary_id") == expected_canary_id and config.get("preview_mode") is not True
        return {
            "status": "GOVERNED_RUNTIME_READY" if matches else "OTHER_RUNTIME_ACTIVE",
            "launch_enabled": bool(matches),
            "runtime_url": "http://127.0.0.1:8899/" if matches else None,
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return {"status": "AWAITING_ACTIVATION", "launch_enabled": False}
