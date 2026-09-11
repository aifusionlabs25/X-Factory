"""Verify the final locked production-promotion gate."""
from __future__ import annotations

import json
import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from x_factory.control_plane_package_v0_1 import (  # noqa: E402
    prepare_production_promotion_plan,
    preflight_production_promotion,
    validate_envelope,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contents = {
            "input/control-plane/accepted-package.v1.json": b"accepted",
            "runtime/anam.json": b"anam",
            "runtime/anam-observed.json": b"observed",
            "runtime/deps.json": b"deps",
            "runtime/verification.json": b"verification",
            "runtime/rollback.md": b"rollback",
            "runtime/rollback-test.json": b"rollback-test",
            "owner-approval.txt": b"Rob approved this contained promotion plan for review.",
        }
        for relative, content in contents.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        def ref(relative: str) -> dict[str, str]:
            return {"path": relative, "sha256": hashlib.sha256(contents[relative]).hexdigest()}
        release = {
            "schema_version": "1.0.0", "kind": "release_record", "release_id": "preview-001",
            "agent_id": "fixture", "instance_id": "xi-fixture", "environment": "preview",
            "status": "verified", "recorded_at": "2026-09-10T12:00:00Z",
            "accepted_package": {"package_id": "apd-fixture", "manifest": ref("input/control-plane/accepted-package.v1.json")},
            "anam": {"mode": "session_config", "persona_id": None, "intended_config": ref("runtime/anam.json"),
                     "observed_config": ref("runtime/anam-observed.json"), "observed_at": "2026-09-10T12:01:00Z"},
            "application": {"repository": "repo", "commit_sha": "d" * 40, "deployment_id": "local-preview"},
            "url": "http://127.0.0.1:8877/", "dependencies": ref("runtime/deps.json"),
            "verification": {"status": "passed", "verified_at": "2026-09-10T12:02:00Z", "evidence": ref("runtime/verification.json")},
            "production_approval": None,
            "rollback": {"target_record_id": None, "procedure": ref("runtime/rollback.md"), "test_evidence": ref("runtime/rollback-test.json")},
        }
        verified_path = root / "input/control-plane/release-record.preview.verified.v1.json"
        verified_path.write_text(json.dumps(release), encoding="utf-8")
        validate_envelope("release_record", release)
        plan = prepare_production_promotion_plan(
            verified_path, root, plan_id="promotion-001", production_url="https://example.invalid/",
            production_repository="repo", production_commit_sha="a" * 40,
            approval_receipt="owner-approval.txt", approved_at="2026-09-10T12:05:00Z",
            rollback_procedure="runtime/rollback.md")
        assert plan["status"] == "READY_FOR_EXPLICIT_EXECUTION"
        plan_value = json.loads((root / plan["path"]).read_text(encoding="utf-8"))
        assert plan_value["execution"] == {"authorized": False, "provider_actions": 0}
        preflight = preflight_production_promotion(root / plan["path"], root)
        assert preflight["status"] == "BLOCKED_EXPLICIT_EXECUTION_REQUIRED"
        try:
            preflight_production_promotion(root / plan["path"], root, execution_authorized=True)
        except ValueError:
            pass
        else:
            raise AssertionError("the local Factory must never execute production")
    print("production-promotion gate: PASS")


if __name__ == "__main__":
    main()
