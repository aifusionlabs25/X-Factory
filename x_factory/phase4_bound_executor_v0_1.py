"""Transaction-bound Phase 4 executor.

The default path launches a subprocess, but the module is inert until called by
a separately approved mission. Offline launch injection is restricted to test
mission identifiers and cannot be used for a live mission id.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .phase4_broker import require_within, sha256_bytes
from .phase4_live_runner_v0_4 import (
    _BOUND_EXECUTOR_CAPABILITY,
    DerivationBoundRunnerV04,
)


PROFILE_BY_STAGE = {
    "ATLAS_TRIAGE": "atlas",
    "ARIA_BLUEPRINT": "aria",
    "VERA_SPEC_REVIEW": "vera",
    "MASON_PLAN": "mason",
    "VERA_BUILD_REVIEW": "vera",
}


def _atomic_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".next")
    if path.exists() or temporary.exists():
        raise PermissionError(f"Executor output path must be new: {path.name}")
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass
class BoundStageExecutorV01:
    runner: DerivationBoundRunnerV04
    bridge_path: Path
    offline_launcher: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        self.bridge_path = self.bridge_path.resolve(strict=True)
        expected = self.runner.manifest["implementation_hashes"].get("transaction_bound_bridge")
        if expected is None or sha256_bytes(self.bridge_path.read_bytes()) != expected:
            raise PermissionError("Transaction-bound bridge hash mismatch")
        if self.offline_launcher is not None and not self.runner.mission_id.startswith("phase4-v04-offline-"):
            raise PermissionError("Offline launcher injection is prohibited for non-test missions")

    def _launch(self, command: list[str], mission_root: Path) -> Any:
        if self.offline_launcher is not None:
            return self.offline_launcher(command, cwd=mission_root)
        return subprocess.run(
            command,
            cwd=mission_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=300,
        )

    def execute_stage(self, stage: str) -> dict[str, Any]:
        envelope = self.runner.prepare_transmission(stage)
        transaction = envelope["transaction"]
        mission_root = self.runner.factory_root / "runs" / "contained" / self.runner.mission_id
        control_root = mission_root / "control"
        prompt_path = require_within(
            control_root / f"transaction-{transaction:02d}.prompt.txt", control_root, "prompt path"
        )
        evidence_path = require_within(
            control_root / f"transaction-{transaction:02d}.bridge-evidence.json", control_root, "evidence path"
        )
        prompt_bytes = envelope["prompt"].encode("utf-8")
        prompt_hash = sha256_bytes(prompt_bytes)
        payload_hash = self.runner.chain[-1]["payload_sha256"]
        bridge_hash = sha256_bytes(self.bridge_path.read_bytes())

        try:
            if prompt_hash != self.runner.chain[-1]["prompt_sha256"]:
                raise PermissionError("Reserved prompt hash mismatch")
            _atomic_bytes(prompt_path, prompt_bytes)
            command = [
                sys.executable,
                str(self.bridge_path),
                "--profile", PROFILE_BY_STAGE[stage],
                "--mission-id", self.runner.mission_id,
                "--transaction", str(transaction),
                "--stage", stage,
                "--mission-root", str(mission_root),
                "--prompt-file", str(prompt_path),
                "--prompt-sha256", prompt_hash,
                "--payload-sha256", payload_hash,
                "--bridge-sha256", bridge_hash,
                "--evidence-file", str(evidence_path),
            ]
            self.runner._verify_baseline()
            process = self._launch(command, mission_root)
            if not evidence_path.is_file():
                raise PermissionError("Bound bridge did not produce execution evidence")
            evidence_bytes = evidence_path.read_bytes()
            execution = json.loads(evidence_bytes.decode("utf-8"))
            if getattr(process, "returncode", None) != execution.get("exit_code"):
                raise PermissionError("Subprocess and evidence exit codes disagree")
            if bytes(getattr(process, "stdout", b"")) or bytes(getattr(process, "stderr", b"")):
                raise PermissionError("Unexpected output escaped the bound bridge evidence channel")
            expected_fields = {
                "mission_id": self.runner.mission_id,
                "transaction": transaction,
                "stage": stage,
                "profile": PROFILE_BY_STAGE[stage],
                "prompt_sha256": prompt_hash,
                "payload_sha256": payload_hash,
                "bridge_sha256": bridge_hash,
            }
            for name, expected in expected_fields.items():
                if execution.get(name) != expected:
                    raise PermissionError(f"Execution evidence mismatch: {name}")
            stdout_bytes = base64.b64decode(execution["stdout_base64"], validate=True)
            stderr_bytes = base64.b64decode(execution["stderr_base64"], validate=True)
            if sha256_bytes(stdout_bytes) != execution.get("stdout_sha256"):
                raise PermissionError("Captured stdout hash mismatch")
            if sha256_bytes(stderr_bytes) != execution.get("stderr_sha256"):
                raise PermissionError("Captured stderr hash mismatch")
            output = json.loads(stdout_bytes.decode("utf-8").strip())
            if not isinstance(output, dict):
                raise PermissionError("Hermes output must be exactly one JSON object")
            self.runner._accept_bound_execution(
                stage,
                output,
                execution=execution,
                execution_sha256=sha256_bytes(evidence_bytes),
                capability=_BOUND_EXECUTOR_CAPABILITY,
            )
            return output
        except Exception as error:
            if self.runner.chain and self.runner.chain[-1].get("status") == "RESERVED_BEFORE_TRANSMISSION":
                self.runner.record_transport_failure(stage, str(error))
            raise
