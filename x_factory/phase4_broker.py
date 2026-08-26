"""Deterministic lifecycle broker for the first contained Phase 4 mission.

This module performs no model, provider, network, installation, or deployment
work.  It validates stage order, authority gates, hashes, and write boundaries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MARKER = "X_FACTORY_CONTAINED_MISSION_V0_1"
MODE = "CONTAINED_DRAFT_ONLY"
MODEL_ACTORS = {"ATLAS", "ARIA", "VERA", "MASON"}
SEQUENCE = (
    ("ATLAS_TRIAGE", "ATLAS"),
    ("ARIA_BLUEPRINT", "ARIA"),
    ("VERA_SPEC_REVIEW", "VERA"),
    ("OWNER_BUILD_DECISION", "ROB"),
    ("MASON_PLAN", "MASON"),
    ("DETERMINISTIC_BUILD", "DETERMINISTIC_BUILDER"),
    ("VERA_BUILD_REVIEW", "VERA"),
    ("DRAFT_READY", "BROKER"),
)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def require_digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError(f"{label} is not a SHA-256 digest")
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError(f"{label} is not a SHA-256 digest")
    return value


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise PermissionError(f"{label} must remain inside {root.resolve()}") from error
    return resolved


def verify_bytes(data: bytes, expected_hash: str, label: str) -> None:
    require_digest(expected_hash, f"{label} expected hash")
    if sha256_bytes(data) != expected_hash:
        raise PermissionError(f"{label} hash drift")


@dataclass
class Phase4Broker:
    mission_id: str
    intake_hash: str
    state: str = "INTAKE"
    stage_index: int = 0
    model_transactions: int = 0
    tool_calls: int = 0
    stage_records: list[dict[str, Any]] = field(default_factory=list)
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    mission_launch_approved: bool = False
    build_approved: bool = False

    def __post_init__(self) -> None:
        if not self.mission_id or len(self.mission_id) < 6:
            raise ValueError("mission_id is invalid")
        require_digest(self.intake_hash, "intake_hash")
        self.artifact_hashes["owner_intake"] = self.intake_hash

    def approve_launch(self) -> None:
        if self.state != "INTAKE" or self.stage_records:
            raise PermissionError("Mission launch approval must precede Atlas")
        self.mission_launch_approved = True

    def advance(
        self,
        stage: str,
        actor: str,
        input_hashes: dict[str, str],
        output_hash: str | None,
        *,
        runtime_tool_calls: int = 0,
        owner_build_approval: bool = False,
        model_transaction: bool = True,
    ) -> None:
        if not self.mission_launch_approved:
            raise PermissionError("Mission launch is not approved")
        if self.stage_index >= len(SEQUENCE):
            raise PermissionError("Mission is already terminal")
        expected_stage, expected_actor = SEQUENCE[self.stage_index]
        if (stage, actor) != (expected_stage, expected_actor):
            raise PermissionError(
                f"Illegal transition: expected {expected_stage}/{expected_actor}, received {stage}/{actor}"
            )
        if runtime_tool_calls != 0:
            raise PermissionError(f"{stage} recorded nonzero tool calls")
        for key, value in input_hashes.items():
            require_digest(value, f"{stage}.{key}")
        if output_hash is not None:
            require_digest(output_hash, f"{stage}.output")

        if stage == "OWNER_BUILD_DECISION":
            if not owner_build_approval:
                raise PermissionError("Rob's explicit contained-build approval is absent")
            self.build_approved = True
        elif owner_build_approval:
            raise PermissionError("Build approval can only be recorded at OWNER_BUILD_DECISION")
        if stage in {"MASON_PLAN", "DETERMINISTIC_BUILD", "VERA_BUILD_REVIEW", "DRAFT_READY"} and not self.build_approved:
            raise PermissionError(f"{stage} cannot run before Rob's build approval")

        if actor in MODEL_ACTORS and model_transaction:
            self.model_transactions += 1
        self.tool_calls += runtime_tool_calls
        self.stage_records.append(
            {
                "stage": stage,
                "actor": actor,
                "input_hashes": dict(sorted(input_hashes.items())),
                "output_hash": output_hash,
                "status": "COMPLETE",
            }
        )
        if output_hash is not None:
            self.artifact_hashes[stage.lower()] = output_hash
        self.state = stage
        self.stage_index += 1

    def candidate_path(self, candidate_root: Path, requested: Path) -> Path:
        if not self.build_approved:
            raise PermissionError("Candidate writes require Rob's build approval")
        return require_within(requested, candidate_root, "candidate write")

    def record(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "mission_id": self.mission_id,
            "governed_run_marker": MARKER,
            "mode": MODE,
            "state": self.state,
            "stage_records": self.stage_records,
            "artifact_hashes": dict(sorted(self.artifact_hashes.items())),
            "model_transactions": self.model_transactions,
            "tool_calls": self.tool_calls,
            "owner_gates": {
                "mission_launch_approved": self.mission_launch_approved,
                "build_approved": self.build_approved,
                "release_approved": False,
            },
            "authority": {
                "contained_draft": True,
                "live_factory_write": False,
                "installation": False,
                "deployment": False,
                "production": False,
            },
        }
