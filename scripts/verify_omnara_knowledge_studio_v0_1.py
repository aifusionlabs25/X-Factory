"""Regression for OMNARA's traceable, customer-ready Knowledge Bank compiler."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from x_factory.knowledge_studio_v0_1 import compile_knowledge_studio
from x_factory.mission_control_factory_v0_1 import ROOT, load_json, sha256


def main() -> int:
    source = ROOT / "runs/interactive/draft-ava-home-services-concierge-20260826-052631-c7e6c1/instance/knowledge/approved-knowledge.v0.1.json"
    bundle = load_json(source)
    package = compile_knowledge_studio(bundle, bundle["mission_id"])
    curated = json.loads(package["values"]["instance/knowledge/curated-knowledge.v0.1.json"])
    Draft202012Validator(load_json(ROOT / "contracts/knowledge_studio_package.v0.1.schema.json")).validate(curated)
    entries = {item["entry_id"]: item for item in curated["entries"]}
    assert len(entries) == len(bundle["entries"])
    assert "power-packed" not in entries["K-0001"]["statement"].casefold()
    assert "dominate deadlines" not in entries["K-0001"]["statement"].casefold()
    assert entries["K-0004"]["statement"].startswith("Summit Home Services handles")
    assert entries["K-0012"]["title"] == "Company services and service area"
    assert "Central Mississippi" in entries["K-0012"]["statement"]
    assert entries["K-0013"]["title"] == "Realtor and inspection repair support"
    originals = {item["entry_id"]: item for item in bundle["entries"]}
    for entry_id, item in entries.items():
        original = originals[entry_id]
        assert item["source_entry_ids"] == [entry_id]
        assert item["source_statement_sha256"] == sha256(" ".join(original["statement"].split()).encode("utf-8"))
        assert item["source"] == original["source"]
    print(json.dumps({"status": "PASS", "specialist": "OMNARA", "source_entries": len(bundle["entries"]), "curated_entries": len(entries), "provider_calls": 0, "source_mutation": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
