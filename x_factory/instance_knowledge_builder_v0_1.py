"""Build a named candidate's local knowledge core from an exact owner review."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.knowledge_compiler_v0_1 import KnowledgeCompilerError, get_compilation
from x_factory.knowledge_studio_v0_1 import compile_knowledge_studio
from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256, slugify, write_new
from x_factory.prompt_forge_v0_1 import _system_prompt, compile_prompt_package


BUNDLE_SCHEMA = ROOT / "contracts/instance_knowledge_bundle.v0.1.schema.json"
REPORT_SCHEMA = ROOT / "contracts/instance_knowledge_build_report.v0.1.schema.json"


class InstanceKnowledgeBuildError(RuntimeError):
    pass


def _digest_without(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _validate_reference(reference: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    try:
        compilation = get_compilation(reference["package_id"], reference["compilation_id"])
    except (KeyError, KnowledgeCompilerError) as error:
        raise InstanceKnowledgeBuildError(f"Knowledge source binding failed: {error}") from error
    review = compilation.get("latest_review")
    if not review or review.get("status") != "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD":
        raise InstanceKnowledgeBuildError("A completed owner review with approved entries is required")
    bindings = {
        "manifest_sha256": compilation["source_manifest_sha256"],
        "compilation_sha256": compilation["compilation_sha256"],
        "review_id": review["review_id"],
        "review_sha256": review["review_sha256"],
    }
    for field, actual in bindings.items():
        if reference.get(field) != actual:
            raise InstanceKnowledgeBuildError(f"Knowledge {field} drifted before instance build")
    approved_ids = {item["entry_id"] for item in review["decisions"] if item["decision"] == "APPROVE"}
    entries = [deepcopy(item) for item in compilation["entries"] if item["entry_id"] in approved_ids]
    if len(entries) != review["approved_count"] or not entries:
        raise InstanceKnowledgeBuildError("Approved knowledge entry count failed closed")
    return compilation, review, entries


def _knowledge_markdown(identity: dict[str, str], entries: list[dict[str, Any]], *, source_vault: bool = False) -> tuple[str, dict[str, dict[str, int]]]:
    lines = [
        f"# {identity['agent_name']} — {'Immutable Source Vault' if source_vault else 'Curated Knowledge Bank'}",
        "",
        f"Client: {identity['client_name']}",
        f"Role: {identity['role_title']}",
        "",
        "> LOCAL CANDIDATE KNOWLEDGE. Owner-reviewed and source-linked. Not deployed or production-approved.",
        "",
    ]
    anchors: dict[str, dict[str, int]] = {}
    for entry in entries:
        start = len(lines) + 1
        lines.extend([
            f"## [{entry['entry_id']}] {entry['title']}",
            "",
            f"**Type:** {entry['kind']}",
            "",
            entry["statement"],
            "",
            f"**Source:** `{entry['source']['file']}` lines {entry['source']['line_start']}–{entry['source']['line_end']} · SHA-256 `{entry['source']['file_sha256']}`",
            "",
        ])
        anchors[entry["entry_id"]] = {"line_start": start, "line_end": len(lines) - 1}
    return "\n".join(lines).rstrip() + "\n", anchors


def build_instance_knowledge(mission_root: Path, mission_id: str, brief: dict[str, Any]) -> dict[str, Any]:
    reference = brief.get("knowledge_package")
    if not reference:
        raise InstanceKnowledgeBuildError("No reviewed knowledge package is attached")
    compilation, review, entries = _validate_reference(reference)
    identity = {"agent_name": brief["agent_name"], "role_title": brief["role_title"], "client_name": brief["client_name"]}
    bundle = {
        "schema_version": "0.1",
        "bundle_id": f"ikb-{slugify(brief['display_name'])}-{review['review_id'][-6:]}",
        "mission_id": mission_id,
        "status": "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED",
        "identity": identity,
        "source_binding": {
            "package_id": reference["package_id"],
            "manifest_sha256": reference["manifest_sha256"],
            "approval_sha256": reference["approval_sha256"],
            "compilation_id": compilation["compilation_id"],
            "compilation_sha256": compilation["compilation_sha256"],
            "review_id": review["review_id"],
            "review_sha256": review["review_sha256"],
        },
        "entries": [{key: deepcopy(item[key]) for key in ("entry_id", "kind", "title", "statement", "source")} for item in entries],
        "authority": {"owner_reviewed": True, "local_runtime_candidate": True, "runtime_installed": False, "provider_calls": 0, "deployment_authorized": False, "production_approved": False},
    }
    bundle["bundle_sha256"] = _digest_without(bundle, "bundle_sha256")
    Draft202012Validator(load_json(BUNDLE_SCHEMA)).validate(bundle)

    source_vault_markdown, source_anchors = _knowledge_markdown(identity, entries, source_vault=True)
    knowledge_studio = compile_knowledge_studio(bundle, mission_id, preserve_reviewed=bool(brief.get('prepared_agent')))
    curated_entries = knowledge_studio["entries"]
    kb_markdown, anchors = _knowledge_markdown(identity, curated_entries)
    prompt_package = compile_prompt_package(brief, curated_entries, mission_id)
    system_prompt = prompt_package["prompt"]
    traceability = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "bundle_sha256": bundle["bundle_sha256"],
        "entries": [
            {
                "entry_id": item["entry_id"],
                "source": item["source"],
                "source_entry_ids": item["source_entry_ids"],
                "source_statement_sha256": item["source_statement_sha256"],
                "transformation": item["transformation"],
                "knowledge_bank": {"file": "knowledge/KB.md", **anchors[item["entry_id"]]},
                "source_vault": {"file": "knowledge/SOURCE_VAULT.md", **source_anchors[item["entry_id"]]},
                "system_prompt_marker": f"[{item['entry_id']}]",
            }
            for item in curated_entries
        ],
    }
    checks = []
    for item in curated_entries:
        source_item = next(entry for entry in entries if entry["entry_id"] == item["entry_id"])
        checks.append({
            "test_id": f"T-{item['entry_id']}",
            "entry_id": item["entry_id"],
            "statement_exact_in_kb": item["statement"] in kb_markdown,
            "source_statement_exact_in_vault": source_item["statement"] in source_vault_markdown,
            "entry_marker_in_system_prompt": f"[{item['entry_id']}]" in system_prompt,
            "source_hash_preserved": item["source"]["file_sha256"] == source_item["source"]["file_sha256"],
            "curated_answer_traceable": item["source_statement_sha256"] == sha256(" ".join(source_item["statement"].split()).encode("utf-8")),
        })
    test_pack = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "status": "PASS" if all(all(value for key, value in item.items() if key not in {"test_id", "entry_id"}) for item in checks) else "FAIL",
        "checks": checks,
        "unsupported_question_expected_behavior": "STATE_UNKNOWN_AND_PREPARE_HUMAN_REVIEW",
        "provider_calls": 0,
    }
    if test_pack["status"] != "PASS":
        raise InstanceKnowledgeBuildError("Instance knowledge tests failed before any artifact was accepted")

    relative_artifacts = {
        "instance_knowledge_bundle": "instance/knowledge/approved-knowledge.v0.1.json",
        "instance_knowledge_bank": "instance/knowledge/KB.md",
        "instance_source_vault": "instance/knowledge/SOURCE_VAULT.md",
        "instance_traceability": "instance/traceability/knowledge-traceability.v0.1.json",
        "instance_knowledge_tests": "instance/tests/knowledge-tests.v0.1.json",
        **knowledge_studio["artifacts"],
        **prompt_package["artifacts"],
    }
    values: dict[str, bytes] = {
        relative_artifacts["instance_knowledge_bundle"]: canonical(bundle),
        relative_artifacts["instance_knowledge_bank"]: kb_markdown.encode("utf-8"),
        relative_artifacts["instance_source_vault"]: source_vault_markdown.encode("utf-8"),
        relative_artifacts["instance_traceability"]: canonical(traceability),
        relative_artifacts["instance_knowledge_tests"]: canonical(test_pack),
        **knowledge_studio["values"],
        **prompt_package["values"],
    }
    artifact_hashes = {path: sha256(data) for path, data in values.items()}
    report = {
        "schema_version": "0.1",
        "mission_id": mission_id,
        "status": "INSTANCE_KNOWLEDGE_BUILD_PASS",
        "bundle_sha256": bundle["bundle_sha256"],
        "entry_count": len(entries),
        "artifacts": artifact_hashes,
        "verification": {"status": "PASS", "checks": len(checks), "failed": 0},
        "authority": {"provider_calls": 0, "network_calls": 0, "runtime_installed": False, "deployment_authorized": False, "production_approved": False},
    }
    report["report_sha256"] = _digest_without(report, "report_sha256")
    Draft202012Validator(load_json(REPORT_SCHEMA)).validate(report)
    relative_artifacts["instance_knowledge_report"] = "instance/instance-knowledge-build-report.v0.1.json"
    values[relative_artifacts["instance_knowledge_report"]] = canonical(report)

    for relative, data in values.items():
        target = mission_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise InstanceKnowledgeBuildError(f"Instance artifact already exists: {relative}")
        target.write_bytes(data)
    return {
        "status": "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED",
        "entry_count": len(entries),
        "bundle_sha256": bundle["bundle_sha256"],
        "report_sha256": report["report_sha256"],
        "verification": "PASS",
        "runtime_installed": False,
        "prompt_forge": {
            "specialist": "Troy",
            "status": prompt_package["status"],
            "package_sha256": prompt_package["package_sha256"],
            "system_prompt_sha256": prompt_package["system_prompt_sha256"],
        },
        "knowledge_studio": {
            "specialist": "OMNARA",
            "status": knowledge_studio["status"],
            "package_sha256": knowledge_studio["package_sha256"],
            "entry_count": knowledge_studio["entry_count"],
        },
        "artifacts": relative_artifacts,
    }
