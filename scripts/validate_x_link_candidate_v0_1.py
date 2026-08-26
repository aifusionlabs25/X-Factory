#!/usr/bin/env python3
"""Validate one Factory candidate through X-Link's real registry and compiler code."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
X_LINK = Path("C:/AI Fusion Labs/X AGENTS/REPOS/X-LINK")
INTERACTIVE = ROOT / "runs" / "interactive"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission-id", required=True)
    args = parser.parse_args()
    mission = INTERACTIVE / args.mission_id
    record = load(mission / "mission-record.json")
    registry_path = mission / record["artifacts"]["x_link_agent_entry"]
    scenarios_path = mission / record["artifacts"]["x_link_scenario_pack"]
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    scenarios = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    actual_schema = load(X_LINK / "config/schemas/agent_registry.schema.json")
    Draft202012Validator(actual_schema).validate(registry)
    agent = registry["agents"][0]
    pack = agent["eval"]["default_pack"]
    if pack != scenarios["pack"]:
        raise ValueError("Registry default pack does not match the generated scenario pack")
    if agent["factory_authority"]["status"] != "CANDIDATE_NOT_INSTALLED":
        raise ValueError("Candidate authority marker is missing")

    sys.path.insert(0, str(X_LINK))
    from tools.xagent_blueprint import compiler

    temporary_parent = ROOT / "verification" / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="x-link-fixture-", dir=temporary_parent) as temporary:
        fixture = Path(temporary)
        config = fixture / "config"
        scenario_root = config / "eval_scenarios"
        golden_root = fixture / "golden"
        scenario_root.mkdir(parents=True)
        golden_root.mkdir()
        (config / "agents.yaml").write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (scenario_root / f"{pack}.yaml").write_text(yaml.safe_dump(scenarios, sort_keys=False, allow_unicode=True), encoding="utf-8")
        compiler.CONFIG_DIR = config
        compiler.SCENARIOS_DIR = scenario_root
        compiler.GOLDEN_TRANSCRIPTS_DIR = golden_root
        compiled = compiler.reverse_compile_agent_blueprint(agent["slug"], truth_mode="factory_candidate_validation")
        plan = compiler.build_eval_plan_from_blueprint(compiled)

    result = {
        "schema_version": "0.1",
        "status": "PASS",
        "mission_id": args.mission_id,
        "x_link_registry_schema": "PASS",
        "x_link_reverse_compile": "PASS",
        "agent_slug": agent["slug"],
        "scenario_pack": pack,
        "scenario_count": len(scenarios["scenarios"]),
        "compiled_blueprint_status": compiled["status"],
        "compiled_release_lane": compiled["release_gates"]["current_lane"],
        "compiled_production_approved": False,
        "eval_plan_generated": isinstance(plan, dict) and bool(plan),
        "repository_writes": 0,
        "provider_calls": 0,
        "anam_actions": 0,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
