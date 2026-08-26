"""Phase 4.1 fail-closed runner control plane with no provider transport."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .phase4_broker import require_within, sha256_bytes
from .phase4_payloads import canonical, digest
from .phase4_payloads_v0_2 import STAGE_INPUTS_V0_2, make_stage_payload_v0_2


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"
STAGES = tuple(STAGE_INPUTS_V0_2)
SCHEMA_KEYS = {
    "ATLAS_TRIAGE": "atlas_intake",
    "ARIA_BLUEPRINT": "aria_blueprint",
    "VERA_SPEC_REVIEW": "vera_specification_review",
    "MASON_PLAN": "mason_implementation_decision",
    "VERA_BUILD_REVIEW": "vera_build_review",
}
SCHEMA_IDS = {
    "ATLAS_TRIAGE": "intake.v0.1",
    "ARIA_BLUEPRINT": "x_agent_blueprint.v0.1",
    "VERA_SPEC_REVIEW": "evaluation_contract.v0.1",
    "MASON_PLAN": "implementation_decision.v0.1",
    "VERA_BUILD_REVIEW": "build_review.v0.1",
}
REQUIRED_VERDICTS = {
    "VERA_SPEC_REVIEW": ("verdict", "SPECIFICATION_READY_FOR_BUILD"),
    "MASON_PLAN": ("decision", "IMPLEMENTATION_PLAN_READY"),
    "VERA_BUILD_REVIEW": ("verdict", "CONTAINED_DRAFT_READY"),
}
ORIGINS = {
    "ATLAS_TRIAGE": {"owner_intake": "owner_intake"},
    "ARIA_BLUEPRINT": {"normalized_intake": "normalized_intake", "component_catalog": "component_catalog"},
    "VERA_SPEC_REVIEW": {
        "normalized_intake": "normalized_intake",
        "frozen_blueprint": "frozen_blueprint",
        "evidence_index": "evidence_index",
    },
    "MASON_PLAN": {
        "approved_blueprint": "approved_blueprint",
        "generation_contract": "generation_contract",
        "output_contract": "output_contract",
        "acceptance_fixture": "acceptance_fixture",
        "owner_build_approval": "owner_build_approval",
    },
    "VERA_BUILD_REVIEW": {
        "approved_blueprint": "approved_blueprint",
        "mason_plan": "mason_plan",
        "candidate_manifest": "candidate_manifest",
        "test_evidence": "test_evidence",
        "build_record": "build_record",
    },
}
OUTPUT_ALIASES = {
    "ATLAS_TRIAGE": ("normalized_intake",),
    "ARIA_BLUEPRINT": ("frozen_blueprint", "approved_blueprint"),
    "VERA_SPEC_REVIEW": ("specification_verdict",),
    "MASON_PLAN": ("mason_plan",),
    "VERA_BUILD_REVIEW": ("build_review",),
}


def file_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical(value))


@dataclass
class TransactionLedger:
    stages: list[str] = field(default_factory=list)

    def reserve_before_transmission(self, stage: str) -> int:
        if len(self.stages) >= 5:
            raise PermissionError("Maximum model transaction count exceeded")
        if stage in self.stages:
            raise PermissionError(f"Retry prohibited for {stage}")
        expected = STAGES[len(self.stages)]
        if stage != expected:
            raise PermissionError(f"Stage order violation: expected {expected}, received {stage}")
        self.stages.append(stage)
        return len(self.stages)


@dataclass
class DerivationBoundRunnerV02:
    factory_root: Path
    mission_id: str
    manifest: dict[str, Any]
    policy: dict[str, Any]
    manifest_schema: dict[str, Any]
    ledger: TransactionLedger = field(default_factory=TransactionLedger)
    chain: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    artifact_origins: dict[str, str] = field(default_factory=dict)
    terminal_failure: str | None = None
    _baseline: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.factory_root = self.factory_root.resolve()
        errors = list(Draft202012Validator(self.manifest_schema).iter_errors(self.manifest))
        if errors:
            raise PermissionError("Live mission manifest failed schema validation")
        if self.manifest["mission_id"] != self.mission_id:
            raise PermissionError("Mission ID mismatch")
        runtime = self.policy.get("runtime", {})
        if (
            self.policy.get("status") != "DRAFT_NOT_ACTIVE"
            or runtime.get("provider") != "openai-codex"
            or runtime.get("model") != "gpt-5.6-luna"
            or runtime.get("reasoning") != "low"
            or runtime.get("maximum_model_transactions") != 5
            or runtime.get("maximum_transactions_per_stage") != 1
            or runtime.get("retry_authorized") is not False
            or runtime.get("tool_calls_per_stage") != 0
            or runtime.get("oauth_refresh_authorized") is not False
        ):
            raise PermissionError("Runtime policy drift")

    def bind_runtime(
        self,
        *,
        implementation_paths: dict[str, Path],
        schema_paths: dict[str, Path],
        profile_paths: dict[str, Path],
        authentication_paths: dict[str, Path],
        derivation_policy_path: Path,
    ) -> None:
        if set(schema_paths) != set(STAGES):
            raise PermissionError("Stage schema binding set mismatch")
        self._baseline = {
            "implementation_paths": implementation_paths,
            "schema_paths": schema_paths,
            "profile_paths": profile_paths,
            "authentication_paths": authentication_paths,
            "derivation_policy_path": derivation_policy_path,
        }
        self._verify_baseline()

    def _verify_map(self, paths: dict[str, Path], expected: dict[str, str], label: str) -> None:
        if set(paths) != set(expected):
            raise PermissionError(f"{label} binding set mismatch")
        for name, path in paths.items():
            if not path.is_file() or file_digest(path) != expected[name]:
                raise PermissionError(f"{label} drift: {name}")

    def _verify_baseline(self) -> None:
        if self._baseline is None:
            raise PermissionError("Runtime baseline is not bound")
        self._verify_map(self._baseline["implementation_paths"], self.manifest["implementation_hashes"], "implementation")
        stage_schema_hashes = {
            stage: self.manifest["schema_hashes"][SCHEMA_KEYS[stage]] for stage in STAGES
        }
        self._verify_map(self._baseline["schema_paths"], stage_schema_hashes, "schema")
        self._verify_map(self._baseline["profile_paths"], self.manifest["profile_hashes"], "profile")
        self._verify_map(self._baseline["authentication_paths"], self.manifest["authentication_baseline"], "authentication")
        policy_path = self._baseline["derivation_policy_path"]
        if not policy_path.is_file() or file_digest(policy_path) != self.manifest["derivation_policy_sha256"]:
            raise PermissionError("Derivation policy drift")

    def seed_starting_artifact(self, name: str, path: Path) -> None:
        if name not in self.manifest["starting_input_hashes"]:
            raise PermissionError(f"Unapproved starting artifact: {name}")
        if not path.is_file() or file_digest(path) != self.manifest["starting_input_hashes"][name]:
            raise PermissionError(f"Starting artifact drift: {name}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if name == "owner_intake" and value.get("run_id") != self.mission_id:
            raise PermissionError("Owner intake run_id must equal mission_id")
        self.artifacts[name] = value
        self.artifact_origins[name] = f"APPROVED_STARTING_INPUT.{name}"

    def authorize_conditional_build(self) -> None:
        if self.terminal_failure or not self.chain:
            raise PermissionError("Specification approval is absent")
        last = self.chain[-1]
        if last["stage"] != "VERA_SPEC_REVIEW" or last["status"] != "ACCEPTED":
            raise PermissionError("Vera specification approval is absent")
        value = {"decision": "APPROVE_CONTAINED_BUILD", "mission_id": self.mission_id}
        self.artifacts["owner_build_approval"] = value
        self.artifact_origins["owner_build_approval"] = "CONDITIONAL_OWNER_BUILD_AUTHORITY"

    def register_deterministic_artifact(self, name: str, value: Any, evidence_path: Path) -> None:
        if name not in {"candidate_manifest", "test_evidence", "build_record"}:
            raise PermissionError("Unsupported deterministic artifact")
        if self.terminal_failure or "mason_plan" not in self.artifacts:
            raise PermissionError("Mason plan is not accepted")
        mission_root = self.factory_root / "runs" / "contained" / self.mission_id
        require_within(evidence_path, mission_root, "deterministic evidence")
        if not evidence_path.is_file() or json.loads(evidence_path.read_text(encoding="utf-8")) != value:
            raise PermissionError("Deterministic artifact evidence mismatch")
        self.artifacts[name] = value
        self.artifact_origins[name] = f"DETERMINISTIC_OUTPUT.{name}"

    def derive_payload(self, stage: str) -> dict[str, Any]:
        if self.terminal_failure:
            raise PermissionError(f"Mission is terminal: {self.terminal_failure}")
        if stage not in ORIGINS:
            raise PermissionError("Unknown stage")
        artifacts = {}
        for payload_name, registry_name in ORIGINS[stage].items():
            if registry_name not in self.artifacts:
                raise PermissionError(f"Approved origin missing: {registry_name}")
            artifacts[payload_name] = self.artifacts[registry_name]
        return make_stage_payload_v0_2(stage, self.mission_id, artifacts, SCHEMA_IDS[stage])

    def prepare_transmission(self, stage: str) -> dict[str, Any]:
        self._verify_baseline()
        payload = self.derive_payload(stage)
        prompt = (
            "Return only one JSON object that validates against the required output schema. "
            "Do not use tools, MCP, memory, delegation, files, or external actions.\n"
            + canonical(payload).decode("utf-8")
        )
        number = self.ledger.reserve_before_transmission(stage)
        record = {
            "transaction": number,
            "stage": stage,
            "status": "RESERVED_BEFORE_TRANSMISSION",
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "payload_sha256": canonical_digest(payload),
            "output_sha256": None,
            "tool_calls": 0,
            "retry": False,
        }
        self.chain.append(record)
        return {"transaction": number, "stage": stage, "prompt": prompt, "payload": payload}

    def accept_response(self, stage: str, output: dict[str, Any], *, tool_calls: int = 0) -> None:
        if not self.chain or self.chain[-1]["stage"] != stage or self.chain[-1]["status"] != "RESERVED_BEFORE_TRANSMISSION":
            raise PermissionError("No matching reserved transaction")
        record = self.chain[-1]
        try:
            self._verify_baseline()
            if tool_calls != 0:
                raise PermissionError("Tool use is prohibited")
            schema_path = self._baseline["schema_paths"][stage]
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(schema).iter_errors(output))
            if errors:
                raise PermissionError("Stage output failed its bound schema")
            verdict = REQUIRED_VERDICTS.get(stage)
            if verdict and output.get(verdict[0]) != verdict[1]:
                raise PermissionError(f"{stage} required verdict is absent")
            output_identifier = output.get("mission_id", output.get("run_id"))
            if output_identifier is not None and output_identifier != self.mission_id:
                raise PermissionError("Stage output mission identifier mismatch")
            record["output_sha256"] = canonical_digest(output)
            record["status"] = "ACCEPTED"
            for alias in OUTPUT_ALIASES[stage]:
                self.artifacts[alias] = output
                self.artifact_origins[alias] = f"VALIDATED_OUTPUT.{stage}"
            self._verify_baseline()
        except PermissionError as error:
            record["status"] = "FAILED_TERMINAL_SLOT_CONSUMED"
            record["failure"] = str(error)
            self.terminal_failure = f"{stage}: {error}"
            raise

    def record_transport_failure(self, stage: str, reason: str) -> None:
        if not self.chain or self.chain[-1]["stage"] != stage or self.chain[-1]["status"] != "RESERVED_BEFORE_TRANSMISSION":
            raise PermissionError("No matching reserved transaction")
        self.chain[-1]["status"] = "FAILED_TERMINAL_SLOT_CONSUMED"
        self.chain[-1]["failure"] = reason
        self.terminal_failure = f"{stage}: {reason}"

    def contained_path(self, requested: Path) -> Path:
        return require_within(requested, self.factory_root / "runs" / "contained" / self.mission_id, "mission write")

    def execution_preview(self) -> dict[str, Any]:
        return {
            "schema_version": "0.2",
            "status": STATUS,
            "mission_id": self.mission_id,
            "provider_transport_present": False,
            "transactions_reserved": len(self.ledger.stages),
            "terminal_failure": self.terminal_failure,
            "hash_chain": self.chain,
        }

    def execute(self) -> None:
        raise PermissionError("Provider transport is absent and mission activation is not authorized")
