#!/usr/bin/env python3
"""Provider-free regression for Troy's governed Prompt Forge package."""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import ROOT, load_json, sha256
from x_factory.prompt_forge_v0_1 import compile_prompt_package


def main() -> int:
    brief = {
        "display_name": "Ava — Home Services Concierge",
        "agent_name": "Ava",
        "role_title": "Home Services Concierge",
        "client_name": "Summit Home Services",
        "purpose": "Answer approved home-service questions, qualify customer requests, and prepare a clear staff handoff.",
        "client_context": "A locally operated home-services company.",
        "personality": "Warm, concise, transparent, capable, and reassuringWarm, concise, transparent, capable, and reassuringWarmWarm, concise, knowledgeable, calm, practical, and reassuring. Ask useful follow-up questions without sounding scripted or overly salesy., concise, transparent, capable, and reassuring",
        "must_accomplish": ["Answer supported questions", "Capture service requests", "Prepare a staff handoff"],
        "never_do": ["Invent pricing", "Guarantee appointment availability"],
        "target_users": ["Prospective customers", "Existing customers"],
        "output_artifact": "Structured staff handoff",
    }
    entries = [{
        "entry_id": "K-0001",
        "kind": "FAQ",
        "title": "Water heater repairs",
        "statement": "Summit repairs residential water heaters.",
        "source": {"file": "services.md", "line_start": 1, "line_end": 1, "file_sha256": "a" * 64},
    }]
    package = compile_prompt_package(brief, entries, "verify-troy-prompt-forge")
    manifest = json.loads(package["values"]["instance/system-prompt/PROMPT_FORGE_MANIFEST.v0.1.json"])
    prompt = package["prompt"]
    Draft202012Validator(load_json(ROOT / "contracts/prompt_forge_package.v0.1.schema.json")).validate(manifest)
    assert manifest["specialist"] == "Troy"
    assert manifest["mode"] == "ARIA_CONTROLLED_PROMPT_FORGE_SIDECAR"
    assert manifest["input_binding"]["knowledge_entry_ids"] == ["K-0001"]
    assert manifest["outputs"]["system_prompt_sha256"] == sha256(prompt.encode("utf-8"))
    assert "reassuringWarm" not in prompt
    assert "WarmWarm" not in prompt
    assert prompt.count("Warm, concise, knowledgeable, calm, practical, and reassuring.") == 1
    assert "Ask useful follow-up questions without sounding scripted or overly salesy." in prompt
    assert "[K-0001]" in prompt
    assert "Informational questions" in prompt
    assert "previous and corrected values" in prompt
    assert "ANAM may provide the approved visual avatar and voice" in prompt
    assert "internal chassis" in prompt
    assert len(json.loads(package["values"]["instance/system-prompt/PROMPT_TESTS.v0.1.json"])["tests"]) == 8
    print(json.dumps({
        "status": "PASS",
        "specialist": "Troy",
        "system_prompt_sha256": package["system_prompt_sha256"],
        "knowledge_bindings": package["knowledge_entry_count"],
        "prompt_tests": manifest["quality"]["test_count"],
        "provider_calls": manifest["authority"]["provider_calls"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
