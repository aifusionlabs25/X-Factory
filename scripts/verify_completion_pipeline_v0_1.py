#!/usr/bin/env python3
"""Verify the automatic local finish with a structurally different X-Agent."""

from __future__ import annotations

import json
import secrets
import shutil
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import completion_pipeline_v0_1 as completion  # noqa: E402
from x_factory import independent_review_v0_1 as review  # noqa: E402
from x_factory import mission_control_factory_v0_1 as factory  # noqa: E402
from x_factory import repo_foundry_v0_1 as porter  # noqa: E402


MISSION_ID = "draft-nora-policy-guide-verification"


def main() -> int:
    verification_root = ROOT / "verification" / "mission-control" / "tmp"
    verification_root.mkdir(parents=True, exist_ok=True)
    sandbox = verification_root / f"completion-pipeline-{secrets.token_hex(4)}"
    sandbox.mkdir()
    try:
        interactive_root = sandbox / "runs" / "interactive"
        factory.INTERACTIVE_ROOT = interactive_root
        review.INTERACTIVE_ROOT = interactive_root
        review.REVIEW_ROOT = sandbox / "reviews" / "independent-local"
        porter.INTERACTIVE_ROOT = interactive_root
        porter.LOCAL_REPO_ROOT = sandbox / "repos" / "local"
        completion.COMPLETION_ROOT = sandbox / "runs" / "completions"

        mission = factory.create_mission(
            {
                "purpose": "Help employees find approved workplace policy information and prepare a clarification request when the approved material does not answer them.",
                "agent_or_client": "People Operations",
                "x_agent_name": "Nora",
                "client_name": "Apex People Operations",
                "role_title": "Employee Policy Guide",
                "personality": "Calm, neutral, private, and concise",
                "must_accomplish": "Answer only from approved policy material; preserve the employee's question; prepare a structured clarification request",
                "never_do": "Invent policy; provide legal advice; approve leave or benefits; send information externally",
                "target_users": "Employees and People Operations staff",
                "output_artifact": "Structured policy clarification handoff",
                "presence_mode": "TEXT_ONLY",
            },
            mission_id=MISSION_ID,
        )
        first = completion.complete_local_draft(MISSION_ID)
        second = completion.complete_local_draft(MISSION_ID)
        repo = porter.find_local_repo(MISSION_ID)
        independent = review.find_independent_review(MISSION_ID)

        assert first == second
        assert first["status"] == "LOCAL_DRAFT_COMPLETE"
        assert [item["specialist"] for item in first["route"]] == ["Atlas", "Aria", "Vera", "Mason", "Vera", "Rook", "Porter"]
        assert all(item["status"] == "PASS" for item in first["route"])
        assert independent and independent["verdict"] == "READY_FOR_PORTER_PACKAGING"
        assert independent["reviewer"]["provider_calls"] == 0
        assert independent["hermes_review"]["status"] == "PREPARED_NOT_INVOKED"
        assert repo and repo["status"] == "LOCAL_REPO_READY"
        assert repo["verification"]["status"] == "PASS"
        assert repo["display_name"] == "Nora — Employee Policy Guide"
        assert (Path(repo["local_path"]) / "factory-record" / "independent-local-review.json").is_file()
        assert first["authority"] == {
            "provider_calls": 0,
            "network_attempts": 0,
            "credentials_copied": False,
            "existing_repo_mutation": False,
            "deployment": False,
            "production": False,
        }

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "capability": "AUTOMATIC_LOCAL_COMPLETION",
                    "mission_id": mission["mission_id"],
                    "agent": repo["display_name"],
                    "route": [item["specialist"] for item in first["route"]],
                    "review": independent["verdict"],
                    "repo_tests": repo["verification"]["status"],
                    "idempotent": True,
                    "provider_calls": 0,
                    "network_attempts": 0,
                    "deployment": False,
                    "production": False,
                },
                indent=2,
            )
        )
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
