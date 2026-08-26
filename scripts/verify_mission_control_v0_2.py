#!/usr/bin/env python3
"""Provider-free verification for Mission Control v0.2 build outputs."""

from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from x_factory import mission_control_factory_v0_1 as factory


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    brief = {
        "purpose": "Create a bounded concierge that answers approved questions and prepares a local handoff.",
        "agent_or_client": "Factory v0.2 Verification Concierge",
        "personality": "Warm, concise, and transparent",
        "must_accomplish": "Answer approved questions; qualify the request; prepare a staff handoff",
        "never_do": "Invent business facts; book appointments; transmit data",
        "target_users": "Synthetic verification visitors",
        "output_artifact": "Structured staff handoff",
        "presence_mode": "EXISTING_ANAM",
        "persona_catalog_id": "ANAM-STOCK-MIA-SUPPORT-GUIDE",
    }
    temporary_parent = factory.ROOT / "verification" / "mission-control" / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_parent / f"x-factory-v02-{secrets.token_hex(4)}"
    temporary.mkdir()
    try:
        original_root = factory.INTERACTIVE_ROOT
        factory.INTERACTIVE_ROOT = temporary
        try:
            record = factory.create_mission(brief, "factory-v02-verification")
        finally:
            factory.INTERACTIVE_ROOT = original_root
        mission = temporary / record["mission_id"]
        assert record["status"] == "LOCAL_CANDIDATE_BUILT"
        assert len(record["specialists"]) == 7
        assert all(stage["status"] == "PASS" for stage in record["specialists"])
        assert record["provider"]["calls"] == 0
        assert record["anam"]["provider_actions"] == 0
        assert len(record["artifacts"]) == 15

        x_link = load(mission / record["artifacts"]["x_link_package"])
        semantic = load(mission / record["artifacts"]["hermes_review_packet"])
        canary = load(mission / record["artifacts"]["x_link_canary_plan"])
        registry = load(mission / record["artifacts"]["x_link_agent_entry"])
        scenarios = load(mission / record["artifacts"]["x_link_scenario_pack"])
        Draft202012Validator(load(factory.X_LINK_SCHEMA)).validate(x_link)
        Draft202012Validator(load(factory.SEMANTIC_PACKET_SCHEMA)).validate(semantic)
        assert x_link["status"] == "CANDIDATE_NOT_INSTALLED"
        assert x_link["presence"]["avatar"]["display_name"] == "Mia"
        assert semantic["status"] == "PREPARED_NOT_TRANSMITTED"
        assert semantic["execution_policy"]["maximum_calls"] == 3
        assert semantic["authority"]["provider_actions_performed"] == 0
        assert canary["status"] == "INACTIVE"
        assert canary["authority"]["anam_session_authorized"] is False
        Draft202012Validator(load(factory.X_LINK_REGISTRY_SCHEMA)).validate(registry)
        assert registry["agents"][0]["factory_authority"]["status"] == "CANDIDATE_NOT_INSTALLED"
        assert len(scenarios["scenarios"]) == 3
        print(json.dumps({
            "status": "PASS",
            "factory_stages": len(record["specialists"]),
            "artifact_count": len(record["artifacts"]),
            "x_link_package": x_link["status"],
            "hermes_review_packet": semantic["status"],
            "provider_calls": record["provider"]["calls"],
            "anam_actions": record["anam"]["provider_actions"],
        }, indent=2))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
