#!/usr/bin/env python3
"""Execute and display one governed Luna-to-ANAM visual canary."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "anam-canary"
CANARIES = ROOT / "canaries" / "anam"
SCHEMA_PATH = ROOT / "contracts" / "anam_luna_spoken_response.v0.1.schema.json"
BRIDGE = ROOT / "scripts" / "anam_luna_canary_bridge_v0_1.py"
ANAM_ENV_PATH = Path("C:/AI Fusion Labs/X AGENTS/REPOS/X-LINK/.env")
ANAM_TOKEN_URL = "https://api.anam.ai/v1/auth/session-token"
MIA_PORTRAIT = ROOT / "assets" / "anam" / "mia-support-guide" / "portrait.webp"
SDK_UMD = APP_ROOT / "node_modules" / "@anam-ai" / "js-sdk" / "dist" / "umd" / "anam.js"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
MAX_EVENT_BODY = 4096


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    encoded = canonical(value)
    temporary = path.with_name(path.name + ".next")
    if temporary.exists():
        raise PermissionError("Unexpected temporary state file")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else canonical(value)
    with path.open("xb") as handle:
        handle.write(data)


def auth_metadata() -> dict[str, Any]:
    path = Path("C:/Users/AI Fusion Labs/AppData/Local/hermes/auth.json")
    if not path.is_file():
        return {"exists": False, "sha256": None, "size": None, "mtime_ns": None}
    stat = path.stat()
    return {"exists": True, "sha256": digest(path.read_bytes()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def load_anam_key() -> str:
    if not ANAM_ENV_PATH.is_file():
        raise PermissionError("ANAM credential source is missing")
    matches: list[str] = []
    for line in ANAM_ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*ANAM_API_KEY\s*=\s*(.*?)\s*$", line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
                value = value[1:-1]
            matches.append(value)
    if len(matches) != 1 or not matches[0]:
        raise PermissionError("Expected exactly one non-empty ANAM_API_KEY declaration")
    return matches[0]


class CanaryRuntime:
    def __init__(self, canary_root: Path, execution_root: Path, manifest: dict[str, Any], response: dict[str, Any]):
        self.canary_root = canary_root
        self.execution_root = execution_root
        self.manifest = manifest
        self.response = response
        self.luna_source_reused = manifest.get("mode") == "ANAM_ONLY_ACCEPTED_LUNA_REUSE"
        self.session_requested = False
        self.talk_accepted = False
        self.lock = threading.Lock()
        self.events: list[dict[str, str]] = []
        self.terminal_error: str | None = None
        self.status = "INITIALIZING"
        self.state_path = execution_root / "runtime-state.json"
        self.persist("READY_FOR_USER_START")

    def persist(self, status: str, error: str | None = None) -> None:
        self.status = status
        atomic_json(self.state_path, {
            "schema_version": "0.1",
            "canary_id": self.manifest["canary_id"],
            "status": status,
            "luna_call_consumed": not self.luna_source_reused,
            "accepted_luna_source_reused": self.luna_source_reused,
            "anam_session_slot_consumed": self.session_requested,
            "talk_command_accepted": self.talk_accepted,
            "events": self.events,
            "credential_persisted": False,
            "session_token_persisted": False,
            "deployment_authorized": False,
            "production_approved": False,
            "error": error if error is not None else self.terminal_error,
        })

    def start_session(self) -> dict[str, str]:
        with self.lock:
            if self.session_requested:
                raise PermissionError("The single ANAM session slot has already been consumed")
            self.session_requested = True
            self.persist("ANAM_SESSION_REQUESTING")
        request_bytes = (self.canary_root / "anam-session-request.v0.1.json").read_bytes()
        anam_transaction = next(item for item in self.manifest["provider_transactions"] if item["provider"] == "ANAM")
        expected = anam_transaction["session_request_sha256"]
        if digest(request_bytes) != expected:
            self.persist("FAILED_TERMINAL_NO_RETRY", "ANAM session request drift")
            raise PermissionError("ANAM session request drifted")
        api_key = load_anam_key()
        request = urllib.request.Request(
            ANAM_TOKEN_URL,
            data=request_bytes,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as provider_response:
                body = provider_response.read(64 * 1024)
            decoded = json.loads(body.decode("utf-8"))
            token = decoded.get("sessionToken")
            if not isinstance(token, str) or not token:
                raise PermissionError("ANAM did not return a session token")
            self.persist("ANAM_SESSION_TOKEN_ISSUED")
            return {"session_token": token, "spoken_text": self.response["spoken_text"]}
        except urllib.error.HTTPError as error:
            provider_code = "UNKNOWN"
            try:
                provider_body = json.loads(error.read(16 * 1024).decode("utf-8"))
                raw_code = provider_body.get("error") if isinstance(provider_body, dict) else None
                if isinstance(raw_code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", raw_code):
                    provider_code = raw_code
            except Exception:
                pass
            self.terminal_error = f"ANAM_HTTP_{error.code}:{provider_code}"
            self.persist("FAILED_TERMINAL_NO_RETRY")
            raise PermissionError("ANAM rejected the session request; inspect sanitized evidence") from None
        except Exception as error:
            self.terminal_error = type(error).__name__
            self.persist("FAILED_TERMINAL_NO_RETRY")
            raise

    def record_event(self, event: str, detail: str) -> None:
        allowed = {"CONNECTION_ESTABLISHED", "CONNECTION_CLOSED", "TALK_COMMAND_ACCEPTED", "CANARY_FAILED", "SESSION_STOPPED_BY_USER"}
        if event not in allowed:
            raise PermissionError("Unsupported canary event")
        if len(detail) > 500:
            raise PermissionError("Canary event detail is too long")
        with self.lock:
            if self.status == "FAILED_TERMINAL_NO_RETRY":
                self.events.append({"event": event, "detail": detail})
                self.persist("FAILED_TERMINAL_NO_RETRY")
                return
            if event == "TALK_COMMAND_ACCEPTED":
                if self.talk_accepted or detail != self.response["spoken_text"]:
                    raise PermissionError("Talk evidence drift or duplication")
                self.talk_accepted = True
            self.events.append({"event": event, "detail": detail})
            final = "CANARY_PASS" if self.talk_accepted else "SESSION_ACTIVE"
            if event == "CANARY_FAILED":
                final = "FAILED_TERMINAL_NO_RETRY"
            elif event == "SESSION_STOPPED_BY_USER" and self.talk_accepted:
                final = "CANARY_PASS_SESSION_CLOSED"
            self.persist(final)


class PreviewRuntime:
    """Static rehearsal runtime: every mutating endpoint stays disabled."""

    def start_session(self) -> dict[str, str]:
        raise PermissionError("Provider controls are disabled in preview mode")

    def record_event(self, event: str, detail: str) -> None:
        raise PermissionError("Event recording is disabled in preview mode")


def make_handler(runtime: CanaryRuntime, config: dict[str, Any]):
    class CanaryHandler(BaseHTTPRequestHandler):
        server_version = "XFactoryAnamCanary/0.1"

        def log_message(self, format: str, *args: object) -> None:
            sys.stdout.write("[anam-canary] " + (format % args) + "\n")

        def security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' https://*.anam.ai wss://*.anam.ai; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

        def send_bytes(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.security_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status: HTTPStatus, value: Any) -> None:
            self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path == "/api/config":
                self.send_json(HTTPStatus.OK, config)
                return
            routes = {
                "/": APP_ROOT / "index.html",
                "/app.js": APP_ROOT / "app.js",
                "/styles.css": APP_ROOT / "styles.css",
                "/portrait.webp": MIA_PORTRAIT,
                "/vendor/anam-sdk.js": SDK_UMD,
            }
            target = routes.get(path)
            if target is None or not target.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix in {".html", ".js", ".css"}:
                content_type += "; charset=utf-8"
            self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/start":
                try:
                    self.send_json(HTTPStatus.OK, runtime.start_session())
                except Exception as error:
                    self.send_json(HTTPStatus.CONFLICT, {"error": f"Terminal canary stop: {type(error).__name__}"})
                return
            if path == "/api/event":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 2 or length > MAX_EVENT_BODY:
                        raise PermissionError("Invalid event body size")
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    runtime.record_event(str(body.get("event", "")), str(body.get("detail", "")))
                    self.send_json(HTTPStatus.OK, {"accepted": True})
                except Exception as error:
                    self.send_json(HTTPStatus.BAD_REQUEST, {"error": type(error).__name__})
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    return CanaryHandler


def preflight(canary_root: Path, manifest_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = canary_root / "activation-manifest.v0.1.json"
    manifest = load(manifest_path)
    if digest(manifest_path.read_bytes()) != manifest_sha256:
        raise PermissionError("Activation manifest hash mismatch")
    allowed_ceilings = (
        {"luna_calls": 1, "anam_sessions": 1, "talk_commands": 1, "retries": 0},
        {"luna_calls": 0, "anam_sessions": 1, "talk_commands": 1, "retries": 0},
    )
    if manifest["status"] != "PREPARED_INACTIVE" or manifest["ceilings"] not in allowed_ceilings:
        raise PermissionError("Activation manifest policy mismatch")
    if manifest.get("mode") == "ANAM_ONLY_ACCEPTED_LUNA_REUSE":
        source_path = (ROOT / manifest["accepted_luna_source"]["path"]).resolve(strict=True)
        source_path.relative_to((CANARIES / "mia-luna-visual-canary-005").resolve())
        if digest(source_path.read_bytes()) != manifest["accepted_luna_source"]["sha256"]:
            raise PermissionError("Accepted Luna response drift")
        Draft202012Validator(load(SCHEMA_PATH)).validate(load(source_path))
    else:
        prompt = (canary_root / "luna-prompt.txt").read_bytes()
        payload = (canary_root / "luna-payload.v0.1.json").read_bytes()
        if digest(prompt) != manifest["provider_transactions"][0]["prompt_sha256"]:
            raise PermissionError("Luna prompt drift")
        if digest(payload) != manifest["provider_transactions"][0]["payload_sha256"]:
            raise PermissionError("Luna payload drift")
    if not SDK_UMD.is_file() or load(APP_ROOT / "node_modules" / "@anam-ai" / "js-sdk" / "package.json")["version"] != "4.25.0":
        raise PermissionError("Pinned ANAM SDK is unavailable")
    implementation_paths = {
        "runner": ROOT / "scripts" / "run_anam_luna_canary_v0_1.py",
        "hermes_bridge": BRIDGE,
        "html": APP_ROOT / "index.html",
        "javascript": APP_ROOT / "app.js",
        "styles": APP_ROOT / "styles.css",
        "package_lock": APP_ROOT / "package-lock.json",
        "sdk_umd": SDK_UMD,
    }
    for label, expected_hash in manifest["implementation_sha256"].items():
        path = implementation_paths.get(label)
        if path is None or not path.is_file() or digest(path.read_bytes()) != expected_hash:
            raise PermissionError(f"Canary implementation drift: {label}")
    return manifest, load(canary_root / "public-config.v0.1.json")


def execute_luna(canary_root: Path, manifest: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    execution_id = datetime.now(timezone.utc).strftime("execution-%Y%m%d-%H%M%S")
    execution_root = canary_root / "executions" / execution_id
    execution_root.mkdir(parents=True, exist_ok=False)
    prompt = (canary_root / "luna-prompt.txt").read_bytes()
    prompt_path = execution_root / "luna-prompt.txt"
    evidence_path = execution_root / "luna-evidence.json"
    write_new(prompt_path, prompt)
    before_auth = auth_metadata()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    transaction = manifest["provider_transactions"][0]
    process = subprocess.run([
        sys.executable, "-B", str(BRIDGE),
        "--execution-root", str(execution_root),
        "--prompt-file", str(prompt_path),
        "--evidence-file", str(evidence_path),
        "--prompt-sha256", transaction["prompt_sha256"],
        "--payload-sha256", transaction["payload_sha256"],
    ], cwd=execution_root, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=300, check=False)
    if process.stdout or process.stderr:
        raise PermissionError("Unexpected bridge output escaped the evidence channel")
    evidence = load(evidence_path)
    if process.returncode != 0 or evidence["exit_code"] != 0 or evidence["physical_requests"] != 1:
        raise RuntimeError("Luna canary transaction failed; no retry permitted")
    if any(evidence[key] for key in ("tool_attempts", "oauth_refresh_attempts", "auth_write_attempts", "codex_cli_import_attempts")):
        raise PermissionError("Luna canary violated zero-tool, read-only-auth policy")
    if auth_metadata() != before_auth:
        raise PermissionError("Hermes authentication changed during Luna canary")
    response = json.loads(base64.b64decode(evidence["response_base64"], validate=True).decode("utf-8"))
    Draft202012Validator(load(SCHEMA_PATH)).validate(response)
    write_new(execution_root / "luna-response.json", response)
    return execution_root, response


def reuse_accepted_luna(canary_root: Path, manifest: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    execution_id = datetime.now(timezone.utc).strftime("execution-%Y%m%d-%H%M%S")
    execution_root = canary_root / "executions" / execution_id
    execution_root.mkdir(parents=True, exist_ok=False)
    source_path = (ROOT / manifest["accepted_luna_source"]["path"]).resolve(strict=True)
    response_bytes = source_path.read_bytes()
    if digest(response_bytes) != manifest["accepted_luna_source"]["sha256"]:
        raise PermissionError("Accepted Luna response drift")
    response = json.loads(response_bytes.decode("utf-8"))
    Draft202012Validator(load(SCHEMA_PATH)).validate(response)
    write_new(execution_root / "luna-response.reused.json", response_bytes)
    return execution_root, response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-id", required=True)
    parser.add_argument("--activation-manifest-sha256", required=True)
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    if not ID_PATTERN.fullmatch(args.canary_id) or not re.fullmatch(r"sha256:[0-9a-f]{64}", args.activation_manifest_sha256):
        raise SystemExit("Invalid canary ID or manifest hash")
    canary_root = (CANARIES / args.canary_id).resolve(strict=True)
    manifest, config = preflight(canary_root, args.activation_manifest_sha256)
    config = {**config, "maximum_luna_calls": manifest["ceilings"]["luna_calls"]}
    if args.preflight:
        print(json.dumps({"canary_id": args.canary_id, "status": "PREFLIGHT_PASS", "provider_calls": 0, "anam_sessions": 0}, indent=2))
        return 0
    if args.preview:
        config = {**config, "preview_mode": True}
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(PreviewRuntime(), config))
        url = f"http://127.0.0.1:{args.port}/"
        print(json.dumps({"status": "LOCAL_VISUAL_REHEARSAL", "url": url, "provider_calls": 0, "anam_sessions": 0}, indent=2), flush=True)
        if args.open_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PermissionError("PYTHONDONTWRITEBYTECODE=1 is required")
    if manifest.get("mode") == "ANAM_ONLY_ACCEPTED_LUNA_REUSE":
        execution_root, response = reuse_accepted_luna(canary_root, manifest)
    else:
        execution_root, response = execute_luna(canary_root, manifest)
    runtime = CanaryRuntime(canary_root, execution_root, manifest, response)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(runtime, config))
    url = f"http://127.0.0.1:{args.port}/"
    print(json.dumps({"status": "READY_FOR_USER_START", "url": url, "execution_root": str(execution_root)}, indent=2), flush=True)
    if args.open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
