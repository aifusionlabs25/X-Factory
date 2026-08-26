#!/usr/bin/env python3
"""Run local-only positive and negative tests for the Phase 4 broker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator

FACTORY_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(FACTORY_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORY_MODULE_ROOT))

from x_factory.phase4_broker import Phase4Broker, SEQUENCE, sha256_bytes, verify_bytes


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expect_blocked(name: str, action: Callable[[], None]) -> dict[str, str]:
    try:
        action()
    except (PermissionError, ValueError) as error:
        return {"id": name, "status": "PASS", "observed": type(error).__name__}
    raise AssertionError(f"{name} did not fail closed")


def fresh_broker() -> Phase4Broker:
    return Phase4Broker("phase4-synthetic-mission-001", sha256_bytes(b"synthetic intake\n"))


def advance_to(broker: Phase4Broker, count: int) -> None:
    broker.approve_launch()
    prior = broker.intake_hash
    for index, (stage, actor) in enumerate(SEQUENCE[:count]):
        output = sha256_bytes(f"{stage}-output\n".encode())
        broker.advance(
            stage,
            actor,
            {"prior_stage": prior},
            output,
            owner_build_approval=(stage == "OWNER_BUILD_DECISION"),
        )
        prior = output


def run(factory_root: Path) -> dict:
    schema_path = factory_root / "contracts" / "phase4" / "factory_mission_record.v0.1.schema.json"
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)

    positive = fresh_broker()
    advance_to(positive, len(SEQUENCE))
    positive_record = positive.record()
    errors = list(Draft202012Validator(schema).iter_errors(positive_record))
    if errors:
        raise AssertionError("Positive record failed schema: " + "; ".join(error.message for error in errors))
    if positive.state != "DRAFT_READY" or positive.model_transactions != 5 or positive.tool_calls != 0:
        raise AssertionError("Positive lifecycle counters are wrong")

    no_launch = fresh_broker()
    skipped_gate = fresh_broker()
    skipped_gate.approve_launch()
    tool_use = fresh_broker()
    tool_use.approve_launch()
    no_build = fresh_broker()
    advance_to(no_build, 3)
    boundary = fresh_broker()
    advance_to(boundary, 4)
    tamper_hash = sha256_bytes(b"approved bytes")

    negatives = [
        expect_blocked(
            "NEG-001-LAUNCH-REQUIRED",
            lambda: no_launch.advance("ATLAS_TRIAGE", "ATLAS", {"intake": no_launch.intake_hash}, sha256_bytes(b"atlas")),
        ),
        expect_blocked(
            "NEG-002-STAGE-SKIP",
            lambda: skipped_gate.advance("ARIA_BLUEPRINT", "ARIA", {"intake": skipped_gate.intake_hash}, sha256_bytes(b"aria")),
        ),
        expect_blocked(
            "NEG-003-NONZERO-TOOLS",
            lambda: tool_use.advance("ATLAS_TRIAGE", "ATLAS", {"intake": tool_use.intake_hash}, sha256_bytes(b"atlas"), runtime_tool_calls=1),
        ),
        expect_blocked(
            "NEG-004-OWNER-BUILD-APPROVAL-REQUIRED",
            lambda: no_build.advance("OWNER_BUILD_DECISION", "ROB", {"vera_spec": sha256_bytes(b"verdict")}, sha256_bytes(b"decision")),
        ),
        expect_blocked(
            "NEG-005-CANDIDATE-WRITE-BEFORE-BUILD-GATE",
            lambda: no_build.candidate_path(factory_root / "runs" / "contained" / "mission" / "candidate", factory_root / "runs" / "contained" / "mission" / "candidate" / "agent" / "AGENT.md"),
        ),
        expect_blocked(
            "NEG-006-WRITE-BOUNDARY",
            lambda: boundary.candidate_path(factory_root / "runs" / "contained" / "mission" / "candidate", factory_root.parent / "escaped.txt"),
        ),
        expect_blocked(
            "NEG-007-HASH-DRIFT",
            lambda: verify_bytes(b"tampered bytes", tamper_hash, "frozen candidate"),
        ),
    ]

    root = factory_root / "verification" / "phase4" / "virtual-candidate-root"
    allowed = boundary.candidate_path(root, root / "agent" / "AGENT.md")
    if root.resolve() not in allowed.parents:
        raise AssertionError("Positive boundary check failed")

    return {
        "schema_version": "0.1",
        "status": "PASS",
        "provider_calls": 0,
        "model_calls": 0,
        "filesystem_mutation_outside_test_report": False,
        "positive": {
            "id": "POS-001-COMPLETE-LIFECYCLE",
            "status": "PASS",
            "final_state": positive.state,
            "simulated_model_transactions": positive.model_transactions,
            "tool_calls": positive.tool_calls,
            "record": positive_record,
        },
        "negative_tests": negatives,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    factory_root = args.factory_root.resolve()
    report_path = args.report.resolve()
    try:
        report_path.relative_to(factory_root)
    except ValueError as error:
        raise PermissionError("Phase 4 test report must remain inside the Factory root") from error
    result = run(factory_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "report": str(report_path), "negative_tests": len(result["negative_tests"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
