#!/usr/bin/env python3
"""Local-only HTTP surface for the operational X-Factory Mission Control draft."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.mission_control_factory_v0_1 import (  # noqa: E402
    INTERACTIVE_ROOT,
    MIA_PORTRAIT,
    MissionControlError,
    create_mission,
    list_missions,
    load_json,
)
from x_factory.mission_control_presence_v0_1 import (  # noqa: E402
    PresencePreviewError,
    preview_descriptor,
    runtime_status as presence_runtime_status,
)
from x_factory.runtime_foundry_v0_1 import (  # noqa: E402
    RuntimeFoundryError,
    runtime_status as agent_runtime_status,
    simulate_turn,
)
from x_factory.repo_foundry_v0_1 import (  # noqa: E402
    RepoFoundryError,
    create_local_repo,
    find_local_repo,
    repo_root,
)
from x_factory.completion_pipeline_v0_1 import (  # noqa: E402
    CompletionPipelineError,
    complete_local_draft,
    find_completion,
)
from x_factory.owner_control_v0_1 import (  # noqa: E402
    OwnerControlError,
    owner_control_status,
    prepare_governed_run,
    prepare_repo_promotion,
    request_governed_run,
    request_repo_promotion,
)
from x_factory.chassis_depot_v0_1 import (  # noqa: E402
    ChassisDepotError,
    commission_chassis,
    derive_public_role,
    get_chassis,
    list_chassis,
    list_module_options,
    recommend_chassis,
)
from x_factory.knowledge_loading_v0_1 import (  # noqa: E402
    KnowledgeLoadingError,
    approve_knowledge_package,
    ingest_knowledge_package,
    list_knowledge_packages,
    package_status,
)
from x_factory.knowledge_compiler_v0_1 import (  # noqa: E402
    KnowledgeCompilerError,
    compilation_summary,
    compile_package,
    get_compilation,
    review_compilation,
)
from x_factory.website_ingestion_v0_1 import (  # noqa: E402
    WebsiteCaptureError,
    capture_website_knowledge,
)


APP_ROOT = ROOT / "apps/mission-control"
MAX_BODY = 64 * 1024
MAX_KNOWLEDGE_BODY = 768 * 1024
MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")


def public_record_view(record: dict) -> dict:
    """Return an owner-safe view without mutating an immutable mission record."""
    agent = record.get("agent", {})
    if not agent.get("derived_from_chassis"):
        return record
    safe = deepcopy(record)
    safe_agent = safe["agent"]
    chassis = safe_agent.get("derived_from_chassis") or {}
    public_role = safe_agent.get("public_role_title") or derive_public_role(
        safe_agent.get("purpose", ""),
        chassis.get("chassis_role_title") or chassis.get("role_title") or "Concierge",
    )
    safe_agent["public_role_title"] = public_role
    safe_agent["display_name"] = f"{safe_agent['agent_name']} — {public_role}" if public_role else safe_agent["agent_name"]
    safe_agent["role_title"] = public_role or "X-Agent"
    return safe


class MissionControlHandler(BaseHTTPRequestHandler):
    server_version = "XFactoryMissionControl/1.9"

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write("[mission-control] " + (format % args) + "\n")

    def security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

    def send_bytes(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: HTTPStatus, value: object) -> None:
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/status":
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "READY",
                    "mode": "LOCAL_DETERMINISTIC_DRAFT",
                    "provider_calls": 0,
                    "network_policy": "LOCALHOST_UI_EXPLICIT_SCOPED_WEBSITE_CAPTURE_ONLY",
                    "model_plan": "openai-codex / gpt-5.6-luna",
                    "semantic_review": "HERMES_LUNA_UNANIMOUS_PASS",
                    "anam_status": "VISUAL_TRANSPORT_PROVEN",
                    "factory_version": "1.9",
                    "website_review_build_interlock": True,
                    "owner_progressive_disclosure": True,
                    "capabilities": ["FIVE_STEP_OWNER_WORKFLOW", "EIGHT_INTERNAL_STATIONS", "TROY_PROMPT_FORGE", "ANAM_STANDARD_ARTIFACTS", "LOCAL_BUILD", "REVISION_FROM_HISTORY", "X_AGENT_CHASSIS_DEPOT", "CLIENT_COMMISSIONING", "IDENTITY_SEPARATION", "IMMUTABLE_KNOWLEDGE_PACKAGES", "OWNER_KNOWLEDGE_APPROVAL", "SCOPED_PUBLIC_WEBSITE_CAPTURE", "WEBSITE_SOURCE_PROVENANCE", "WEBSITE_RELEVANCE_FILTER", "WEBSITE_BOILERPLATE_DEDUP", "KNOWLEDGE_PROMPT_SEPARATION", "DETERMINISTIC_KNOWLEDGE_COMPILER", "SOURCE_LINKED_OWNER_REVIEW", "INSTANCE_KNOWLEDGE_BUILDER", "PERSONALIZED_SYSTEM_PROMPT", "KNOWLEDGE_TRACEABILITY", "INSTANCE_KNOWLEDGE_TESTS", "INSTANCE_RUNTIME_CONTRACT_LOCK", "CROSS_ARTIFACT_IDENTITY_VALIDATION", "LOCAL_MULTI_TURN_BEHAVIOR_CERTIFICATION", "FRESH_SESSION_NON_PERSISTENCE_PROOF", "RUNTIME_BEHAVIOR_PROOF_PLAN", "RUNTIME_FOUNDRY_PACKAGE", "HERMES_PROFILE_BLUEPRINT", "LOCAL_RUNTIME_BOUNDARY_CONSOLE", "GROUNDED_MATCHER_V0_2", "REALISTIC_PARAPHRASE_CERTIFICATION", "PRIMARY_UNKNOWN_REQUEST_CAPTURE", "PROVIDER_FREE_PREVIEW_DISCLOSURE", "INACTIVE_RUNTIME_CANARY", "MODULE_OPTIONS_BAY", "X_LINK_PACKAGE", "HERMES_REVIEW_CERTIFIED", "ANAM_TRANSPORT_PROVEN", "MISSION_PRESENCE_PREVIEW", "INDEPENDENT_LOCAL_REVIEW", "HERMES_SLASH_REVIEW_PACKET", "AUTOMATIC_LOCAL_COMPLETION", "PORTER_STAGING_REPO", "PORTER_OFFICIAL_RUNTIME_GATE", "PRODUCT_METRICS", "OWNER_CONTROL_PACKETS", "OWNER_EXECUTION_REQUESTS", "GUARDED_EXECUTOR_PREFLIGHT"],
                },
            )
            return
        if path == "/api/missions":
            self.send_json(HTTPStatus.OK, {"missions": [public_record_view(record) for record in list_missions()]})
            return
        if path == "/api/chassis":
            self.send_json(HTTPStatus.OK, {"chassis": list_chassis()})
            return
        if path == "/api/knowledge-packages":
            packages = list_knowledge_packages()
            for package in packages:
                package["compilation"] = compilation_summary(package["package_id"])
            self.send_json(HTTPStatus.OK, {"packages": packages})
            return
        compilation_match = re.fullmatch(r"/api/knowledge-packages/(kp-[a-z0-9-]+)/compilation", path)
        if compilation_match:
            try:
                compilation = get_compilation(compilation_match.group(1))
            except KnowledgeCompilerError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, compilation)
            return
        knowledge_match = re.fullmatch(r"/api/knowledge-packages/(kp-[a-z0-9-]+)", path)
        if knowledge_match:
            try:
                package = package_status(knowledge_match.group(1))
            except KnowledgeLoadingError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            package["compilation"] = compilation_summary(package["package_id"])
            self.send_json(HTTPStatus.OK, package)
            return
        options_match = re.fullmatch(r"/api/chassis/([^/]+)/options", path)
        if options_match:
            try:
                options = list_module_options(options_match.group(1))
            except ChassisDepotError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, options)
            return
        chassis_match = re.fullmatch(r"/api/chassis/([^/]+)", path)
        if chassis_match:
            try:
                chassis = get_chassis(chassis_match.group(1))
            except ChassisDepotError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, chassis)
            return
        if path == "/favicon.ico":
            self.send_bytes(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
            return
        if path == "/assets/mia.webp":
            if MIA_PORTRAIT.is_file():
                self.send_bytes(HTTPStatus.OK, MIA_PORTRAIT.read_bytes(), "image/webp")
            else:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Persona portrait unavailable"})
            return
        mission_match = re.fullmatch(r"/api/missions/([^/]+)", path)
        if mission_match:
            mission_id = mission_match.group(1)
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            record_path = INTERACTIVE_ROOT / mission_id / "mission-record.json"
            if not record_path.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Mission not found"})
                return
            self.send_json(HTTPStatus.OK, public_record_view(load_json(record_path)))
            return
        brief_match = re.fullmatch(r"/api/missions/([^/]+)/brief", path)
        if brief_match:
            mission_id = brief_match.group(1)
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            brief_path = INTERACTIVE_ROOT / mission_id / "input/owner-brief.v0.1.json"
            if not brief_path.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Owner brief not found"})
                return
            self.send_json(HTTPStatus.OK, load_json(brief_path))
            return
        preview_match = re.fullmatch(r"/api/missions/([^/]+)/presence-preview", path)
        if preview_match:
            try:
                descriptor = preview_descriptor(preview_match.group(1))
            except PresencePreviewError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, descriptor)
            return
        runtime_match = re.fullmatch(r"/api/missions/([^/]+)/presence-runtime", path)
        if runtime_match:
            try:
                descriptor = preview_descriptor(runtime_match.group(1))
            except PresencePreviewError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            canary_id = descriptor.get("activation", {}).get("canary_id") if descriptor.get("activation") else None
            self.send_json(HTTPStatus.OK, presence_runtime_status(canary_id))
            return
        agent_runtime_match = re.fullmatch(r"/api/missions/([^/]+)/runtime-foundry", path)
        if agent_runtime_match:
            mission_id = agent_runtime_match.group(1)
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            mission_root = INTERACTIVE_ROOT / mission_id
            if not (mission_root / "mission-record.json").is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Mission not found"})
                return
            try:
                status = agent_runtime_status(mission_root)
            except RuntimeFoundryError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, status)
            return
        repo_status_match = re.fullmatch(r"/api/missions/([^/]+)/repo", path)
        if repo_status_match:
            mission_id = repo_status_match.group(1)
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            record = find_local_repo(mission_id)
            self.send_json(HTTPStatus.OK, {"status": record.get("status", "LOCAL_REPO_READY"), "repo": record} if record else {"status": "NOT_CREATED", "repo": None})
            return
        completion_status_match = re.fullmatch(r"/api/missions/([^/]+)/completion", path)
        if completion_status_match:
            try:
                record = find_completion(completion_status_match.group(1))
            except CompletionPipelineError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, {"status": record.get("status", "LOCAL_DRAFT_COMPLETE"), "completion": record} if record else {"status": "NOT_COMPLETED", "completion": None})
            return
        control_status_match = re.fullmatch(r"/api/missions/([^/]+)/owner-control", path)
        if control_status_match:
            try:
                status = owner_control_status(control_status_match.group(1))
            except OwnerControlError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, status)
            return
        repo_file_match = re.fullmatch(r"/api/repos/([^/]+)/files/(.+)", path)
        if repo_file_match:
            repo_id, relative = repo_file_match.groups()
            try:
                root = repo_root(repo_id)
            except RepoFoundryError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid repo artifact path"})
                return
            if not target.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Repo artifact not found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or target.suffix in {".json", ".md", ".py", ".toml", ".yaml", ".yml", ".ps1", ".example"}:
                content_type += "; charset=utf-8"
            self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)
            return
        repo_preview_match = re.fullmatch(r"/repo-preview/([^/]+)(?:/(.*))?", path)
        if repo_preview_match:
            repo_id, relative = repo_preview_match.groups()
            try:
                repo_base = repo_root(repo_id)
                root = repo_base / "web"
            except RepoFoundryError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            relative = relative or "index.html"
            target = (root / relative).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid preview path"})
                return
            if not target.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Preview file not found"})
                return
            if relative == "agent.json":
                repo_record_path = repo_base / "repo-record.json"
                repo_record = load_json(repo_record_path) if repo_record_path.is_file() else {}
                source_mission = repo_record.get("source_mission_id")
                source_record_path = INTERACTIVE_ROOT / source_mission / "mission-record.json" if source_mission else None
                if source_record_path and source_record_path.is_file():
                    source_record = public_record_view(load_json(source_record_path))
                    preview_agent = load_json(target)
                    preview_agent["display_name"] = source_record["agent"]["display_name"]
                    self.send_json(HTTPStatus.OK, preview_agent)
                    return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or target.suffix in {".js", ".css", ".json"}:
                content_type += "; charset=utf-8"
            self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)
            return
        file_match = re.fullmatch(r"/api/missions/([^/]+)/files/(.+)", path)
        if file_match:
            mission_id, relative = file_match.groups()
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            mission_root = (INTERACTIVE_ROOT / mission_id).resolve()
            target = (mission_root / relative).resolve()
            try:
                target.relative_to(mission_root)
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid artifact path"})
                return
            if not target.is_file():
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Artifact not found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or target.suffix in {".json", ".md", ".py"}:
                content_type += "; charset=utf-8"
            self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)
            return
        self.serve_static(path)

    def serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (APP_ROOT / relative).resolve()
        try:
            target.relative_to(APP_ROOT.resolve())
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid path"})
            return
        if not target.is_file():
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or target.suffix in {".js", ".css"}:
            content_type += "; charset=utf-8"
        self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/chassis/recommend":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Job description must be valid JSON under 64 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = recommend_chassis(payload.get("purpose") if isinstance(payload, dict) else None)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Job description is not valid UTF-8 JSON"})
                return
            except ChassisDepotError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)
            return
        if path == "/api/knowledge-packages":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_KNOWLEDGE_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Knowledge upload must be valid JSON under 768 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                package = ingest_knowledge_package(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Knowledge upload is not valid UTF-8 JSON"})
                return
            except KnowledgeLoadingError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Knowledge Loading Dock stopped safely: {error}"})
                return
            self.send_json(HTTPStatus.CREATED, package)
            return
        if path == "/api/website-knowledge":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Website capture request must be valid JSON under 64 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                package = capture_website_knowledge(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Website capture request is not valid UTF-8 JSON"})
                return
            except WebsiteCaptureError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Website capture stopped safely: {error}"})
                return
            self.send_json(HTTPStatus.CREATED, package)
            return
        compilation_create_match = re.fullmatch(r"/api/knowledge-packages/(kp-[a-z0-9-]+)/compile", path)
        if compilation_create_match:
            try:
                compilation = compile_package(compilation_create_match.group(1))
            except KnowledgeCompilerError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, compilation)
            return
        compilation_review_match = re.fullmatch(r"/api/knowledge-packages/(kp-[a-z0-9-]+)/compilation/review", path)
        if compilation_review_match:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Knowledge review must be valid JSON under 64 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                compilation = review_compilation(compilation_review_match.group(1), payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Knowledge review is not valid UTF-8 JSON"})
                return
            except KnowledgeCompilerError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, compilation)
            return
        knowledge_approval_match = re.fullmatch(r"/api/knowledge-packages/(kp-[a-z0-9-]+)/approve", path)
        if knowledge_approval_match:
            try:
                package = approve_knowledge_package(knowledge_approval_match.group(1))
            except KnowledgeLoadingError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, package)
            return
        commission_match = re.fullmatch(r"/api/chassis/([^/]+)/commission", path)
        if commission_match:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Commissioning request must be valid JSON under 64 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                record = commission_chassis(commission_match.group(1), payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Commissioning request is not valid UTF-8 JSON"})
                return
            except (ChassisDepotError, MissionControlError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Commissioning stopped safely: {error}"})
                return
            self.send_json(HTTPStatus.CREATED, record)
            return
        repo_match = re.fullmatch(r"/api/missions/([^/]+)/repo", path)
        if repo_match:
            try:
                record = create_local_repo(repo_match.group(1))
            except RepoFoundryError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Repo Foundry failed safely: {error}"})
                return
            self.send_json(HTTPStatus.CREATED, record)
            return
        completion_match = re.fullmatch(r"/api/missions/([^/]+)/complete", path)
        if completion_match:
            try:
                record = complete_local_draft(completion_match.group(1))
            except CompletionPipelineError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Local completion stopped safely: {error}"})
                return
            self.send_json(HTTPStatus.CREATED, record)
            return
        governed_run_match = re.fullmatch(r"/api/missions/([^/]+)/owner-control/governed-run", path)
        if governed_run_match:
            try:
                plan = prepare_governed_run(governed_run_match.group(1))
            except OwnerControlError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, plan)
            return
        promotion_match = re.fullmatch(r"/api/missions/([^/]+)/owner-control/repo-promotion", path)
        if promotion_match:
            try:
                plan = prepare_repo_promotion(promotion_match.group(1))
            except OwnerControlError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, plan)
            return
        governed_request_match = re.fullmatch(r"/api/missions/([^/]+)/owner-control/governed-run/request", path)
        if governed_request_match:
            try:
                request = request_governed_run(governed_request_match.group(1))
            except OwnerControlError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, request)
            return
        promotion_request_match = re.fullmatch(r"/api/missions/([^/]+)/owner-control/repo-promotion/request", path)
        if promotion_request_match:
            try:
                request = request_repo_promotion(promotion_request_match.group(1))
            except OwnerControlError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, request)
            return
        runtime_simulate_match = re.fullmatch(r"/api/missions/([^/]+)/runtime-foundry/simulate", path)
        if runtime_simulate_match:
            mission_id = runtime_simulate_match.group(1)
            if not MISSION_ID.fullmatch(mission_id):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid mission ID"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Runtime test must be valid JSON under 64 KB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict) or set(payload) != {"message"}:
                    raise RuntimeFoundryError("Runtime test accepts only one message field")
                result = simulate_turn(INTERACTIVE_ROOT / mission_id, payload["message"])
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Runtime test is not valid UTF-8 JSON"})
                return
            except RuntimeFoundryError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)
            return
        if path != "/api/missions":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 2 or length > MAX_BODY:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Request body must be valid JSON under 64 KB"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            record = create_mission(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body is not valid UTF-8 JSON"})
            return
        except MissionControlError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except Exception as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Contained build failed: {error}"})
            return
        self.send_json(HTTPStatus.CREATED, record)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local X-Factory Mission Control")
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    if not APP_ROOT.is_dir():
        raise SystemExit("Mission Control application files are missing")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), MissionControlHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"X-Factory Mission Control ready at {url}", flush=True)
    print("Contained local draft: no provider calls, deployment, or production actions.", flush=True)
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
