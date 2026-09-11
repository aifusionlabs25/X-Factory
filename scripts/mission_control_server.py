#!/usr/bin/env python3
"""Local-only HTTP surface for the operational X-Factory Mission Control draft."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import socket
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
from x_factory.hunter_draft_v0_1 import HunterDraftError, list_prospects, review_prospect, accept_draft, reopen_draft
from x_factory.hunter_knowledge_v0_1 import knowledge_plan, prepare_knowledge
from x_factory.hunter_inbox_v0_1 import HunterInboxError, list_inbox, send_to_factory, use_handoff
from x_factory.idea_research_v0_1 import start_research, cancel_research
from x_factory.idea_research_review_v0_1 import job_view, review_direction
from x_factory.role_library_v0_1 import list_roles
from x_factory.hunter_refresh_v0_1 import HunterRefreshError, create_refresh_request
from x_factory.idea_intake_v0_1 import IdeaIntakeError, prepare_idea, research_idea, get_idea
from x_factory.control_plane_registry_v0_1 import registry_snapshot


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
        if path.startswith('/api/prepared-agents/'):
            from x_factory.prepared_agent_v0_1 import get_project
            try:
                self.send_json(HTTPStatus.OK, get_project(path.removeprefix('/api/prepared-agents/')))
            except (ValueError, OSError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            return
        if path == '/api/roles':
            self.send_json(HTTPStatus.OK, {'roles': list_roles()})
            return
        if path.startswith('/api/idea-research/'):
            try:
                self.send_json(HTTPStatus.OK, job_view(path.removeprefix('/api/idea-research/')))
            except (ValueError, OSError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            return
        if path.startswith('/api/ideas/'):
            try:
                self.send_json(HTTPStatus.OK, get_idea(path.removeprefix('/api/ideas/')))
            except (ValueError, IdeaIntakeError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            return
        if path == "/api/hunter/prospects":
            try:
                self.send_json(HTTPStatus.OK, list_prospects())
            except HunterDraftError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        if path == "/api/hunter/inbox":
            try:
                self.send_json(HTTPStatus.OK, list_inbox())
            except HunterInboxError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        if path == "/api/status":
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "READY",
                    "mode": "LOCAL_BUILD_OPTIONAL_OWNER_STARTED_HERMES_RESEARCH",
                    "provider_calls": 0,
                    "provider_calls_scope": "LOCAL_BUILD_ONLY_RESEARCH_USAGE_IS_PER_JOB",
                    "network_policy": "LOCALHOST_UI_OWNER_STARTED_PUBLIC_RESEARCH_AND_WEBSITE_CAPTURE",
                    "model_plan": "openai-codex / gpt-5.6-luna",
                    "semantic_review": "HERMES_LUNA_UNANIMOUS_PASS",
                    "anam_status": "VISUAL_TRANSPORT_PROVEN",
                    "factory_version": "1.9",
                    "studio_intake_version": "1.1",
                    "research_runtime": "HERMES_WEB_ONLY_OWNER_STARTED",
                    "entry_sources": ["OWNER_IDEA", "COMPANY_WEBSITE", "X_POST_INSPIRATION", "HUNTER_REVIEWED_DRAFT"],
                    "idea_research_mode": "HERMES_WEB_RESEARCH_THEN_OWNER_DIRECTION_REVIEW",
                    "role_library_count": len(list_roles()),
                    "website_review_build_interlock": True,
                    "owner_progressive_disclosure": True,
                    "internal_stations": 9,
                    "knowledge_engineering": "OMNARA_KNOWLEDGE_STUDIO",
                    "capabilities": ["FIVE_STEP_OWNER_WORKFLOW", "EIGHT_INTERNAL_STATIONS", "TROY_PROMPT_FORGE", "ANAM_STANDARD_ARTIFACTS", "LOCAL_BUILD", "REVISION_FROM_HISTORY", "X_AGENT_CHASSIS_DEPOT", "CLIENT_COMMISSIONING", "IDENTITY_SEPARATION", "IMMUTABLE_KNOWLEDGE_PACKAGES", "OWNER_KNOWLEDGE_APPROVAL", "SCOPED_PUBLIC_WEBSITE_CAPTURE", "WEBSITE_SOURCE_PROVENANCE", "WEBSITE_RELEVANCE_FILTER", "WEBSITE_BOILERPLATE_DEDUP", "KNOWLEDGE_PROMPT_SEPARATION", "DETERMINISTIC_KNOWLEDGE_COMPILER", "SOURCE_LINKED_OWNER_REVIEW", "INSTANCE_KNOWLEDGE_BUILDER", "PERSONALIZED_SYSTEM_PROMPT", "KNOWLEDGE_TRACEABILITY", "INSTANCE_KNOWLEDGE_TESTS", "INSTANCE_RUNTIME_CONTRACT_LOCK", "CROSS_ARTIFACT_IDENTITY_VALIDATION", "LOCAL_MULTI_TURN_BEHAVIOR_CERTIFICATION", "FRESH_SESSION_NON_PERSISTENCE_PROOF", "RUNTIME_BEHAVIOR_PROOF_PLAN", "RUNTIME_FOUNDRY_PACKAGE", "HERMES_PROFILE_BLUEPRINT", "LOCAL_RUNTIME_BOUNDARY_CONSOLE", "GROUNDED_MATCHER_V0_2", "REALISTIC_PARAPHRASE_CERTIFICATION", "PRIMARY_UNKNOWN_REQUEST_CAPTURE", "PROVIDER_FREE_PREVIEW_DISCLOSURE", "INACTIVE_RUNTIME_CANARY", "MODULE_OPTIONS_BAY", "X_LINK_PACKAGE", "HERMES_REVIEW_CERTIFIED", "ANAM_TRANSPORT_PROVEN", "MISSION_PRESENCE_PREVIEW", "INDEPENDENT_LOCAL_REVIEW", "HERMES_SLASH_REVIEW_PACKET", "AUTOMATIC_LOCAL_COMPLETION", "PORTER_STAGING_REPO", "PORTER_OFFICIAL_RUNTIME_GATE", "PRODUCT_METRICS", "OWNER_CONTROL_PACKETS", "OWNER_EXECUTION_REQUESTS", "GUARDED_EXECUTOR_PREFLIGHT", "HUNTER_FACTORY_LEAD_INBOX", "HUNTER_REFRESH_REQUESTS"],
                },
            )
            return
        if path == "/api/control-plane/registry":
            try:
                self.send_json(HTTPStatus.OK, registry_snapshot())
            except (ValueError, OSError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
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
        prepared_route = re.fullmatch(r'/api/prepared-agents/(project-[a-f0-9]{24})/(edit|approve|build|refresh|text-session|text-turn|dojo|portrait)', path)
        if path in {'/api/prepared-agents','/api/prepared-from-hunter'} or prepared_route:
            from x_factory.prepared_agent_v0_1 import start_project, edit_project, approve_project, build_project, refresh_project, start_from_hunter
            if (self.headers.get('Origin') not in {None, f'http://127.0.0.1:{self.server.server_port}'}
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                self.send_json(HTTPStatus.FORBIDDEN, {'error': 'Use the local prepared-agent controls.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 2 <= length <= MAX_BODY:
                    raise ValueError('Prepared-agent input must be JSON under 64 KB')
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(payload, dict):
                    raise ValueError('Prepared-agent input must be an object')
                if path == '/api/prepared-from-hunter':
                    result=start_from_hunter(payload)
                elif prepared_route and prepared_route.group(2)=='portrait':
                    from x_factory.prepared_agent_v0_1 import save_portrait
                    result=save_portrait(prepared_route.group(1),payload)
                elif prepared_route and prepared_route.group(2)=='dojo':
                    from x_factory.dojo_candidate_v0_1 import start_evaluation
                    result=start_evaluation(prepared_route.group(1),payload)
                elif prepared_route and prepared_route.group(2) in {'text-session','text-turn'}:
                    from x_factory.candidate_text_runtime_v0_1 import start_session, turn, candidate
                    project_id=prepared_route.group(1)
                    if prepared_route.group(2)=='text-session':
                        if set(payload)!={'owner_requested','candidate_sha256'} or payload['owner_requested'] is not True or candidate(project_id)[0]['candidate_sha256']!=payload['candidate_sha256']:
                            raise ValueError('Open an explicit test session for this exact candidate')
                        result=start_session(project_id)
                    else:
                        session_id=payload.pop('session_id',None)
                        result=turn(project_id,session_id,payload)
                elif prepared_route:
                    action = {'edit': edit_project, 'approve': approve_project, 'build': build_project, 'refresh':refresh_project}[prepared_route.group(2)]
                    result = action(prepared_route.group(1), payload)
                else:
                    if set(payload) != {'idea_id', 'owner_requested'} or payload['owner_requested'] is not True:
                        raise ValueError('Start preparation explicitly; it uses bounded Hermes research and drafting calls')
                    result = start_project(payload['idea_id'])
                self.send_json(HTTPStatus.OK, result)
            except (ValueError, OSError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)[:700]})
            except Exception:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': 'Preparation stopped safely. Your saved project and completed evidence remain available.'})
            return
        research_route = re.fullmatch(r'/api/ideas/(idea-[a-f0-9]{24})/(research-jobs|research-review)', path)
        cancel_route = re.fullmatch(r'/api/idea-research/(research-[a-f0-9]{24})/cancel', path)
        if research_route or cancel_route or path == '/api/roles/recommend':
            if (self.headers.get('Origin') not in {None, f'http://127.0.0.1:{self.server.server_port}'}
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                self.send_json(HTTPStatus.FORBIDDEN, {'error': 'Use the local Factory research controls.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 2 <= length <= MAX_BODY:
                    raise ValueError('Research input must be JSON under 64 KB.')
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(payload, dict):
                    raise ValueError('Research input must be an object.')
                if path == '/api/roles/recommend':
                    if set(payload) != {'purpose'}:
                        raise ValueError('Role recommendation requires only the purpose.')
                    result = recommend_chassis(payload['purpose'])
                elif cancel_route:
                    if payload != {'owner_requested': True}:
                        raise ValueError('Cancel research using the owner control.')
                    result = cancel_research(cancel_route.group(1))
                elif research_route.group(2) == 'research-review':
                    result = review_direction(research_route.group(1), payload)
                else:
                    if set(payload) != {'owner_requested', 'draft_sha256'} or payload['owner_requested'] is not True:
                        raise ValueError('Start research explicitly after reviewing your brief.')
                    draft = get_idea(research_route.group(1))
                    if draft['draft_sha256'] != payload['draft_sha256']:
                        raise ValueError('The draft changed. Reopen it before starting research.')
                    result = start_research(draft)
                self.send_json(HTTPStatus.OK, result)
            except (ValueError, UnicodeDecodeError, OSError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            return
        if path in {'/api/ideas/prepare', '/api/ideas/research'}:
            origin = self.headers.get('Origin')
            if (origin not in {None, f'http://127.0.0.1:{self.server.server_port}'} or
                    self.headers.get('Sec-Fetch-Site') == 'cross-site' or
                    self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                self.send_json(HTTPStatus.FORBIDDEN, {'error': 'Open this action in the local Factory workspace.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 2 <= length <= MAX_BODY:
                    raise IdeaIntakeError('Idea input must be JSON under 64 KB. Reduce attachment size.')
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                action = prepare_idea if path.endswith('/prepare') else research_idea
                self.send_json(HTTPStatus.OK, action(payload))
            except (ValueError, UnicodeDecodeError, IdeaIntakeError, KnowledgeLoadingError, KnowledgeCompilerError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            except OSError:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'error': 'The local idea draft could not be saved.'})
            return
        if path in {"/api/hunter/review", "/api/hunter/accept-draft", "/api/hunter/reopen-draft", "/api/hunter/knowledge-plan", "/api/hunter/prepare-knowledge", "/api/hunter/inbox/send", "/api/hunter/inbox/refresh", "/api/hunter/inbox/use"}:
            # Only the separate prepare route may fetch/compile; none builds or approves facts.
            origin = self.headers.get("Origin")
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if origin not in {None, expected_origin} or self.headers.get("Sec-Fetch-Site") == "cross-site" or self.headers.get("Content-Type", "").split(';')[0] != "application/json":
                self.send_json(HTTPStatus.FORBIDDEN, {"error": "Draft review requires same-origin JSON."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 2 <= length <= MAX_BODY:
                    raise HunterDraftError("Draft request must be JSON under 64 KB.")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                operation = {'/api/hunter/review': review_prospect, '/api/hunter/accept-draft': accept_draft, '/api/hunter/reopen-draft': reopen_draft,
                             '/api/hunter/knowledge-plan': knowledge_plan, '/api/hunter/prepare-knowledge': prepare_knowledge,
                             '/api/hunter/inbox/send': send_to_factory, '/api/hunter/inbox/refresh': create_refresh_request,
                             '/api/hunter/inbox/use': use_handoff}[path]
                result = operation(payload)
                self.send_json(HTTPStatus.OK, result)
            except (ValueError, UnicodeDecodeError, KnowledgeLoadingError, KnowledgeCompilerError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except OSError:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Local review receipt could not be saved; nothing was built."})
            return
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
    server = ThreadingHTTPServer(("127.0.0.1", args.port), MissionControlHandler, bind_and_activate=False)
    # Windows SO_REUSEADDR can let an obsolete server keep serving the same port.
    server.allow_reuse_address = False
    if os.name == 'nt':
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.server_bind()
    server.server_activate()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"X-Factory Mission Control ready at {url}", flush=True)
    print("Local draft server: opening it starts no model call. Research, specialist preparation and optional live tests require explicit owner controls. No deployment or production actions.", flush=True)
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
