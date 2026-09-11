"""Verify the Phase 1 control-plane contract adoption and bridge."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from x_factory.control_plane_package_v0_1 import (
    SCHEMA_ROOT,
    export_package_draft,
    prepare_preview_release_record,
    promote_package_draft,
    validate_envelope,
    validate_package_draft,
    verify_preview_release_record,
)


def main() -> None:
    expected = {
        "accepted-package-draft.schema.json": "9ce54651f38c9794bae95fe8e306353a13dd9bf72e02f200c7fe9f2b5fc27c56",
        "accepted-package.schema.json": "30de467d21483df6e32d1dd62af8f6c91398683ead0f84d054d9ef3e503a6a24",
        "release-record.schema.json": "86282b1cc27f090737418c6ad32bca4a4ca05182966b06470f4ac97e40e193d4",
        "registry-snapshot.v1.schema.json": "ad99c52794ee50278ea5ec1e7d3293a516529c267035f8d9a74075b87361952d",
        "production-promotion-plan.v1.schema.json": "eba30fd478180476770b09bd02b215227b1a667d8ef7d94674669f71582e682f",
    }
    for filename, digest in expected.items():
        assert SCHEMA_ROOT.joinpath(filename).read_bytes()
        import hashlib
        assert hashlib.sha256(SCHEMA_ROOT.joinpath(filename).read_bytes()).hexdigest() == digest
    manifest = json.loads((SCHEMA_ROOT / "adoption-manifest.v1.json").read_text(encoding="utf-8"))
    assert manifest["adopted_without_execution_authority"] is True
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for filename in ("accepted-package-draft.schema.json", "accepted-package.schema.json", "release-record.schema.json"):
            assert json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8"))["additionalProperties"] is False
        files = {
            "instance/system-prompt/SYSTEM_PROMPT.md": b"reviewed prompt",
            "instance/knowledge/approved-knowledge.v0.1.json": b'{"entries":[]}',
            "runtime-foundry/instance-runtime-contract.v0.1.json": b'{"status":"locked"}',
            "input/text-runtime-candidate.v0.1.json": b'{"candidate_sha256":"' + b"a" * 64 + b'"}',
            "runtime-foundry/local-behavior-certification.v0.1.json": b'{"status":"pass"}',
            "input/prepared-agent-binding.v0.1.json": b'{"project_id":"project-"' + b"a" * 24 + b'"}',
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        result = export_package_draft(
            {"project_id": "project-" + "a" * 24, "mission_id": "draft-phase1-fixture-1234",
             "revision_sha256": "b" * 64, "fields": {"x_agent_name": "Fixture"}},
            root,
            {"package_sha256": "c" * 64},
        )
        assert result["status"] == "PENDING_EVALUATION_AND_OWNER_ACCEPTANCE"
        draft_path = root / result["path"]
        validate_package_draft(draft_path, root)
        try:
            promote_package_draft(draft_path, root, evaluation={
                "evaluated_content_sha256": "d" * 64, "verdict": "pass",
                "evidence": {"path": "runtime-foundry/local-behavior-certification.v0.1.json", "sha256": "e" * 64}},
                accepted_by="Rob", accepted_at="2026-09-10T12:00:00Z")
        except ValueError:
            pass
        else:
            raise AssertionError("mismatched evaluation must be rejected")
        manifest_hash = __import__("hashlib").sha256((root / "input/control-plane/accepted-package-content.v1.json").read_bytes()).hexdigest()
        evidence_path = root / "runtime-foundry/evaluation-pass.json"
        evidence_path.write_bytes(b'{"verdict":"pass"}')
        accepted = promote_package_draft(draft_path, root, evaluation={
            "evaluated_content_sha256": manifest_hash, "verdict": "pass",
            "evidence": {"path": "runtime-foundry/evaluation-pass.json",
                         "sha256": __import__("hashlib").sha256(evidence_path.read_bytes()).hexdigest()}},
            accepted_by="Rob", accepted_at="2026-09-10T12:00:00Z")
        assert accepted["status"] == "ACCEPTED"
        accepted_value = json.loads((root / accepted["path"]).read_text(encoding="utf-8"))
        validate_envelope("accepted_package", accepted_value)
        for relative, content in {
            "runtime-foundry/anam-intended-config.json": b'{"mode":"session_config"}',
            "runtime-foundry/dependencies.json": b'{"runtime":"frozen"}',
            "runtime-foundry/rollback.md": b"Restore the previous local preview record.",
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        release = prepare_preview_release_record(
            root / accepted["path"], root, release_id="release-fixture-001",
            recorded_at="2026-09-10T12:01:00Z", url="http://127.0.0.1:8877/",
            application_repository="repos/local/fixture", application_commit_sha="f" * 40,
            anam_intended_config="runtime-foundry/anam-intended-config.json",
            dependencies="runtime-foundry/dependencies.json",
            rollback_procedure="runtime-foundry/rollback.md",
        )
        assert release["status"] == "PREVIEW_PREPARED"
        release_value = json.loads((root / release["path"]).read_text(encoding="utf-8"))
        validate_envelope("release_record", release_value)
        assert release_value["environment"] == "preview"
        assert release_value["verification"]["status"] == "pending"
        for relative, content in {
            "runtime-foundry/anam-observed-config.json": b'{"mode":"session_config","observed":true}',
            "runtime-foundry/verification-evidence.json": b'{"checks":["identity","prompt","knowledge","fresh-session"]}',
            "runtime-foundry/rollback-test-evidence.json": b'{"rollback":"passed"}',
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        verified = verify_preview_release_record(
            root / release["path"], root,
            observed_config="runtime-foundry/anam-observed-config.json",
            observed_at="2026-09-10T12:02:00Z", verified_at="2026-09-10T12:03:00Z",
            verification_evidence="runtime-foundry/verification-evidence.json",
            rollback_test_evidence="runtime-foundry/rollback-test-evidence.json",
            deployment_id="local-preview-fixture-001",
        )
        assert verified["status"] == "PREVIEW_VERIFIED"
        verified_value = json.loads((root / verified["path"]).read_text(encoding="utf-8"))
        validate_envelope("release_record", verified_value)
        assert verified_value["status"] == "verified"
        assert verified_value["verification"]["status"] == "passed"
        assert verified_value["rollback"]["test_evidence"] is not None
    print("control-plane contract adoption: PASS")


if __name__ == "__main__":
    main()
