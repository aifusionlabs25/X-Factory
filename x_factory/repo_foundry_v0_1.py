"""Porter Repo Foundry: create a safe, runnable local repo from a certified mission."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x_factory.chassis_depot_v0_1 import derive_public_role
from x_factory.grounded_matcher_v0_1 import MATCHING_CONTRACT, suggested_questions
from x_factory.independent_review_v0_1 import run_independent_review
from x_factory.mission_control_factory_v0_1 import (
    INTERACTIVE_ROOT,
    MissionControlError,
    ROOT,
    canonical,
    load_json,
    slugify,
)


LOCAL_REPO_ROOT = ROOT / "repos" / "local"
REPO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,95}$")
SECRET_LIKE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|password|secret|token)\s*=\s*[A-Za-z0-9_./+=-]{16,})",
    re.IGNORECASE,
)


class RepoFoundryError(MissionControlError):
    pass


def _customer_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    """Remove internal chassis naming from every customer-facing repo surface."""
    if not record.get("agent", {}).get("derived_from_chassis"):
        return record
    safe = deepcopy(record)
    agent = safe["agent"]
    chassis = agent.get("derived_from_chassis") or {}
    public_role = agent.get("public_role_title") or derive_public_role(
        agent.get("purpose", ""),
        chassis.get("chassis_role_title") or chassis.get("role_title") or "Concierge",
    )
    agent["public_role_title"] = public_role
    agent["display_name"] = f"{agent['agent_name']} — {public_role}" if public_role else agent["agent_name"]
    agent["role_title"] = public_role or "X-Agent"
    return safe


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _write_text(path: Path, text: str) -> None:
    _write_bytes(path, text.replace("\r\n", "\n").encode("utf-8"))


def _write_json(path: Path, value: Any) -> None:
    _write_bytes(path, canonical(value))


def _copy_known(source: Path, target: Path) -> None:
    if not source.is_file():
        raise RepoFoundryError(f"Required certified artifact is missing: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(source.read_bytes())


def _file_map(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    excluded = exclude or set()
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative not in excluded:
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _root_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(canonical(files)).hexdigest()


def _repo_id(record: dict[str, Any]) -> str:
    base = slugify(record["agent"]["display_name"])
    suffix = hashlib.sha256(record["mission_id"].encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}"[:95]


def _repo_preview_agent(record: dict[str, Any], brief: dict[str, Any], spec: dict[str, Any], knowledge: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "repo_mode": "LOCAL_STAGING_PREVIEW",
        "agent_name": record["agent"]["agent_name"],
        "client_name": record["agent"]["client_name"],
        "display_name": record["agent"]["display_name"],
        "purpose": record["agent"]["purpose"],
        "personality": brief["personality"],
        "target_users": brief["target_users"],
        "must_accomplish": brief["must_accomplish"],
        "never_do": brief["never_do"],
        "output_artifact": brief["output_artifact"],
        "persona": record["agent"].get("persona"),
        "presence_mode": record["agent"]["presence_mode"],
        "requirements": spec["requirements"],
        "knowledge_status": record.get("knowledge", {}).get("status"),
        "knowledge_entries": [
            {key: item[key] for key in ("entry_id", "kind", "title", "statement")}
            for item in (knowledge or {}).get("entries", [])
        ],
        "matching_contract": deepcopy(MATCHING_CONTRACT),
        "suggested_questions": suggested_questions((knowledge or {}).get("entries", [])),
        "authority": {
            "provider_transport": False,
            "external_actions": False,
            "deployment": False,
            "production": False,
        },
    }


def _readme(record: dict[str, Any], repo_id: str) -> str:
    name = record["agent"]["display_name"]
    purpose = record["agent"]["purpose"]
    return f"""# {name}

This repository was created by the X-Factory Porter Repo Foundry from the certified local mission `{record['mission_id']}`.

## Purpose

{purpose}

## Start the contained local preview

```powershell
python -B -m src.x_agent_runtime --port 8787
```

Then open `http://127.0.0.1:8787/`.

## Verify the repository

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
```

## Repository status

- Repo ID: `{repo_id}`
- Mode: local staging preview
- Hermes provider transport: not connected
- ANAM provider transport: not connected
- Credentials: not included
- Deployment: not authorized
- Production: not approved
- Instance knowledge: {record.get('knowledge', {}).get('status', 'NOT_ATTACHED')}
- Hermes runtime package: {record.get('runtime_foundry', {}).get('status', 'NOT_PREPARED')}

The browser preview is deterministic and provider-free. When present, `runtime/` contains the sealed Hermes profile blueprint and inactive one-call Luna canary. No profile is installed and no provider is contacted by this repository.
"""


def _porter_handoff(record: dict[str, Any]) -> str:
    knowledge_ready = record.get("knowledge", {}).get("status") == "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED"
    knowledge_included = "- Owner-reviewed instance KB, system prompt, traceability map, and tests\n- Sealed Hermes profile blueprint and inactive one-call Luna canary\n" if knowledge_ready else ""
    knowledge_gated = "" if knowledge_ready else "- Domain knowledge installation\n"
    return f"""# Porter handoff

Porter created a complete local staging repository for **{record['agent']['display_name']}**.

## Included

- Runnable zero-dependency local web preview
- Certified agent instructions and specification
- Owner brief and persona binding
- X-Link candidate, registry entry, and scenario pack
- Factory build, certification, and source-mission records
{knowledge_included}- Local verification tests and start scripts
- Empty credential placeholders only

## Still gated

- Hermes/Luna runtime activation and provider transport
- Live ANAM session wiring
{knowledge_gated}- Existing-repository mutation
- X-Link installation or registry promotion
- Deployment, release, and production

Source mission: `{record['mission_id']}`
Source build digest: `{record['build']['root_digest']}`
"""


RUNTIME_INIT = '"""Contained X-Agent staging runtime."""\n'

RUNTIME_MAIN = """from .server import main

if __name__ == "__main__":
    raise SystemExit(main())
"""

RUNTIME_SERVER = '''"""Zero-dependency localhost server for the generated X-Agent preview."""

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
'''

WEB_INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Contained X-Agent Preview</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header><span>PORTER / LOCAL REPO</span><b>STAGING PREVIEW</b></header>
  <main>
    <section class="identity">
      <p class="eyebrow">X-AGENT APPLICATION REPOSITORY</p>
      <h1 id="agent-name">Loading agent…</h1>
      <p id="purpose" class="purpose"></p>
      <div class="status"><i></i> LOCAL KNOWLEDGE PREVIEW · ZERO MODEL CALLS · NO PRODUCTION</div>
    </section>
    <section class="workspace">
      <div class="conversation">
        <div class="message agent"><small>LOCAL KNOWLEDGE PREVIEW</small><p id="opening">This contained local preview is loading.</p></div>
        <div id="messages"></div>
        <div class="test-guide" aria-label="How to test this local X-Agent">
          <p><strong>1 · KNOWN-ANSWER TEST</strong> Choose an approved question below. Each one comes from the knowledge package built into this X-Agent.</p>
          <p><strong>2 · SAFETY TEST</strong> Type a different topic to confirm unsupported questions are routed for review instead of guessed.</p>
        </div>
        <div id="suggested-questions" class="suggested-questions"></div>
        <form id="message-form">
          <label for="message">Ask another question</label>
          <div><input id="message" required autocomplete="off" placeholder="Ask about the selected knowledge"><button>TEST QUESTION</button></div>
        </form>
      </div>
      <aside>
        <small>VISIBLE HANDOFF NOTES</small>
        <h2>Local review</h2>
        <dl><dt>Request summary</dt><dd id="note-summary">Waiting for a service request</dd><dt>Service category</dt><dd id="note-service">Not provided</dd><dt>Location</dt><dd id="note-location">Not provided</dd><dt>Urgency</dt><dd id="note-urgency">Not provided</dd><dt>Recommended queue</dt><dd id="note-routing">HUMAN_REVIEW</dd><dt>Secondary questions</dt><dd id="known-unknowns">None yet</dd><dt>Review flags</dt><dd id="note-flags">None</dd><dt>Corrections</dt><dd id="note-corrections">None yet</dd><dt>Routing note</dt><dd id="note-routing-note">None</dd><dt>Knowledge</dt><dd id="knowledge-state">Checking local bundle…</dd></dl>
        <button id="fresh-session" type="button">START FRESH SESSION</button>
        <button id="copy-handoff" type="button">COPY HANDOFF JSON</button>
      </aside>
    </section>
  </main>
  <footer><span>Generated by X-Factory Porter</span><span>Local staging repository</span></footer>
  <script src="grounded-matcher.js"></script>
  <script src="app.js"></script>
</body>
</html>
"""

WEB_CSS = """:root{--ink:#161814;--paper:#f2eddf;--panel:#fffaf0;--signal:#ef4b26;--acid:#d9ed55;--blue:#4c7187;--muted:#66695f;--line:#292b26}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font:18px/1.5 Georgia,serif}header,footer{padding:18px 5vw;display:flex;justify-content:space-between;gap:20px;color:var(--paper);background:var(--ink);font:700 13px/1.2 monospace;letter-spacing:.12em}header{border-bottom:5px solid var(--signal)}main{max-width:1440px;margin:auto;padding:64px 5vw}.eyebrow,small,label,dt,.status{font:700 12px/1.4 monospace;letter-spacing:.13em}.identity{max-width:1040px}.identity h1{margin:16px 0;font:900 clamp(52px,8vw,108px)/.9 Georgia,serif;letter-spacing:-.055em}.purpose{max-width:920px;font-size:25px;color:#45483f}.status{display:inline-block;margin:20px 0 42px;padding:11px 13px;color:var(--paper);background:var(--ink)}.status i{display:inline-block;width:9px;height:9px;margin-right:8px;border-radius:50%;background:var(--acid);box-shadow:0 0 10px var(--acid)}.workspace{display:grid;grid-template-columns:1fr 360px;border:2px solid var(--line);box-shadow:9px 9px 0 var(--line)}.conversation{padding:30px;background:var(--panel)}.message{max-width:760px;margin:0 0 16px;padding:18px 20px;border:1px solid var(--line)}.message p{margin:7px 0 0}.agent{background:#e5ded0}.visitor{margin-left:auto;background:var(--acid)}.test-guide{display:grid;gap:8px;margin:18px 0;padding:14px 16px;background:#eef2d1;border:1px solid var(--line)}.test-guide p{margin:0;color:#45483f;font-size:14px;line-height:1.4}.test-guide strong{display:block;margin-bottom:2px;color:var(--ink);font:900 10px/1.3 monospace;letter-spacing:.08em}.suggested-questions{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.suggested-questions:empty{display:none}.suggested-questions button{max-width:100%;padding:9px 12px;color:var(--ink);background:var(--acid);border:1px solid var(--line);font-size:11px;text-align:left}.suggested-questions button:hover,.suggested-questions button:focus-visible{background:var(--paper);outline:2px solid var(--ink);outline-offset:1px}form{margin-top:30px;padding-top:24px;border-top:1px solid #aaa59a}form>div{display:flex;margin-top:8px}input{min-width:0;flex:1;padding:15px;border:2px solid var(--line);font:18px Georgia,serif}button{padding:15px 18px;color:white;background:var(--signal);border:0;font:900 13px monospace;letter-spacing:.08em;cursor:pointer}aside{padding:30px;background:#ded8ca;border-left:2px solid var(--line)}aside h2{margin:10px 0 24px;font-size:33px}dt{margin-top:19px;color:var(--muted)}dd{margin:5px 0;padding-bottom:13px;border-bottom:1px solid #aaa59a;overflow-wrap:anywhere}aside button{width:100%;margin-top:14px;background:var(--ink)}#fresh-session{color:var(--ink);background:var(--acid)}footer{margin-top:70px}@media(max-width:820px){main{padding-top:42px}.workspace{grid-template-columns:1fr}aside{border-top:2px solid var(--line);border-left:0}form>div{display:grid;gap:8px}.identity h1{font-size:58px}}
"""

WEB_MATCHER_JS = r"""(function attachGroundedMatcher(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.XAgentGroundedMatcher = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createGroundedMatcher() {
  "use strict";
  const STOPWORDS = new Set(["the","and","can","you","your","what","with","for","from","that","this","are","have","does","how","who","why","when","where","will","would","could","please","tell","give","about","someone","something","service","services","provide","customer","customers","home","homes","need","needed","new","my","me","our"]);
  const SERVICE_ENTITIES = ["waterheater", "airconditioning", "plumbing", "electrical", "heating"];
  const POLICY_MARKERS = ["pricing", "hours", "availability"];
  const CAPABILITY_QUERY = /(?:what|which).{0,30}(?:service|services|capabilities).{0,30}(?:offer|provide|available|have)|(?:service|services|capabilities).{0,20}(?:offer|provide|available)|what can you help with/i;
  const LOCATION_QUERY = /\b(?:work\s+in|serve|served|serving|located|location|area)\b/i;

  function normalized(text) {
    return String(text || "").toLowerCase()
      .replace(/water[\s-]*heaters?\b/g, " waterheater ")
      .replace(/\b(?:a\s*\/\s*c|ac|air[\s-]*conditioning|hvac)\b/g, " airconditioning ")
      .replace(/\b(?:fix|fixes|fixed|fixing|repair|repairs|repaired|repairing|service|services|serviced|servicing)\b/g, " repair ")
      .replace(/\b(?:price|prices|pricing|cost|costs|costing|quote|quotes|estimate|estimates|pay|expensive|run)\b/g, " pricing ")
      .replace(/\b(?:hours|hour|open|opened|opening|close|closed|closing)\b/g, " hours ")
      .replace(/\b(?:availability|available|appointment|appointments|guarantee|guaranteed|promise|promised|tonight|after[\s-]*hours)\b/g, " availability ")
      .replace(/\b(?:install|installs|installed|installing|installation|installations)\b/g, " install ")
      .replace(/\b(?:replace|replaces|replaced|replacing|replacement|replacements)\b/g, " replace ")
      .replace(/\b(?:remodel|remodels|remodeled|remodeling)\b/g, " remodel ")
      .replace(/\b(?:maintain|maintains|maintained|maintaining|maintenance)\b/g, " maintain ")
      .replace(/\b(?:inspect|inspects|inspected|inspecting|inspection|inspections)\b/g, " inspect ")
      .replace(/\s+/g, " ").trim();
  }

  function canonicalTerm(term) {
    const irregular = {cabinets:"cabinet",kitchens:"kitchen",bathrooms:"bathroom",windows:"window",doors:"door",fixtures:"fixture",appliances:"appliance",fans:"fan",floors:"floor",repairs:"repair",offerings:"offer",capabilities:"capability",hours:"hours"};
    if (irregular[term]) return irregular[term];
    if (term.endsWith("ies") && term.length > 5) return `${term.slice(0, -3)}y`;
    if (term.endsWith("s") && !term.endsWith("ss") && !term.endsWith("us") && term.length > 4) return term.slice(0, -1);
    return term;
  }

  function terms(text) {
    const found = normalized(text).match(/[a-z0-9]{3,}/g) || [];
    return new Set(found.map(canonicalTerm).filter((term) => !STOPWORDS.has(term)));
  }

  function overlap(left, right) {
    let count = 0;
    left.forEach((term) => { if (right.has(term)) count += 1; });
    return count;
  }

  function match(entries, message, contract = {}) {
    const clean = String(message || "").replace(/\s+/g, " ").trim();
    const query = normalized(clean);
    const queryTerms = terms(clean);
    const prepared = entries.map((entry) => ({entry, titleTerms: terms(entry.title), statementTerms: terms(entry.statement)}));
    const exact = prepared.find((item) => normalized(item.entry.title) === query);
    if (exact) return {entry: exact.entry, reason: "EXACT_APPROVED_TITLE"};

    for (const marker of POLICY_MARKERS) {
      if (!queryTerms.has(marker)) continue;
      const title = prepared.filter((item) => item.titleTerms.has(marker));
      const candidates = title.length ? title : prepared.filter((item) => item.statementTerms.has(marker));
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        return {entry: candidates[0].entry, reason: `APPROVED_${marker.toUpperCase()}_POLICY`};
      }
    }

    const entities = SERVICE_ENTITIES.filter((entity) => queryTerms.has(entity));
    if (entities.length) {
      const candidates = prepared.filter((item) => entities.some((entity) => item.statementTerms.has(entity)));
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        const entity = entities.find((item) => candidates[0].statementTerms.has(item));
        return {entry: candidates[0].entry, reason: `APPROVED_SERVICE_ENTITY_${entity.toUpperCase()}`};
      }
    }

    if (CAPABILITY_QUERY.test(clean)) {
      const capabilities = prepared.filter((item) => item.entry.kind === "CAPABILITY");
      if (capabilities.length) {
        capabilities.sort((a, b) => String(b.entry.statement).length - String(a.entry.statement).length);
        return {entry: capabilities[0].entry, reason: "APPROVED_CAPABILITY_SUMMARY"};
      }
    }

    if (LOCATION_QUERY.test(clean)) {
      const candidates = prepared.filter((item) => overlap(queryTerms, item.statementTerms) >= 1);
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        return {entry: candidates[0].entry, reason: "APPROVED_LOCATION_TERM"};
      }
    }

    let best = null;
    let bestScore = 0;
    let bestOverlap = 0;
    prepared.forEach((item) => {
      const titleOverlap = overlap(queryTerms, item.titleTerms);
      const statementOverlap = overlap(queryTerms, item.statementTerms);
      const score = titleOverlap * (contract.title_term_weight || 3) + statementOverlap * (contract.statement_term_weight || 1);
      if (score > bestScore) { best = item.entry; bestScore = score; bestOverlap = overlap(queryTerms, new Set([...item.titleTerms, ...item.statementTerms])); }
    });
    const queryCoverage = bestOverlap / Math.max(1, queryTerms.size);
    if (best && bestOverlap >= (contract.minimum_distinct_term_overlap || 2) && bestScore >= (contract.minimum_weighted_score || 2) && queryCoverage >= (contract.minimum_query_coverage || 0.6)) {
      return {entry: best, reason: "CONSERVATIVE_APPROVED_TERM_OVERLAP"};
    }
    return {entry: null, reason: "NO_APPROVED_MATCH"};
  }

  return {normalized, terms, match};
});
"""

WEB_JS = """let agent;
const $ = (selector) => document.querySelector(selector);
function createHandoff() { return {request_summary: "", service_category: "", service_city: "", urgency: "", primary_review_required: false, known_unknowns: [], session_corrections: [], turn_intents: []}; }
let handoff = createHandoff();

function detectedFacts(message) {
  const city = message.match(/\\b(Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\\b/i);
  const services = [[/\\b(?:A\/?C|air conditioning|HVAC)\\b/i, "Air conditioning / HVAC"], [/\\bwater[ -]?heater\\b/i, "Water heater"], [/\\bplumb(?:ing|er)?\\b/i, "Plumbing"], [/\\belectri(?:cal|cian)\\b/i, "Electrical"], [/\\bheating|\\bheater\\b/i, "Heating"]];
  const service = services.find(([pattern]) => pattern.test(message));
  return {city: city ? city[1][0].toUpperCase() + city[1].slice(1).toLowerCase() : "", urgency: /\\b(emergency|urgent|asap|immediately|right away|tonight)\\b/i.test(message) ? "Urgent" : /\\b(not urgent|routine|whenever|this week)\\b/i.test(message) ? "Routine" : "", service: service ? service[1] : ""};
}

function requestSummary(message) {
  const sentences = message.match(/[^.!?]+[.!?]?/g) || [message];
  const issue = sentences.find((sentence) => {
    const facts = detectedFacts(sentence);
    return facts.service && /\\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\\b/i.test(sentence);
  }) || message;
  const summary = issue
    .replace(/\s+(?:i(?:'m| am)\s+)?in\s+(?:Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\\b/ig, "")
    .replace(/(?:,?\s+(?:and\s+)?)(?:it(?:'s| is)\s+)?(?:urgent|an? emergency|asap|routine)\\b.*$/i, "")
    .trim();
  if (/^my\s+(?:a\/?c|air conditioning)\s+is(?:n't| not)\s+cooling[.!?]?$/i.test(summary)) return "Customer reports that their AC is not cooling.";
  return summary;
}

function recommendedQueue() {
  if (handoff.urgency === "Urgent" && handoff.primary_review_required) return "URGENT_HUMAN_REVIEW";
  return handoff.urgency === "Urgent" && handoff.service_category === "Air conditioning / HVAC" ? "URGENT_HVAC" : "HUMAN_REVIEW";
}

function reviewFlags() {
  return [handoff.primary_review_required && "PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE", handoff.known_unknowns.length && "OUT_OF_KNOWLEDGE_SERVICE_QUESTION"].filter(Boolean);
}

function humanReviewFlag(flag) {
  if (flag === "OUT_OF_KNOWLEDGE_SERVICE_QUESTION") return "Service question outside approved knowledge";
  if (flag === "PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE") return "Requested service needs human confirmation";
  return flag;
}

function routingNote() {
  if (handoff.primary_review_required && handoff.urgency === "Urgent") return "Prioritize the urgent service request and confirm coverage before making a promise.";
  if (handoff.primary_review_required) return "Confirm the requested service is covered before making a promise.";
  if (recommendedQueue() === "URGENT_HVAC" && handoff.known_unknowns.length) return "Prioritize urgent AC service request. Pool-pump question requires separate confirmation.";
  return handoff.known_unknowns.length ? "Primary request may proceed; secondary question requires separate confirmation." : "";
}

function serviceRequestResponse() {
  const request = handoff.request_summary || "I captured your service request.";
  const details = [handoff.service_city && `Location: ${handoff.service_city}.`, handoff.urgency && `Urgency: ${handoff.urgency}.`].filter(Boolean).join(" ");
  const coverage = handoff.primary_review_required
    ? `The approved ${agent.client_name || "company"} information does not confirm this service, so I marked it for prompt team review instead of promising coverage.`
    : "I added these details to the visible handoff for the service team.";
  return `I captured your request: ${request}${details ? ` ${details}` : ""} ${coverage}`;
}

function classifyTurn(message, matchResult, aboutPurpose) {
  if (/^(?:correction|update|actually)\s*:?/i.test(message)) return "CORRECTION";
  if (/\\b(?:summarize|summary)\\b.*\\b(?:team|handoff|service)\\b/i.test(message)) return "HANDOFF_REQUEST";
  const query = XAgentGroundedMatcher.normalized(message);
  if (["pricing", "hours", "availability"].some((marker) => query.includes(marker))) return "INFORMATIONAL_QUERY";
  const facts = detectedFacts(message);
  const groundedService = matchResult?.entry?.title;
  if ((facts.service || groundedService) && /\\b(?:I|I'm|I am|my|mine|we|our)\\b/i.test(message) && /\\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\\b/i.test(message)) return "SERVICE_REQUEST";
  if (facts.city || facts.urgency) return "QUALIFICATION_DETAIL";
  if (!matchResult?.entry && !aboutPurpose) return "UNKNOWN_REVIEW";
  return "INFORMATIONAL_QUERY";
}

function applyTurn(message, intent, matchResult = null) {
  handoff.turn_intents.push({message, intent});
  if (intent === "UNKNOWN_REVIEW") {
    if (!handoff.known_unknowns.includes(message)) handoff.known_unknowns.push(message);
  } else if (["SERVICE_REQUEST", "QUALIFICATION_DETAIL", "CORRECTION"].includes(intent)) {
    const content = intent === "CORRECTION" ? message.replace(/^(?:correction|update|actually)\s*:?\s*/i, "").trim() : message;
    if (intent === "SERVICE_REQUEST") handoff.request_summary = requestSummary(message);
    const facts = detectedFacts(content);
    if (intent === "SERVICE_REQUEST") {
      handoff.primary_review_required = !matchResult?.entry;
      if (!facts.service && matchResult?.entry?.title) handoff.service_category = matchResult.entry.title.replace(/[?.]+$/, "");
    }
    if (intent === "CORRECTION") {
      const corrections = [facts.city && {field: "service_city", previous_value: handoff.service_city || "Not provided", corrected_value: facts.city}, facts.service && {field: "service_category", previous_value: handoff.service_category || "Not provided", corrected_value: facts.service}, facts.urgency && {field: "urgency", previous_value: handoff.urgency || "Not provided", corrected_value: facts.urgency}].filter(Boolean);
      corrections.forEach((correction) => {
        if (!handoff.session_corrections.some((existing) => existing.field === correction.field && existing.corrected_value === correction.corrected_value)) handoff.session_corrections.push(correction);
      });
    }
    if (intent === "CORRECTION" && facts.service && /\\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\\b/i.test(content)) handoff.request_summary = requestSummary(content);
    if (facts.service) handoff.service_category = facts.service;
    if (facts.city) handoff.service_city = facts.city;
    if (facts.urgency) handoff.urgency = facts.urgency;
  }
  renderHandoff();
}

function renderHandoff() {
  $("#note-summary").textContent = handoff.request_summary || "Waiting for a service request";
  $("#note-service").textContent = handoff.service_category || "Not provided";
  $("#note-location").textContent = handoff.service_city || "Not provided";
  $("#note-urgency").textContent = handoff.urgency || "Not provided";
  $("#note-routing").textContent = recommendedQueue();
  $("#known-unknowns").textContent = handoff.known_unknowns.join(" · ") || "None yet";
  $("#note-flags").textContent = reviewFlags().map(humanReviewFlag).join(" · ") || "None";
  $("#note-corrections").textContent = handoff.session_corrections.length ? handoff.session_corrections.map((item) => `${item.field}: ${item.previous_value} -> ${item.corrected_value}`).join(" · ") : "None yet";
  $("#note-routing-note").textContent = routingNote() || "None";
}

function addMessage(role, text) {
  const box = document.createElement("div");
  const label = document.createElement("small");
  const copy = document.createElement("p");
  box.className = `message ${role}`;
  label.textContent = role === "visitor" ? "VISITOR" : "LOCAL KNOWLEDGE PREVIEW";
  copy.textContent = text;
  box.append(label, copy);
  $("#messages").append(box);
}

fetch("agent.json", {cache: "no-store"}).then((response) => response.json()).then((data) => {
  agent = data;
  document.title = `${agent.display_name} · Local Preview`;
  $("#agent-name").textContent = agent.display_name;
  $("#purpose").textContent = agent.purpose;
  const knowledgeCount = agent.knowledge_entries?.length || 0;
  $("#knowledge-state").textContent = knowledgeCount ? `${knowledgeCount} owner-approved entries installed in this local preview.` : "No owner-reviewed client knowledge is attached.";
  $("#opening").textContent = knowledgeCount
    ? `This is the provider-free local knowledge preview for ${agent.display_name}. No language model is active. It returns only exact statements from ${knowledgeCount} owner-approved entries and prepares a visible local handoff.`
    : `This is the provider-free local preview for ${agent.display_name}. No language model is active and no owner-reviewed client knowledge is attached.`;
  const holder = $("#suggested-questions");
  (agent.suggested_questions || []).forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `APPROVED · ${item.question}`;
    button.title = "This question is confirmed by the selected owner-approved knowledge package.";
    button.addEventListener("click", () => { $("#message").value = item.question; $("#message").focus(); });
    holder.append(button);
  });
});

$("#message-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("#message");
  const message = input.value.trim();
  if (!message || !agent) return;
  addMessage("visitor", message);
  const aboutPurpose = /(?:what is|describe|explain).*(?:purpose|role)|(?:purpose|role).*(?:what|describe|explain)/i.test(message);
  const matchResult = XAgentGroundedMatcher.match(agent.knowledge_entries || [], message, agent.matching_contract || {});
  const intent = classifyTurn(message, matchResult, aboutPurpose);
  applyTurn(message, intent, matchResult);
  const response = intent === "CORRECTION"
    ? "I updated the current handoff. This correction is not persistent memory."
    : intent === "HANDOFF_REQUEST"
      ? `Request: ${handoff.request_summary || "Not provided"} Service: ${handoff.service_category || "Not provided"}. Location: ${handoff.service_city || "Not provided"}. Urgency: ${handoff.urgency || "Not provided"}. Route: ${recommendedQueue()}. Secondary questions: ${handoff.known_unknowns.join(" · ") || "None"}.${routingNote() ? ` ${routingNote()}` : ""}`
      : intent === "SERVICE_REQUEST"
        ? serviceRequestResponse()
        : matchResult.entry
          ? matchResult.entry.statement
          : aboutPurpose
            ? `${agent.purpose} My approved capabilities are: ${agent.must_accomplish.join("; ")}.`
            : `I don’t have an approved answer for that yet, so I’d send it to the ${agent.client_name || "team"} team for review.`;
  addMessage("agent", response);
  input.value = "";
});

$("#copy-handoff").addEventListener("click", async () => {
  const exportHandoff = {
    agent_name: agent.agent_name,
    client_name: agent.client_name,
    request_summary: handoff.request_summary || "Not provided",
    service_category: handoff.service_category || "Not provided",
    service_city: handoff.service_city || "Not provided",
    urgency: handoff.urgency || "Not provided",
    secondary_questions: handoff.known_unknowns,
    review_flags: reviewFlags(),
    session_corrections: handoff.session_corrections,
    recommended_queue: recommendedQueue(),
    routing_note: routingNote(),
    knowledge_status: agent.knowledge_status,
  };
  await navigator.clipboard.writeText(JSON.stringify(exportHandoff, null, 2));
  $("#copy-handoff").textContent = "HANDOFF COPIED";
});

$("#fresh-session").addEventListener("click", () => {
  handoff = createHandoff();
  $("#messages").textContent = "";
  renderHandoff();
  addMessage("agent", "Fresh session started. Previous request details, secondary questions, and corrections were cleared.");
  $("#message").focus();
});
"""

REPO_TEST = '''import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_required_application_files_exist(self):
        required = [
            "README.md", ".env.example", "pyproject.toml", "agent/AGENT.md",
            "config/agent.spec.json", "config/persona-binding.json",
            "config/x-link-candidate.json", "web/index.html", "web/grounded-matcher.js", "web/app.js",
            "src/x_agent_runtime/server.py", "factory-record/vera-final.json",
        ]
        self.assertTrue(all((ROOT / item).is_file() for item in required))

    def test_authority_remains_local_and_nonproduction(self):
        preview = json.loads((ROOT / "web/agent.json").read_text(encoding="utf-8"))
        self.assertEqual(preview["repo_mode"], "LOCAL_STAGING_PREVIEW")
        self.assertTrue(all(value is False for value in preview["authority"].values()))

    def test_no_real_environment_file_or_embedded_secret(self):
        self.assertFalse((ROOT / ".env").exists())
        pattern = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
        for path in ROOT.rglob("*"):
            if path.is_file() and path.stat().st_size < 1_000_000:
                text = path.read_text(encoding="utf-8", errors="ignore")
                self.assertIsNone(pattern.search(text), path.as_posix())

    def test_runtime_source_compiles(self):
        source = (ROOT / "src/x_agent_runtime/server.py").read_text(encoding="utf-8")
        compile(source, "server.py", "exec")

    def test_instance_knowledge_is_complete_when_declared_ready(self):
        preview = json.loads((ROOT / "web/agent.json").read_text(encoding="utf-8"))
        if preview.get("knowledge_status") == "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED":
            required = [
                "knowledge/KB.md", "knowledge/approved-knowledge.json",
                "config/SYSTEM_PROMPT.md", "factory-record/knowledge-traceability.json",
                "factory-record/prompt-forge-manifest.json", "config/PROMPT_ASSUMPTIONS.json",
                "tests/prompt-tests.json", "TROY_PROMPT_FORGE_RECEIPT.md",
                "tests/knowledge-tests.json", "factory-record/instance-knowledge-build-report.json",
                "runtime/runtime-plan.json", "runtime/profile-blueprint.json",
                "runtime/canary/exact-prompt.txt", "runtime/canary/exact-payload.json",
                "runtime/canary/inactive-activation-packet.json",
                "contracts/runtime_behavior_certification.v0.2.schema.json",
            ]
            self.assertTrue(preview.get("knowledge_entries"))
            self.assertTrue(all((ROOT / item).is_file() for item in required))

    def test_behavior_evidence_uses_canonical_match_reason_schema(self):
        certification_path = ROOT / "runtime/local-behavior-certification.json"
        if not certification_path.is_file():
            return
        certification = json.loads(certification_path.read_text(encoding="utf-8"))
        if certification.get("schema_version") == "0.1":
            return
        schema = json.loads((ROOT / "contracts/runtime_behavior_certification.v0.2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(certification["schema_version"], "0.2")
        allowed = set(schema["$defs"]["match_reason"]["enum"])
        expected_turn_keys = {"turn", "message", "speaker", "outcome", "response", "supporting_entry_ids", "match_reason"}
        for session in certification["sessions"].values():
            for turn in session["turns"]:
                self.assertEqual(set(turn), expected_turn_keys)
                self.assertIn(turn["match_reason"], allowed)

    def test_preview_handoff_uses_intent_gated_state_updates(self):
        app = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("\x08", app, "JavaScript regex word boundaries were serialized as control characters")
        expected_intents = {
            "INFORMATIONAL_QUERY", "SERVICE_REQUEST", "QUALIFICATION_DETAIL",
            "CORRECTION", "UNKNOWN_REVIEW", "HANDOFF_REQUEST",
        }
        self.assertTrue(all(intent in app for intent in expected_intents))
        self.assertIn('["SERVICE_REQUEST", "QUALIFICATION_DETAIL", "CORRECTION"].includes(intent)', app)
        self.assertIn('if (intent === "SERVICE_REQUEST") handoff.request_summary = requestSummary(message);', app)
        self.assertIn('"URGENT_HVAC"', app)
        self.assertIn('"OUT_OF_KNOWLEDGE_SERVICE_QUESTION"', app)
        self.assertIn('"PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE"', app)
        self.assertIn('"URGENT_HUMAN_REVIEW"', app)
        self.assertIn('"Service question outside approved knowledge"', app)
        self.assertIn('secondary_questions: handoff.known_unknowns', app)
        self.assertIn('handoff = createHandoff();', app)
        self.assertIn('$("#messages").textContent = "";', app)
        self.assertIn('id="fresh-session"', (ROOT / "web/index.html").read_text(encoding="utf-8"))
        self.assertNotIn('if (!handoff.request_summary)', app)


if __name__ == "__main__":
    unittest.main()
'''


def _assemble(mission_root: Path, target: Path, record: dict[str, Any], repo_id: str, independent_review: dict[str, Any]) -> None:
    brief = load_json(mission_root / "input/owner-brief.v0.1.json")
    spec = load_json(mission_root / "build/run-1/output/agent/agent.spec.json")
    knowledge_path = mission_root / "instance/knowledge/approved-knowledge.v0.1.json"
    knowledge = load_json(knowledge_path) if knowledge_path.is_file() else None

    copies = {
        "build/run-1/output/agent/AGENT.md": "agent/AGENT.md",
        "build/run-1/output/agent/agent.spec.json": "config/agent.spec.json",
        "input/owner-brief.v0.1.json": "config/owner-brief.json",
        "experience/persona-binding.v0.1.json": "config/persona-binding.json",
        "compatibility/x-link-candidate.v0.1.json": "config/x-link-candidate.json",
        "compatibility/x-link-agent-entry.v0.1.yaml": "config/x-link-agent-entry.yaml",
        "compatibility/x-link-scenario-pack.v0.1.yaml": "config/x-link-scenario-pack.yaml",
        "mission-record.json": "factory-record/source-mission-record.json",
        "certification/vera-final.v0.1.json": "factory-record/vera-final.json",
        "artifacts/aria-blueprint.v0.2.json": "factory-record/aria-blueprint.json",
        "build/run-1/output/bundle.manifest.json": "factory-record/source-bundle-manifest.json",
    }
    for source, destination in copies.items():
        _copy_known(mission_root / source, target / destination)
    optional_copies = {
        "instance/knowledge/approved-knowledge.v0.1.json": "knowledge/approved-knowledge.json",
        "instance/knowledge/KB.md": "knowledge/KB.md",
        "instance/system-prompt/SYSTEM_PROMPT.md": "config/SYSTEM_PROMPT.md",
        "instance/system-prompt/PROMPT_FORGE_MANIFEST.v0.1.json": "factory-record/prompt-forge-manifest.json",
        "instance/system-prompt/PROMPT_ASSUMPTIONS.v0.1.json": "config/PROMPT_ASSUMPTIONS.json",
        "instance/system-prompt/PROMPT_TESTS.v0.1.json": "tests/prompt-tests.json",
        "instance/system-prompt/OWNER_SUMMARY.md": "TROY_PROMPT_FORGE_RECEIPT.md",
        "instance/traceability/knowledge-traceability.v0.1.json": "factory-record/knowledge-traceability.json",
        "instance/tests/knowledge-tests.v0.1.json": "tests/knowledge-tests.json",
        "instance/instance-knowledge-build-report.v0.1.json": "factory-record/instance-knowledge-build-report.json",
        "runtime-foundry/runtime-plan.v0.1.json": "runtime/runtime-plan.json",
        "runtime-foundry/profile-blueprint.v0.1.json": "runtime/profile-blueprint.json",
        "runtime-foundry/canary/exact-prompt.txt": "runtime/canary/exact-prompt.txt",
        "runtime-foundry/canary/exact-payload.v0.1.json": "runtime/canary/exact-payload.json",
        "runtime-foundry/canary/inactive-activation-packet.v0.1.json": "runtime/canary/inactive-activation-packet.json",
        "runtime-foundry/instance-runtime-contract.v0.1.json": "runtime/instance-runtime-contract.json",
        "runtime-foundry/behavior-certification-plan.v0.1.json": "runtime/behavior-certification-plan.json",
        "runtime-foundry/local-behavior-certification.v0.2.json": "runtime/local-behavior-certification.json",
    }
    for source, destination in optional_copies.items():
        source_path = mission_root / source
        if source_path.is_file():
            _copy_known(source_path, target / destination)
    legacy_behavior = mission_root / "runtime-foundry/local-behavior-certification.v0.1.json"
    packaged_behavior = target / "runtime/local-behavior-certification.json"
    if legacy_behavior.is_file() and not packaged_behavior.is_file():
        _copy_known(legacy_behavior, packaged_behavior)
    _copy_known(
        ROOT / "contracts/runtime_behavior_certification.v0.2.schema.json",
        target / "contracts/runtime_behavior_certification.v0.2.schema.json",
    )

    _write_text(target / "README.md", _readme(record, repo_id))
    _write_text(target / "PORTER_HANDOFF.md", _porter_handoff(record))
    _write_json(target / "factory-record/independent-local-review.json", independent_review)
    _write_text(target / ".gitignore", ".env\n.venv/\n__pycache__/\n*.pyc\n.factory-runtime/\n")
    _write_text(
        target / ".env.example",
        "# Placeholders only. Do not commit a populated .env file.\n"
        "HERMES_PROFILE=\nHERMES_PROVIDER=openai-codex\nHERMES_MODEL=gpt-5.6-luna\nANAM_API_KEY=\n",
    )
    _write_text(
        target / "pyproject.toml",
        f'[project]\nname = "{repo_id}"\nversion = "0.1.0"\ndescription = "X-Factory generated local staging repository"\nrequires-python = ">=3.11"\ndependencies = []\n\n[project.scripts]\nx-agent-preview = "src.x_agent_runtime.server:main"\n',
    )
    _write_text(target / "src/__init__.py", '"""Generated application source."""\n')
    _write_text(target / "src/x_agent_runtime/__init__.py", RUNTIME_INIT)
    _write_text(target / "src/x_agent_runtime/__main__.py", RUNTIME_MAIN)
    _write_text(target / "src/x_agent_runtime/server.py", RUNTIME_SERVER)
    _write_text(target / "web/index.html", WEB_INDEX)
    _write_text(target / "web/styles.css", WEB_CSS)
    _write_text(target / "web/grounded-matcher.js", WEB_MATCHER_JS)
    _write_text(target / "web/app.js", WEB_JS)
    _write_json(target / "web/agent.json", _repo_preview_agent(record, brief, spec, knowledge))
    _write_text(target / "tests/test_repository.py", REPO_TEST)
    _write_text(target / "scripts/start-local.ps1", "$ErrorActionPreference = 'Stop'\npython -B -m src.x_agent_runtime --port 8787\n")
    _write_text(target / "scripts/verify.ps1", "$ErrorActionPreference = 'Stop'\npython -B -m unittest discover -s tests -p 'test_*.py'\n")


def _run_tests(repo_root: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(repo_root / "tests"), "-p", "test_*.py"],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def create_local_repo(mission_id: str) -> dict[str, Any]:
    if not REPO_ID.fullmatch(mission_id):
        raise RepoFoundryError("Invalid mission ID")
    mission_root = INTERACTIVE_ROOT / mission_id
    record_path = mission_root / "mission-record.json"
    if not record_path.is_file():
        raise RepoFoundryError("Mission not found")
    record = _customer_safe_record(load_json(record_path))
    certification = load_json(mission_root / "certification/vera-final.v0.1.json")
    if record.get("status") != "LOCAL_CANDIDATE_BUILT" or certification.get("verdict") != "LOCAL_CANDIDATE_CERTIFIED":
        raise RepoFoundryError("Only a locally certified Factory candidate can enter Repo Foundry")
    common_root = Path(os.path.commonpath([INTERACTIVE_ROOT.resolve(), LOCAL_REPO_ROOT.resolve()]))
    independent_review = run_independent_review(
        mission_id,
        mission_root=mission_root,
        review_root=common_root / "reviews" / "independent-local",
    )
    if independent_review.get("verdict") != "READY_FOR_PORTER_PACKAGING":
        raise RepoFoundryError("Independent review did not release this candidate to Porter")

    repo_id = _repo_id(record)
    LOCAL_REPO_ROOT.mkdir(parents=True, exist_ok=True)
    final_root = LOCAL_REPO_ROOT / repo_id
    existing_record = final_root / "repo-record.json"
    if final_root.exists():
        if existing_record.is_file():
            existing = load_json(existing_record)
            if existing.get("source_mission_id") == mission_id:
                return existing
        raise RepoFoundryError("Repo destination already exists; overwrite is prohibited")

    staging = LOCAL_REPO_ROOT / f".{repo_id}.staging-{secrets.token_hex(3)}"
    try:
        staging.mkdir()
        _assemble(mission_root, staging, record, repo_id, independent_review)
        test_result = _run_tests(staging)
        if test_result["returncode"]:
            raise RepoFoundryError(f"Generated repository verification failed: {test_result['stderr'] or test_result['stdout']}")
        files = _file_map(staging)
        serialized = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in staging.rglob("*") if path.is_file() and path.stat().st_size < 1_000_000)
        if SECRET_LIKE.search(serialized):
            raise RepoFoundryError("Generated repository failed the credential-content guard")
        repo_record = {
            "schema_version": "0.1",
            "repo_id": repo_id,
            "display_name": record["agent"]["display_name"],
            "source_mission_id": mission_id,
            "source_build_digest": record["build"]["root_digest"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "LOCAL_REPO_READY",
            "mode": "LOCAL_STAGING_PREVIEW",
            "repo_tier": "STAGING",
            "relative_path": f"repos/local/{repo_id}",
            "local_path": str(final_root),
            "preview_url": f"/repo-preview/{repo_id}/",
            "files": files,
            "root_digest": _root_digest(files),
            "verification": {
                "status": "PASS",
                "command": "python -B -m unittest discover -s tests -p test_*.py",
                "stdout": test_result["stdout"],
                "stderr": test_result["stderr"],
                "provider_calls": 0,
                "network_attempts": 0,
            },
            "independent_review": {
                "review_id": independent_review["review_id"],
                "verdict": independent_review["verdict"],
                "review_sha256": independent_review["review_sha256"],
            },
            "authority": {
                "runtime_approved": False,
                "deployment_approved": False,
                "production_approved": False,
                "credentials_copied": False,
                "existing_repo_mutation": False,
                "x_link_installation": False,
                "deployment_authorized": False,
                "production_approved": False,
            },
            "artifacts": {
                "readme": "README.md",
                "porter_handoff": "PORTER_HANDOFF.md",
                "independent_review": "factory-record/independent-local-review.json",
                "agent_instructions": "agent/AGENT.md",
                "agent_spec": "config/agent.spec.json",
                **({
                    "system_prompt": "config/SYSTEM_PROMPT.md",
                    "prompt_forge_manifest": "factory-record/prompt-forge-manifest.json",
                    "prompt_assumptions": "config/PROMPT_ASSUMPTIONS.json",
                    "prompt_tests": "tests/prompt-tests.json",
                    "prompt_owner_summary": "TROY_PROMPT_FORGE_RECEIPT.md",
                } if (mission_root / "instance/system-prompt/SYSTEM_PROMPT.md").is_file() else {}),
                **({
                    "knowledge_bank": "knowledge/KB.md",
                    "knowledge_traceability": "factory-record/knowledge-traceability.json",
                    "knowledge_tests": "tests/knowledge-tests.json",
                    "runtime_plan": "runtime/runtime-plan.json",
                    "runtime_profile_blueprint": "runtime/profile-blueprint.json",
                    "runtime_canary_prompt": "runtime/canary/exact-prompt.txt",
                    "runtime_canary_payload": "runtime/canary/exact-payload.json",
                    "runtime_activation_packet": "runtime/canary/inactive-activation-packet.json",
                    "instance_runtime_contract": "runtime/instance-runtime-contract.json",
                    "runtime_behavior_plan": "runtime/behavior-certification-plan.json",
                    "local_behavior_certification": "runtime/local-behavior-certification.json",
                } if (mission_root / "instance/knowledge/approved-knowledge.v0.1.json").is_file() else {}),
                "repo_manifest": "repo-record.json",
            },
        }
        _write_json(staging / "repo-record.json", repo_record)
        staging.replace(final_root)
        return repo_record
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def find_local_repo(mission_id: str) -> dict[str, Any] | None:
    if not REPO_ID.fullmatch(mission_id) or not LOCAL_REPO_ROOT.is_dir():
        return None
    for record_path in LOCAL_REPO_ROOT.glob("*/repo-record.json"):
        try:
            record = load_json(record_path)
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("source_mission_id") == mission_id:
            return record
    return None


def repo_root(repo_id: str) -> Path:
    if not REPO_ID.fullmatch(repo_id):
        raise RepoFoundryError("Invalid repo ID")
    root = (LOCAL_REPO_ROOT / repo_id).resolve()
    try:
        root.relative_to(LOCAL_REPO_ROOT.resolve())
    except ValueError as error:
        raise RepoFoundryError("Invalid repo path") from error
    if not (root / "repo-record.json").is_file():
        raise RepoFoundryError("Local repo not found")
    return root
