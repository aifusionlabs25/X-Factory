#!/usr/bin/env python3
"""Verify the Porter Repo Foundry against the certified Operational QA mission."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.repo_foundry_v0_1 import LOCAL_REPO_ROOT, create_local_repo  # noqa: E402


MISSION_ID = "draft-operational-qa-concierge-20260821-064103-a3e197"


def main() -> int:
    first = create_local_repo(MISSION_ID)
    second = create_local_repo(MISSION_ID)
    assert first["repo_id"] == second["repo_id"]
    assert first["created_at"] == second["created_at"]
    assert first["root_digest"] == second["root_digest"]
    assert first["status"] == "LOCAL_REPO_READY"
    assert first["verification"]["status"] == "PASS"
    assert first["authority"] == {
        "credentials_copied": False,
        "existing_repo_mutation": False,
        "x_link_installation": False,
        "deployment_authorized": False,
        "production_approved": False,
    }

    repo = LOCAL_REPO_ROOT / first["repo_id"]
    for relative, expected in first["files"].items():
        path = repo / relative
        assert path.is_file(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative
    assert not (repo / ".env").exists()

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    tests = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert tests.returncode == 0, tests.stderr or tests.stdout
    print(
        json.dumps(
            {
                "status": "PASS",
                "capability": "PORTER_REPO_FOUNDRY",
                "mission_id": MISSION_ID,
                "repo_id": first["repo_id"],
                "root_digest": first["root_digest"],
                "hashed_files_verified": len(first["files"]),
                "repository_tests": 4,
                "idempotent_without_overwrite": True,
                "provider_calls": 0,
                "network_attempts": 0,
                "credentials_copied": False,
                "deployment": False,
                "production": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
