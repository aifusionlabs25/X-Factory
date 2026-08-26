"""Immutable, local-only knowledge package ingestion and owner approval."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from x_factory.mission_control_factory_v0_1 import (
    MissionControlError,
    ROOT,
    SECRET_LIKE,
    canonical,
    load_json,
    sha256,
    slugify,
    write_new,
)


KNOWLEDGE_ROOT = ROOT / "knowledge-packages"
MANIFEST_SCHEMA = ROOT / "contracts/knowledge_package_manifest.v0.1.schema.json"
APPROVAL_SCHEMA = ROOT / "contracts/knowledge_package_approval.v0.1.schema.json"
PACKAGE_ID = re.compile(r"^kp-[a-z0-9][a-z0-9-]{2,72}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
ALLOWED_SUFFIXES = {".txt", ".md", ".json", ".csv", ".yaml", ".yml"}
MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}
MAX_FILES = 8
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 512 * 1024


class KnowledgeLoadingError(MissionControlError):
    pass


def _digest_without(value: dict[str, Any], field: str) -> str:
    return sha256(canonical({key: item for key, item in value.items() if key != field}))


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(load_json(MANIFEST_SCHEMA)).validate(manifest)
    source = manifest["authority"]["source"]
    capture = manifest.get("website_capture")
    if source == "OWNER_SUPPLIED_LOCAL_FILES" and (capture is not None or manifest["authority"]["network_calls"] != 0):
        raise KnowledgeLoadingError("Local-file knowledge cannot claim website capture or network activity")
    if source == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE":
        if not capture or manifest["authority"]["network_calls"] < 1:
            raise KnowledgeLoadingError("Website knowledge requires capture provenance and recorded network activity")
        captured_names = {page["stored_name"] for page in capture["pages"]}
        file_names = {item["stored_name"] for item in manifest["files"]}
        if captured_names != file_names:
            raise KnowledgeLoadingError("Website capture provenance does not match the immutable file ledger")
    if _digest_without(manifest, "manifest_sha256") != manifest["manifest_sha256"]:
        raise KnowledgeLoadingError("Knowledge package manifest hash validation failed")
    return manifest


def _validate_approval(approval: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(load_json(APPROVAL_SCHEMA)).validate(approval)
    if _digest_without(approval, "approval_sha256") != approval["approval_sha256"]:
        raise KnowledgeLoadingError("Knowledge package approval hash validation failed")
    return approval


def _package_root(package_id: str) -> Path:
    if not PACKAGE_ID.fullmatch(package_id):
        raise KnowledgeLoadingError("Invalid knowledge package ID")
    return KNOWLEDGE_ROOT / package_id


def _unique_stored_name(name: str, seen: set[str]) -> str:
    candidate = name
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    counter = 2
    while candidate.casefold() in seen:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    seen.add(candidate.casefold())
    return candidate


def ingest_knowledge_package(
    value: Any,
    *,
    authority_source: str = "OWNER_SUPPLIED_LOCAL_FILES",
    network_calls: int = 0,
    website_capture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KnowledgeLoadingError("Knowledge upload must be a JSON object")
    if set(value) != {"label", "files"}:
        raise KnowledgeLoadingError("Knowledge upload accepts only label and files")
    label = re.sub(r"\s+", " ", str(value.get("label") or "")).strip()
    files = value.get("files")
    if len(label) < 2 or len(label) > 120:
        raise KnowledgeLoadingError("Package label must be 2 to 120 characters")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise KnowledgeLoadingError(f"Choose between 1 and {MAX_FILES} text files")

    prepared: list[tuple[str, str, bytes, str]] = []
    seen: set[str] = set()
    total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"name", "content"}:
            raise KnowledgeLoadingError("Each uploaded file needs exactly a name and text content")
        original_name = str(entry.get("name") or "")
        if Path(original_name).name != original_name or not SAFE_NAME.fullmatch(original_name):
            raise KnowledgeLoadingError("File names may contain only letters, numbers, dots, dashes, and underscores")
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise KnowledgeLoadingError("Only TXT, MD, JSON, CSV, YAML, and YML files are accepted in this slice")
        content = entry.get("content")
        if not isinstance(content, str):
            raise KnowledgeLoadingError(f"{original_name} is not readable text")
        data = content.encode("utf-8")
        if not data or len(data) > MAX_FILE_BYTES:
            raise KnowledgeLoadingError(f"{original_name} must contain 1 byte to 256 KB of UTF-8 text")
        if b"\x00" in data:
            raise KnowledgeLoadingError(f"{original_name} appears to be binary")
        if SECRET_LIKE.search(content):
            raise KnowledgeLoadingError(f"{original_name} appears to contain a credential or secret; remove it before upload")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise KnowledgeLoadingError("Knowledge packages are limited to 512 KB total in this slice")
        prepared.append((_unique_stored_name(original_name, seen), original_name, data, MEDIA_TYPES[suffix]))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    package_id = f"kp-{slugify(label, 'knowledge')[:40]}-{stamp}-{secrets.token_hex(3)}"
    root = _package_root(package_id)
    if root.exists():
        raise KnowledgeLoadingError("Knowledge package already exists; overwrite is prohibited")
    root.mkdir(parents=True)
    try:
        file_records = []
        for stored_name, original_name, data, media_type in prepared:
            write_new(root / "files" / stored_name, data)
            file_records.append({
                "stored_name": stored_name,
                "original_name": original_name,
                "media_type": media_type,
                "bytes": len(data),
                "sha256": sha256(data),
            })
        manifest = {
            "schema_version": "0.1",
            "package_id": package_id,
            "label": label,
            "status": "INGESTED_PENDING_OWNER_APPROVAL",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": file_records,
            "total_bytes": total,
            "authority": {
                "source": authority_source,
                "runtime_truth": False,
                "provider_calls": 0,
                "network_calls": network_calls,
                "production_approved": False,
            },
        }
        if website_capture is not None:
            manifest["website_capture"] = website_capture
        manifest["manifest_sha256"] = _digest_without(manifest, "manifest_sha256")
        _validate_manifest(manifest)
        write_new(root / "manifest.v0.1.json", manifest)
        return package_status(package_id)
    except Exception:
        import shutil

        if root.exists():
            shutil.rmtree(root)
        raise


def package_status(package_id: str) -> dict[str, Any]:
    root = _package_root(package_id)
    manifest_path = root / "manifest.v0.1.json"
    if not manifest_path.is_file():
        raise KnowledgeLoadingError("Knowledge package not found")
    manifest = _validate_manifest(load_json(manifest_path))
    for item in manifest["files"]:
        target = root / "files" / item["stored_name"]
        if not target.is_file() or sha256(target.read_bytes()) != item["sha256"]:
            raise KnowledgeLoadingError("Knowledge package file integrity validation failed")
    approval_path = root / "owner-approval.v0.1.json"
    approval = _validate_approval(load_json(approval_path)) if approval_path.is_file() else None
    if approval and approval["manifest_sha256"] != manifest["manifest_sha256"]:
        raise KnowledgeLoadingError("Knowledge approval no longer matches the immutable manifest")
    return {
        **manifest,
        "effective_status": approval["status"] if approval else manifest["status"],
        "approval": approval,
    }


def list_knowledge_packages() -> list[dict[str, Any]]:
    if not KNOWLEDGE_ROOT.is_dir():
        return []
    result = []
    for root in KNOWLEDGE_ROOT.iterdir():
        if not root.is_dir():
            continue
        try:
            result.append(package_status(root.name))
        except (OSError, ValueError, KnowledgeLoadingError):
            continue
    result.sort(key=lambda item: item["created_at"], reverse=True)
    return result


def approve_knowledge_package(package_id: str) -> dict[str, Any]:
    status = package_status(package_id)
    root = _package_root(package_id)
    approval_path = root / "owner-approval.v0.1.json"
    if approval_path.exists():
        return status
    website_source = status["authority"]["source"] == "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE"
    approval = {
        "schema_version": "0.1",
        "package_id": package_id,
        "status": "OWNER_APPROVED_FOR_COMMISSIONING",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": status["manifest_sha256"],
        "owner_attestation": (
            "I explicitly requested this bounded public-website capture and authorize its exact hash-bound files to proceed to deterministic owner review, not runtime truth."
            if website_source
            else "I supplied or reviewed these files and approve their use as bounded commissioning inputs, not compiled runtime truth."
        ),
        "authority": {
            "commissioning_attachment": True,
            "runtime_compilation": False,
            "provider_calls": 0,
            "deployment_authorized": False,
            "production_approved": False,
        },
    }
    approval["approval_sha256"] = _digest_without(approval, "approval_sha256")
    _validate_approval(approval)
    write_new(approval_path, approval)
    return package_status(package_id)


def commissioning_reference(package_id: str) -> dict[str, Any]:
    status = package_status(package_id)
    if status["effective_status"] != "OWNER_APPROVED_FOR_COMMISSIONING" or not status["approval"]:
        raise KnowledgeLoadingError("Select a knowledge package that has been owner-approved for commissioning")
    from x_factory.knowledge_compiler_v0_1 import compilation_summary

    compilation = compilation_summary(package_id)
    if not compilation or compilation["status"] != "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD":
        raise KnowledgeLoadingError("Compile this package and complete the Owner Review Desk before commissioning")
    return {
        "package_id": status["package_id"],
        "label": status["label"],
        "manifest_sha256": status["manifest_sha256"],
        "approval_sha256": status["approval"]["approval_sha256"],
        "status": status["effective_status"],
        "files": len(status["files"]),
        "total_bytes": status["total_bytes"],
        "compilation_id": compilation["compilation_id"],
        "compilation_sha256": compilation["compilation_sha256"],
        "review_id": compilation["review_id"],
        "review_sha256": compilation["review_sha256"],
        "approved_entries": compilation["approved_entries"],
    }
