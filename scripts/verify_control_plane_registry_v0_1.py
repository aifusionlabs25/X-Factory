"""Verify the read-only Factory registry projection."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from x_factory.control_plane_registry_v0_1 import registry_snapshot  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        # Path arithmetic is intentionally explicit to avoid globbing outside the fixture.
        prepared = root / "drafts" / "prepared-agents" / ("project-" + "a" * 24)
        revisions = prepared / "revisions"
        revisions.mkdir(parents=True)
        value = {"schema_version": "factory.prepared-agent.v0.1", "project_id": prepared.name,
                 "status": "BUILT", "mission_id": "draft-registry-fixture-001", "revision": 1,
                 "fields": {"x_agent_name": "Registry Fixture"}}
        from x_factory.mission_control_factory_v0_1 import canonical, sha256
        value["updated_at"] = "2026-09-10T12:00:00Z"
        value["revision_sha256"] = sha256(canonical(value))
        (revisions / "00001.json").write_text(json.dumps(value), encoding="utf-8")
        candidate = root / "runs" / "interactive" / value["mission_id"] / "input" / "control-plane"
        candidate.mkdir(parents=True)
        package = {"kind": "accepted_package_draft", "agent_id": "fixture", "instance_id": "xi-fixture"}
        (candidate / "accepted-package-draft.v1.json").write_text(json.dumps(package), encoding="utf-8")
        snapshot = registry_snapshot(prepared_root=root / "drafts" / "prepared-agents", interactive_root=root / "runs" / "interactive")
        assert snapshot["kind"] == "factory_registry_snapshot"
        assert len(snapshot["entries"]) == 1
        assert snapshot["entries"][0]["current_lane"] == "PACKAGE_DRAFT"
    print("control-plane registry: PASS")


if __name__ == "__main__":
    main()
