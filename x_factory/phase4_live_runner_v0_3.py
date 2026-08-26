"""Phase 4.2 durable, fail-closed control plane with no provider transport."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .phase4_broker import require_within, sha256_bytes
from .phase4_live_runner_v0_2 import (
    ORIGINS,
    OUTPUT_ALIASES,
    REQUIRED_VERDICTS,
    SCHEMA_IDS,
    SCHEMA_KEYS,
    STAGES,
    DerivationBoundRunnerV02,
    canonical_digest,
    file_digest,
)
from .phase4_payloads import canonical
from .phase4_payloads_v0_2 import make_stage_payload_v0_2


STATUS = "INACTIVE_REQUIRES_APPROVED_ACTIVATION"


def _atomic_json(path: Path, value: Any) -> None:
    """Replace a JSON record only after its bytes reach stable storage."""

    path.parent.mkdir(parents=False, exist_ok=True)
    temporary = path.with_name(path.name + ".next")
    if temporary.exists():
        raise PermissionError(f"Ambiguous unfinished ledger write: {temporary.name}")
    data = canonical(value) + b"\n"
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@dataclass
class DurableTransactionLedger:
    path: Path
    mission_id: str
    stages: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path.exists():
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("mission_id") != self.mission_id:
                raise PermissionError("Ledger mission mismatch")
            entries = document.get("entries")
            if not isinstance(entries, list):
                raise PermissionError("Ledger is malformed")
            self.stages = [entry["stage"] for entry in entries]
            if entries and entries[-1].get("status") == "RESERVED_BEFORE_TRANSMISSION":
                raise PermissionError("Unfinished reserved slot blocks restart")

    def persist(self, chain: list[dict[str, Any]]) -> None:
        _atomic_json(
            self.path,
            {
                "schema_version": "0.3",
                "mission_id": self.mission_id,
                "maximum_transactions": 5,
                "entries": chain,
            },
        )

    def reserve_before_transmission(self, stage: str, record: dict[str, Any], chain: list[dict[str, Any]]) -> int:
        if len(self.stages) >= 5:
            raise PermissionError("Maximum model transaction count exceeded")
        if stage in self.stages:
            raise PermissionError(f"Retry prohibited for {stage}")
        expected = STAGES[len(self.stages)]
        if stage != expected:
            raise PermissionError(f"Stage order violation: expected {expected}, received {stage}")
        self.stages.append(stage)
        chain.append(record)
        try:
            self.persist(chain)
        except Exception:
            chain.pop()
            self.stages.pop()
            raise
        return len(self.stages)


@dataclass
class DerivationBoundRunnerV03(DerivationBoundRunnerV02):
    ledger_path: Path | None = None
    ledger: DurableTransactionLedger = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.ledger_path is None:
            raise PermissionError("A durable ledger path is required")
        mission_root = self.factory_root / "runs" / "contained" / self.mission_id
        self.ledger_path = require_within(self.ledger_path, mission_root, "transaction ledger")
        self.ledger = DurableTransactionLedger(self.ledger_path, self.mission_id)

        if "runtime_write_policy" in self.manifest:
            write_policy = self.manifest["runtime_write_policy"]
            if (
                write_policy.get("shared_auth_mutation_authorized") is not False
                or write_policy.get("codex_cli_auth_mutation_authorized") is not False
                or write_policy.get("other_profile_mutation_authorized") is not False
                or write_policy.get("contained_factory_write_only") is not True
            ):
                raise PermissionError("Runtime write policy drift")

    def bind_runtime(
        self,
        *,
        implementation_paths: dict[str, Path],
        schema_paths: dict[str, Path],
        profile_paths: dict[str, Path],
        authentication_paths: dict[str, Path],
        derivation_policy_path: Path,
        hermes_runtime_paths: dict[str, Path] | None = None,
        profile_authentication_paths: dict[str, Path] | None = None,
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
        if "hermes_runtime_hashes" in self.manifest:
            if hermes_runtime_paths is None or profile_authentication_paths is None:
                raise PermissionError("Hermes runtime and profile authentication bindings are required")
            self._baseline["hermes_runtime_paths"] = hermes_runtime_paths
            self._baseline["profile_authentication_paths"] = profile_authentication_paths
        self._verify_baseline()

    def _verify_baseline(self) -> None:
        super()._verify_baseline()
        if "hermes_runtime_hashes" not in self.manifest:
            return
        if "hermes_runtime_paths" not in self._baseline or "profile_authentication_paths" not in self._baseline:
            raise PermissionError("Extended runtime baseline is not bound")
        self._verify_map(
            self._baseline["hermes_runtime_paths"],
            self.manifest["hermes_runtime_hashes"],
            "Hermes runtime",
        )
        paths = self._baseline["profile_authentication_paths"]
        expected = self.manifest["profile_authentication_baseline"]
        if set(paths) != set(expected):
            raise PermissionError("Profile authentication binding set mismatch")
        for name, path in paths.items():
            state = expected[name]
            exists = path.is_file()
            if exists != state["exists"]:
                raise PermissionError(f"Profile authentication presence drift: {name}")
            if exists and file_digest(path) != state["sha256"]:
                raise PermissionError(f"Profile authentication drift: {name}")

    def derive_payload(self, stage: str) -> dict[str, Any]:
        if self.terminal_failure:
            raise PermissionError(f"Mission is terminal: {self.terminal_failure}")
        artifacts: dict[str, Any] = {}
        for payload_name, registry_name in ORIGINS.get(stage, {}).items():
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
        transaction = len(self.ledger.stages) + 1
        record = {
            "transaction": transaction,
            "stage": stage,
            "status": "RESERVED_BEFORE_TRANSMISSION",
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "payload_sha256": canonical_digest(payload),
            "output_sha256": None,
            "raw_evidence": None,
            "physical_requests": None,
            "tool_calls": None,
            "retry": False,
        }
        self.ledger.reserve_before_transmission(stage, record, self.chain)
        return {"transaction": transaction, "stage": stage, "prompt": prompt, "payload": payload}

    def accept_captured_response(
        self,
        stage: str,
        output: dict[str, Any],
        *,
        raw_evidence: dict[str, str],
        physical_requests: int,
        tool_calls: int,
    ) -> None:
        if not self.chain or self.chain[-1]["stage"] != stage or self.chain[-1]["status"] != "RESERVED_BEFORE_TRANSMISSION":
            raise PermissionError("No matching reserved transaction")
        record = self.chain[-1]
        try:
            self._verify_baseline()
            if physical_requests != 1:
                raise PermissionError("Exactly one physical request is required")
            if tool_calls != 0:
                raise PermissionError("Tool use is prohibited")
            if set(raw_evidence) != {"stdout_sha256", "stderr_sha256", "execution_sha256"}:
                raise PermissionError("Captured transport evidence is incomplete")
            if not all(
                isinstance(value, str)
                and value.startswith("sha256:")
                and len(value) == 71
                for value in raw_evidence.values()
            ):
                raise PermissionError("Captured transport evidence digest is malformed")
            schema = json.loads(self._baseline["schema_paths"][stage].read_text(encoding="utf-8"))
            if list(Draft202012Validator(schema).iter_errors(output)):
                raise PermissionError("Stage output failed its bound schema")
            verdict = REQUIRED_VERDICTS.get(stage)
            if verdict and output.get(verdict[0]) != verdict[1]:
                actual = output.get(verdict[0], "<ABSENT>")
                raise PermissionError(
                    f"{stage} required {verdict[0]}={verdict[1]}; received {actual}"
                )
            output_identifier = output.get("mission_id", output.get("run_id"))
            if output_identifier is not None and output_identifier != self.mission_id:
                raise PermissionError("Stage output mission identifier mismatch")

            # Final baseline check precedes every registry mutation.
            self._verify_baseline()
            staged_aliases = {alias: output for alias in OUTPUT_ALIASES[stage]}
            record.update(
                output_sha256=canonical_digest(output),
                raw_evidence=raw_evidence,
                physical_requests=physical_requests,
                tool_calls=tool_calls,
                status="ACCEPTED",
            )
            self.ledger.persist(self.chain)
            for alias, value in staged_aliases.items():
                self.artifacts[alias] = value
                self.artifact_origins[alias] = f"VALIDATED_OUTPUT.{stage}"
        except PermissionError as error:
            record["status"] = "FAILED_TERMINAL_SLOT_CONSUMED"
            record["failure"] = str(error)
            self.terminal_failure = f"{stage}: {error}"
            self.ledger.persist(self.chain)
            raise

    def accept_response(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Caller-asserted response evidence is prohibited; use accept_captured_response")

    def record_transport_failure(self, stage: str, reason: str) -> None:
        super().record_transport_failure(stage, reason)
        self.ledger.persist(self.chain)

    def execution_preview(self) -> dict[str, Any]:
        return {
            "schema_version": "0.3",
            "status": STATUS,
            "mission_id": self.mission_id,
            "provider_transport_present": False,
            "durable_ledger": str(self.ledger_path),
            "transactions_reserved": len(self.ledger.stages),
            "terminal_failure": self.terminal_failure,
            "hash_chain": self.chain,
        }
