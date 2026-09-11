"""Explicit, bounded website capture for owner-reviewed X-Agent knowledge."""

from __future__ import annotations

import ipaddress
import re
import socket
import zlib
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from x_factory.knowledge_loading_v0_1 import KnowledgeLoadingError, ingest_knowledge_package
from x_factory.mission_control_factory_v0_1 import sha256, slugify


MAX_PAGES = 6
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGE_TEXT = 48 * 1024
MAX_REDIRECTS = 3
USER_AGENT = "AI-Fusion-Labs-X-Factory-Website-Capture/0.1"
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain"}


class WebsiteCaptureError(KnowledgeLoadingError):
    def __init__(self, message: str, *, http_status: int | None = None, network_calls: int = 0) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.network_calls = network_calls


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


class _ReadablePage(HTMLParser):
    BLOCK_TAGS = {"a", "article", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "main", "p", "section", "span", "td", "th"}
    SKIP_TAGS = {"button", "footer", "form", "nav", "noscript", "script", "style", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._title = False
        self._heading_level = 0
        self.title_parts: list[str] = []
        self.parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag == "a":
            href = next((value for key, value in attrs if key.casefold() == "href"), None)
            if href:
                self.links.append(href)
        if tag in self.SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "title":
            self._title = True
        if re.fullmatch(r"h[1-6]", tag):
            self._heading_level = int(tag[1])
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.SKIP_TAGS and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag == "title":
            self._title = False
        if re.fullmatch(r"h[1-6]", tag):
            self._heading_level = 0
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        clean = re.sub(r"\s+", " ", data.replace("\ufffd", "-")).strip()
        if not clean:
            return
        if self._title:
            self.title_parts.append(clean)
            return
        self.parts.append(f"\n{'#' * self._heading_level} {clean}\n" if self._heading_level else clean)

    def result(self) -> tuple[str, str, list[str]]:
        title = re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()[:200]
        joined = " ".join(self.parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in re.split(r"\s*\n\s*", joined)]
        text = "\n\n".join(line for line in lines if len(line) > 1)
        return title, text[:MAX_PAGE_TEXT], self.links


def _canonical_url(raw: str) -> str:
    if len(raw.strip()) > 2048:
        raise WebsiteCaptureError("Website address is too long")
    try:
        parts = urlsplit(raw.strip())
    except ValueError as error:
        raise WebsiteCaptureError("Enter a valid public website address") from error
    if parts.scheme.casefold() not in {"http", "https"}:
        raise WebsiteCaptureError("Website address must start with http:// or https://")
    if not parts.hostname or parts.username or parts.password:
        raise WebsiteCaptureError("Website address must not contain credentials")
    try:
        port = parts.port
    except ValueError as error:
        raise WebsiteCaptureError("Website address contains an invalid port") from error
    if port not in {None, 80, 443}:
        raise WebsiteCaptureError("Website capture accepts only standard HTTP and HTTPS ports")
    host = parts.hostname.encode("idna").decode("ascii").casefold().rstrip(".")
    netloc = host if port is None else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.casefold(), netloc, path, "", ""))


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    return parts.scheme, parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80)


def _assert_public_host(url: str, resolver: Callable[..., Any]) -> None:
    host = urlsplit(url).hostname or ""
    try:
        records = resolver(host, None, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as error:
        raise WebsiteCaptureError("The website host could not be resolved") from error
    addresses = {record[4][0] for record in records}
    if not addresses:
        raise WebsiteCaptureError("The website host did not resolve to an address")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise WebsiteCaptureError("Private, local, reserved, and link-local website addresses are blocked")


def _direct_opener():
    """Build a capture-only opener that cannot inherit ambient proxy settings.

    Mission Control may itself be launched from a sandboxed developer shell
    whose HTTP(S)_PROXY points at a short-lived localhost bridge. Owner-requested
    website capture is already bounded and SSRF-checked, so it must connect
    directly instead of silently delegating to that unrelated process.
    """
    return build_opener(ProxyHandler({}), _NoRedirect())


def _default_fetch(url: str) -> tuple[int, dict[str, str], bytes]:
    opener = _direct_opener()
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.8"})
    try:
        with opener.open(request, timeout=12) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            return _decode_http_response(response.status, {key.casefold(): value for key, value in response.headers.items()}, body)
    except HTTPError as error:
        body = error.read(MAX_RESPONSE_BYTES + 1)
        return _decode_http_response(error.code, {key.casefold(): value for key, value in error.headers.items()}, body)
    except (URLError, TimeoutError, OSError) as error:
        raise WebsiteCaptureError(f"Website request failed safely: {error.reason if isinstance(error, URLError) else error}") from error


def _decode_http_response(status, headers, body):
    """Bound both compressed and decoded bytes before any text extraction."""
    if len(body) > MAX_RESPONSE_BYTES:
        raise WebsiteCaptureError('This page exceeds the 8 MB download limit. Use a smaller public About or Services page, or attach a text excerpt. App/login pages may not contain readable public knowledge.')
    encoding = headers.get('content-encoding', 'identity').lower().strip()
    if encoding in {'gzip', 'deflate'}:
        try:
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            body = decoder.decompress(body, MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
                raise ValueError('Invalid or oversized compressed page')
        except (ValueError, zlib.error) as error:
            raise WebsiteCaptureError('Compressed website content is malformed or exceeds the 8 MB decoded limit. Use a smaller public page or a text attachment.') from error
        headers = {key: value for key, value in headers.items() if key not in {'content-encoding', 'content-length'}}
    elif encoding not in {'', 'identity'}:
        raise WebsiteCaptureError('Unsupported website content compression')
    return status, headers, body


def _fetch_page(
    url: str,
    *,
    origin: tuple[str, str, int],
    resolver: Callable[..., Any],
    fetcher: Callable[[str], tuple[int, dict[str, str], bytes]],
) -> tuple[str, str, bytes, int]:
    current = url
    calls = 0
    for _ in range(MAX_REDIRECTS + 1):
        current = _canonical_url(current)
        if _origin(current) != origin:
            raise WebsiteCaptureError("Cross-site redirects are blocked during website capture")
        _assert_public_host(current, resolver)
        status, headers, body = fetcher(current)
        calls += 1
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location:
                raise WebsiteCaptureError("Website returned an invalid redirect")
            current = urljoin(current, location)
            continue
        if status < 200 or status >= 300:
            raise WebsiteCaptureError(
                f"Website returned HTTP {status}",
                http_status=status,
                network_calls=calls,
            )
        if len(body) > MAX_RESPONSE_BYTES:
            raise WebsiteCaptureError("A website page exceeded the 8 MB raw-download limit. Use a smaller public page or a text attachment.")
        media_type = headers.get("content-type", "text/html").split(";", 1)[0].strip().casefold()
        if media_type not in ALLOWED_CONTENT_TYPES:
            raise WebsiteCaptureError(f"Unsupported website content type: {media_type or 'unknown'}")
        return current, media_type, body, calls
    raise WebsiteCaptureError("Website redirected too many times")


def capture_website_knowledge(
    value: Any,
    *,
    resolver: Callable[..., Any] = socket.getaddrinfo,
    fetcher: Callable[[str], tuple[int, dict[str, str], bytes]] = _default_fetch,
    captured_at: str | None = None,
    seed_urls: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"url", "label"}:
        raise WebsiteCaptureError("Website capture accepts only url and label")
    start_url = _canonical_url(str(value.get("url") or ""))
    label = re.sub(r"\s+", " ", str(value.get("label") or "")).strip()
    if len(label) < 2 or len(label) > 120:
        raise WebsiteCaptureError("Website knowledge label must be 2 to 120 characters")
    origin = _origin(start_url)
    # Internal source-bound callers can prioritize already reviewed company URLs.
    # Public requests still accept only url/label, and every seed shares one origin.
    seeds = list(dict.fromkeys([start_url, *[_canonical_url(url) for url in (seed_urls or [])]]))
    if len(seeds) > MAX_PAGES or any(_origin(url) != origin for url in seeds):
        raise WebsiteCaptureError('Source seeds must be at most six same-origin public pages')
    queue = deque(seeds)
    required_seeds = set(seeds)
    queued = set(seeds)
    visited: set[str] = set()
    files: list[dict[str, str]] = []
    pages: list[dict[str, Any]] = []
    skipped_pages: list[dict[str, str]] = []
    network_calls = 0
    attempted_pages = 0
    stamp = captured_at or datetime.now(timezone.utc).isoformat()

    while queue and attempted_pages < MAX_PAGES:
        candidate = queue.popleft()
        if candidate in visited:
            continue
        attempted_pages += 1
        try:
            final_url, media_type, body, calls = _fetch_page(
                candidate,
                origin=origin,
                resolver=resolver,
                fetcher=fetcher,
            )
        except WebsiteCaptureError as error:
            # Hunter-reviewed seeds are required evidence. Links merely discovered
            # while reading those pages are optional; a stale 404/410 must not
            # discard the readable reviewed sources, but remains visible in the
            # governed capture record.
            if candidate not in required_seeds and error.http_status in {404, 410}:
                network_calls += error.network_calls
                skipped_pages.append({
                    "url": candidate,
                    "reason": f"HTTP_{error.http_status}",
                    "source": "DISCOVERED_LINK",
                })
                continue
            raise
        network_calls += calls
        if final_url in visited:
            visited.add(candidate)
            continue
        visited.add(candidate)
        visited.add(final_url)
        try:
            decoded = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise WebsiteCaptureError("Website page is not readable UTF-8 text") from error
        if media_type == "text/html":
            parser = _ReadablePage()
            parser.feed(decoded)
            title, text, links = parser.result()
        else:
            title, text, links = "", re.sub(r"\r\n?", "\n", decoded).strip()[:MAX_PAGE_TEXT], []
        if re.search(r'robot challenge|verify (?:that )?you are (?:a )?human|checking your browser|access denied|just a moment|enable javascript and cookies to continue', f'{title}\n{text}', re.I):
            raise WebsiteCaptureError('HOLD: the website returned an access challenge, not usable company evidence. Supply owner-reviewed documents instead; no bypass was attempted.')
        if len(text) < 20:
            continue
        page_number = len(pages) + 1
        safe_name = f"website-{page_number:02d}-{slugify(title or urlsplit(final_url).path, 'page')[:56]}.md"
        content = f"# {title or 'Website page'}\n\nSource URL: {final_url}\nCaptured: {stamp}\n\n{text}\n"
        files.append({"name": safe_name, "content": content})
        pages.append({
            "url": final_url,
            "title": title or "Website page",
            "stored_name": safe_name,
            "source_sha256": sha256(body),
        })
        for href in links:
            try:
                linked = _canonical_url(urljoin(final_url, href))
            except WebsiteCaptureError:
                continue
            low_value_path = re.match(
                r"^/(?:account|cart|checkout|login|product|products|search|shop|store)(?:/|$)",
                urlsplit(linked).path.casefold(),
            )
            if _origin(linked) == origin and not low_value_path and linked not in visited and linked not in queued:
                queue.append(linked)
                queued.add(linked)

    if not pages:
        raise WebsiteCaptureError("No readable public website pages were captured")
    website_capture = {
        "schema_version": "0.1",
        "requested_url": start_url,
        "captured_at": stamp,
        "scope": "SAME_ORIGIN_PUBLIC_PAGES",
        "max_pages": MAX_PAGES,
        "pages": pages,
        "skipped_pages": skipped_pages,
    }
    package = ingest_knowledge_package(
        {"label": label, "files": files},
        authority_source="OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE",
        network_calls=network_calls,
        website_capture=website_capture,
    )
    return package
