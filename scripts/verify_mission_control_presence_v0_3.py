#!/usr/bin/env python3
"""Provider-free verification of Mission Control's governed presence descriptor."""

from __future__ import annotations

import json

from x_factory.mission_control_presence_v0_1 import preview_descriptor, runtime_status


MISSION_ID = "draft-operational-qa-concierge-20260821-064103-a3e197"


def main() -> int:
    descriptor = preview_descriptor(MISSION_ID)
    assert descriptor["status"] == "LIVE_ACTIVATION_PREPARED"
    assert descriptor["agent"]["persona"] == "Mia"
    assert descriptor["speech"]["source"] == "ACCEPTED_LUNA_RESPONSE"
    assert descriptor["gates"]["local_build"]["status"] == "PASS"
    assert descriptor["gates"]["semantic_review"]["status"] == "PASS"
    assert descriptor["gates"]["anam_transport"]["status"] == "PASS"
    assert descriptor["gates"]["activation_packet"]["status"] == "PASS"
    assert descriptor["activation"]["canary_id"] == "mia-mission-preview-009"
    assert descriptor["activation"]["manifest_sha256"] == "35db2e07b5cc64a85e501439e12157e0c31c3e419044bd0590ef457816a78a5c"
    assert descriptor["authority"] == {
        "provider_active": False,
        "microphone_capture": False,
        "persona_mutation": False,
        "deployment": False,
        "production": False,
    }
    runtime = runtime_status(descriptor["activation"]["canary_id"])
    assert runtime["status"] == "AWAITING_ACTIVATION"
    assert runtime["launch_enabled"] is False
    print(json.dumps({
        "status": "PASS",
        "mission_id": MISSION_ID,
        "descriptor_status": descriptor["status"],
        "canary_id": descriptor["activation"]["canary_id"],
        "runtime_status": runtime["status"],
        "provider_calls": 0,
        "anam_sessions": 0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
