from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ALLOWED_HOST = "github.com"
ALLOWED_REPOSITORY_PREFIX = "/NousResearch/hermes-agent/"
CLASSIFICATIONS = {
    "SECURITY",
    "FACTORY_COMPATIBILITY",
    "DESKTOP_EXPERIENCE",
    "ORCHESTRATION",
    "PROVIDER_MODEL",
    "USEFUL_CAPABILITY",
    "NO_FACTORY_IMPACT",
}
FORBIDDEN_KEY_FRAGMENTS = ("token", "secret", "password", "cookie", "authorization", "credential")
MAX_MODEL_CANDIDATES = 50
MAX_MODEL_PAYLOAD_BYTES = 65_536


class ScoutCollectionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ScoutCollectionError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ScoutCollectionError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _reject_sensitive_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ScoutCollectionError(f"credential-like field prohibited at {path}.{key}")
            _reject_sensitive_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_keys(nested, f"{path}[{index}]")


def _validate_source(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise ScoutCollectionError("source must use HTTPS on official GitHub host")
    if not parsed.path.startswith(ALLOWED_REPOSITORY_PREFIX):
        raise ScoutCollectionError("source must belong to NousResearch/hermes-agent")


def classify(title: str, summary: str) -> list[str]:
    text = f"{title} {summary}".lower()
    found: set[str] = set()
    if any(word in text for word in ("security", "cve", "vulnerability", "credential", "oauth", "auth")):
        found.add("SECURITY")
    if any(word in text for word in ("breaking", "schema", "config", "windows update", "provider routing", "compatibility")):
        found.add("FACTORY_COMPATIBILITY")
    if any(word in text for word in ("desktop", "tour", "preview", "activity view", "walkthrough")):
        found.add("DESKTOP_EXPERIENCE")
    if any(word in text for word in ("orchestrat", "run budget", "stall", "agent run", "bot mode", "kanban")):
        found.add("ORCHESTRATION")
    if any(word in text for word in ("provider", "model", "openrouter", "codex", "luna")):
        found.add("PROVIDER_MODEL")
    if any(word in text for word in ("tool", "feature", "support", "fallback", "improve")):
        found.add("USEFUL_CAPABILITY")
    return sorted(found or {"NO_FACTORY_IMPACT"})


def recommended_action(classifications: list[str]) -> str:
    values = set(classifications)
    if values & {"SECURITY", "FACTORY_COMPATIBILITY"}:
        return "REVIEW_REQUIRED"
    if values & {"DESKTOP_EXPERIENCE", "ORCHESTRATION", "PROVIDER_MODEL", "USEFUL_CAPABILITY"}:
        return "TEST"
    return "WATCH"


@dataclass(frozen=True)
class CollectionResult:
    brief: dict[str, Any]
    next_watermark: dict[str, Any]
    model_packet: dict[str, Any] | None


def collect(baseline: dict[str, Any], watermark: dict[str, Any], upstream: dict[str, Any]) -> CollectionResult:
    _reject_sensitive_keys(baseline, "baseline")
    _reject_sensitive_keys(watermark, "watermark")
    _reject_sensitive_keys(upstream, "upstream")
    collected_at = _parse_timestamp(upstream["collected_at"])
    _parse_timestamp(watermark["last_successful_at"])
    seen = set(watermark.get("last_seen_shas", []))
    if any(not isinstance(value, str) or not value for value in seen):
        raise ScoutCollectionError("watermark SHAs must be nonempty strings")

    by_sha: dict[str, dict[str, Any]] = {}
    source_hashes: list[dict[str, str]] = []
    for source in upstream["sources"]:
        _validate_source(source["url"])
        source_hashes.append({"url": source["url"], "sha256": sha256(source)})
        for item in source["items"]:
            required = ("sha", "published_at", "title", "url", "summary")
            if any(key not in item for key in required):
                raise ScoutCollectionError("upstream item missing required field")
            _validate_source(item["url"])
            _parse_timestamp(item["published_at"])
            previous = by_sha.get(item["sha"])
            if previous is not None and canonical_bytes(previous) != canonical_bytes(item):
                raise ScoutCollectionError("same SHA has conflicting upstream metadata")
            by_sha[item["sha"]] = item

    delta = []
    for item in sorted(by_sha.values(), key=lambda value: (value["published_at"], value["sha"])):
        if item["sha"] in seen:
            continue
        classes = classify(item["title"], item["summary"])
        delta.append({
            "sha": item["sha"],
            "published_at": item["published_at"],
            "title": item["title"],
            "url": item["url"],
            "summary": item["summary"],
            "classifications": classes,
            "recommended_action": recommended_action(classes),
        })

    overall = "WATCH"
    if any(item["recommended_action"] == "REVIEW_REQUIRED" for item in delta):
        overall = "REVIEW_REQUIRED"
    elif delta:
        overall = "TEST"
    brief = {
        "schema_version": "0.1",
        "status": "DELTA_READY" if delta else "NO_DELTA",
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "baseline": baseline,
        "baseline_sha256": sha256(baseline),
        "source_hashes": sorted(source_hashes, key=lambda value: value["url"]),
        "delta_count": len(delta),
        "delta": delta,
        "overall_recommended_action": overall,
        "authority": "ADVISORY_ONLY_NO_MUTATION",
    }
    new_seen = sorted(seen | set(by_sha))
    next_watermark = {
        "last_successful_at": brief["collected_at"],
        "last_seen_shas": new_seen,
        "brief_sha256": sha256(brief),
    }
    model_packet = None
    if delta:
        action_rank = {"REVIEW_REQUIRED": 0, "TEST": 1, "WATCH": 2}
        ordered_candidates = sorted(
            delta,
            key=lambda item: (action_rank[item["recommended_action"]], item["published_at"], item["sha"]),
        )[:MAX_MODEL_CANDIDATES]
        action_counts = {
            action: sum(1 for item in delta if item["recommended_action"] == action)
            for action in ("REVIEW_REQUIRED", "TEST", "WATCH")
        }
        payload = {
            "task": "Summarize the deterministic Scout delta without adding facts or taking action.",
            "baseline": baseline,
            "delta_count": len(delta),
            "action_counts": action_counts,
            "candidates": [
                {
                    "sha": item["sha"],
                    "published_at": item["published_at"],
                    "title": item["title"],
                    "url": item["url"],
                    "classifications": item["classifications"],
                    "recommended_action": item["recommended_action"],
                }
                for item in ordered_candidates
            ],
            "omitted_candidate_count": len(delta) - len(ordered_candidates),
            "authority": "ADVISORY_ONLY_NO_TOOLS_NO_MUTATION",
        }
        payload_bytes = canonical_bytes(payload)
        if len(payload_bytes) > MAX_MODEL_PAYLOAD_BYTES:
            raise ScoutCollectionError("compacted model payload exceeded 64 KB bound")
        model_packet = {
            "payload": payload,
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "payload_bytes": len(payload_bytes),
            "maximum_payload_bytes": MAX_MODEL_PAYLOAD_BYTES,
            "transmitted": False,
        }
    return CollectionResult(brief=brief, next_watermark=next_watermark, model_packet=model_packet)


def write_fixture_result(base_root: Path, relative_directory: str, result: CollectionResult) -> Path:
    if Path(relative_directory).is_absolute():
        raise ScoutCollectionError("output directory must be relative")
    root = base_root.resolve()
    target = (root / relative_directory).resolve()
    if target != root and root not in target.parents:
        raise ScoutCollectionError("output directory escapes Scout root")
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "brief": result.brief,
        "next_watermark": result.next_watermark,
        "model_packet": result.model_packet,
    }
    output = target / "scout-fixture-result.v0.1.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output
