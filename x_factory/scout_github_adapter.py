from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .scout_collector import ScoutCollectionError


API_ROOT = "https://api.github.com/repos/NousResearch/hermes-agent"
PUBLIC_COMMITS_URL = "https://github.com/NousResearch/hermes-agent/commits/main"
USER_AGENT = "Hermes-X-Factory-Scout/0.1-read-only"


def _is_official_commits_api_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com":
        return False
    if parsed.path == "/repos/NousResearch/hermes-agent/commits":
        return True
    parts = parsed.path.strip("/").split("/")
    return len(parts) == 3 and parts[0] == "repositories" and parts[1].isdigit() and parts[2] == "commits"


def _next_link(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        if not section.startswith("<") or ">" not in section:
            raise ScoutCollectionError("malformed GitHub pagination link")
        return section[1:section.index(">")]
    return None


def _fetch_json(url: str, timeout_seconds: int) -> tuple[Any, str | None]:
    if not _is_official_commits_api_url(url):
        raise ScoutCollectionError("adapter refused nonofficial GitHub API URL")
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise ScoutCollectionError(f"unexpected GitHub status {response.status}")
            body = response.read(10_000_001)
            if len(body) > 10_000_000:
                raise ScoutCollectionError("GitHub response exceeded 10 MB bound")
            return json.loads(body.decode("utf-8")), response.headers.get("Link")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ScoutCollectionError(f"official GitHub collection failed: {type(exc).__name__}") from exc


def collect_public_commits(
    *,
    now: datetime | None = None,
    minimum_window_hours: int = 24,
    max_pages: int = 20,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since = current - timedelta(hours=minimum_window_hours)
    query = urlencode({"sha": "main", "since": since.isoformat().replace("+00:00", "Z"), "per_page": 100})
    url: str | None = f"{API_ROOT}/commits?{query}"
    commits: list[dict[str, Any]] = []
    pages = 0
    while url is not None:
        if pages >= max_pages:
            raise ScoutCollectionError("pagination exceeded bound; partial result refused")
        payload, link = _fetch_json(url, timeout_seconds)
        if not isinstance(payload, list):
            raise ScoutCollectionError("GitHub commits response was not a list")
        pages += 1
        for entry in payload:
            commit = entry.get("commit", {})
            committer = commit.get("committer") or commit.get("author") or {}
            message = str(commit.get("message", "")).strip()
            if not message:
                raise ScoutCollectionError("GitHub commit omitted message")
            lines = message.splitlines()
            commits.append({
                "sha": entry["sha"],
                "published_at": committer["date"],
                "title": lines[0][:500],
                "url": entry["html_url"],
                "summary": " ".join(line.strip() for line in lines[1:] if line.strip())[:2000] or lines[0][:2000],
            })
        url = _next_link(link)
        if url is not None and not _is_official_commits_api_url(url):
            raise ScoutCollectionError("pagination escaped official GitHub API")

    return {
        "collected_at": current.isoformat().replace("+00:00", "Z"),
        "collection_metadata": {
            "window_start": since.isoformat().replace("+00:00", "Z"),
            "pages": pages,
            "complete": True,
            "authentication_used": False,
        },
        "sources": [{"url": PUBLIC_COMMITS_URL, "items": commits}],
    }
