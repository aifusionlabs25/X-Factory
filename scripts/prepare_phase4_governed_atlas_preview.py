#!/usr/bin/env python3
"""Create the exact provider-free Atlas payload and prompt preview."""

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.phase4_broker import sha256_bytes
from x_factory.phase4_payloads import canonical
from x_factory.phase4_payloads_v0_3 import make_stage_payload_v0_3

PACKET = ROOT / "approvals/pending/phase4-governed-draft-001-mission"
OWNER = ROOT / "approvals/pending/phase4-governed-draft-001-bootstrap/starting-inputs/owner_intake.json"
GOVERNANCE = PACKET / "starting-inputs/governance-binding.json"
SCHEMA = ROOT / "contracts/phase4/normalized_intake.v0.2.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


payload = make_stage_payload_v0_3(
    "ATLAS_TRIAGE",
    "phase4-governed-draft-001",
    {"owner_intake": load(OWNER)},
    "normalized_intake.v0.2",
    load(GOVERNANCE),
)
prompt = (
    "Return only one JSON object that validates against the exact JSON Schema below. "
    "Do not wrap it in Markdown. Do not use tools, MCP, memory, delegation, files, or external actions.\n"
    "GOVERNED PAYLOAD:\n" + canonical(payload).decode("utf-8") + "\n"
    "EXACT OUTPUT JSON SCHEMA:\n" + canonical(load(SCHEMA)).decode("utf-8")
)
(PACKET / "atlas-derived-payload.json").write_bytes(canonical(payload))
(PACKET / "atlas-derived-prompt.txt").write_text(prompt, encoding="utf-8", newline="")
print(json.dumps({"payload_sha256": sha256_bytes(canonical(payload)), "prompt_sha256": sha256_bytes(prompt.encode()), "network_calls": 0}, indent=2))
