"""Zero-dependency localhost server for the generated X-Agent preview."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print("[x-agent-preview] " + (format % args))

    def send_bytes(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            payload = json.dumps({"status": "READY", "mode": "LOCAL_STAGING_PREVIEW", "provider_calls": 0}).encode("utf-8")
            self.send_bytes(HTTPStatus.OK, payload, "application/json; charset=utf-8")
            return
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        try:
            target.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_bytes(HTTPStatus.BAD_REQUEST, b"Invalid path", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self.send_bytes(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or target.suffix in {".js", ".css", ".json"}:
            content_type += "; charset=utf-8"
        self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run contained X-Agent local preview")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Contained X-Agent preview ready at http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
