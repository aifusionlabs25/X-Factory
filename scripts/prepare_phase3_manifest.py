"""Build the deterministic Phase 3 local-integration install manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FACTORY = Path(__file__).resolve().parents[1]
PACKAGE = FACTORY / "install-images" / "phase3-local-integration"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def payload_files() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for top in ("release", "mason-profile"):
        for path in sorted((PACKAGE / top).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(PACKAGE).as_posix()
            rows.append(
                {
                    "path": relative,
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return rows


def main() -> int:
    installer = PACKAGE / "install_phase3.ps1"
    manifest = {
        "schema_version": "0.1",
        "package_id": "phase3-local-integration-controlled-build-004",
        "lifecycle_input": "BUILD_VERIFIED",
        "intended_lifecycle_output": "INSTALLED_LOCAL_NON_PRODUCTION",
        "candidate": {
            "build_id": "controlled-build-004",
            "root_sha256": "sha256:379e7cdd8fab6df6fda8a9fb74d5f5a087effa0562fd5f5f585b8afe07db7e79",
            "build_record_sha256": "sha256:a13f57baa8608a8e1b612cc29f823fcba8e15d68ec75f7a1ef4edb0fd3927b76",
            "phase2_1_evaluation_sha256": "sha256:b726c14a4637865db73cf2354490a2309215189cecf11cbeb638cfc1bebb278d",
            "phase2_1_promotion_validation_sha256": "sha256:896c10cbe4af79a6d79637dc03d8441e6de7282aa057744a0d03e47f31d9861f",
            "phase2_1_run_record_sha256": "sha256:454421aedb3543990c0b2540c9511ac60a76f0544b5a0f5b3e1846d97c766227",
        },
        "release_destination": "C:\\AI Fusion Labs\\X AGENTS\\HERMES_X_FACTORY\\releases\\controlled-build-004",
        "mason_profile_destination": "C:\\Users\\AI Fusion Labs\\AppData\\Local\\hermes\\profiles\\mason",
        "mason_runtime": {
            "provider": "openai-codex",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "tool_policy": "ZERO_TOOLS_NO_MCP_NO_MEMORY_NO_DELEGATION",
            "credential_material_in_package": False,
        },
        "preconditions": [
            "approval record is bound to this exact manifest hash",
            "release destination is absent",
            "Mason profile destination is absent",
            "all package hashes match",
        ],
        "operations": [
            "materialize Mason atomically from the Hermes profile distribution",
            "create only Mason-local empty runtime directories",
            "copy the verified release through a sibling staging directory",
            "verify every staged release file before atomic directory move",
            "write no credentials and make no provider call",
        ],
        "rollback": {
            "on_installer_failure": "remove only destinations newly created by this installer",
            "existing_paths_overwritten": False,
            "user_data_migrated": False,
        },
        "authority": {
            "local_non_production_install": True,
            "mason_profile_install": True,
            "credential_copy": False,
            "provider_call": False,
            "tools_or_mcp": False,
            "deployment": False,
            "production": False,
        },
        "installer_sha256": sha256(installer),
        "payload_files": payload_files(),
    }
    output = PACKAGE / "phase3-install-manifest.json"
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(sha256(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
