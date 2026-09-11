/*
 * Hosted Mission Control modes.
 *
 * The normal hosted URL is deliberately read-only. An explicit
 * ?mode=ephemeral-test URL enables a browser-only rehearsal of the owner
 * journey. It never writes to Vercel, GitHub, ANAM, Hermes, or a provider;
 * all state lives in this tab and disappears on refresh.
 */
(() => {
  const query = new URLSearchParams(location.search);
  const TEST_MODE = query.get("mode") === "ephemeral-test";
  const originalFetch = window.fetch.bind(window);
  const chassis = {
    schema_version: "0.1",
    chassis_id: "operational-qa-concierge",
    version: "1.0.0",
    status: "LOCAL_VALIDATED_CHASSIS",
    role_title: "Operational QA Concierge",
    summary: "A reusable concierge foundation that answers approved questions, qualifies a request, maintains visible notes, and prepares a structured human-review handoff.",
    source: { mission_id: "draft-operational-qa-concierge-20260821-064103-a3e197", identity_removed: true, anam_binding_removed: true },
    modules: ["CMP-BOUNDARY-FIRST-CONCIERGE", "CMP-DETERMINISTIC-CANDIDATE-BUNDLE", "CMP-STRUCTURED-SESSION-SNAPSHOT", "CMP-APPROVED-KNOWLEDGE-ANSWERS", "CMP-HUMAN-REVIEW-HANDOFF", "CMP-ANAM-PRESENCE-SHELL"],
    configurable_slots: ["x_agent_name", "client_name", "personality", "target_users", "client_context", "knowledge_package", "integration_permissions"],
    authority: { provider_calls: 0, client_data_attached: false, credentials_attached: false, deployment_authorized: false, production_approved: false, claim: "Hosted reference of a locally validated role chassis" },
    knowledge_contract: { runtime_knowledge_included: false, ingestion_status: "COMMISSIONING_INPUT_REQUIRED", unsupported_fact_policy: "ESCALATE_WITHOUT_GUESSING" },
    evaluation: { final_instance_recertification_required: true, client_knowledge_tests_required: true, identity_consistency_tests_required: true }
  };
  const roles = [
    { role_id: "reception-intake", chassis_id: "role-reception-intake", title: "Reception & Intake", summary: "Welcome a visitor, understand the reason for contact, and prepare a useful first-contact brief.", boundaries: ["Promise that a visitor has been connected to staff"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "lead-qualification", chassis_id: "role-lead-qualification", title: "Lead Qualification", summary: "Understand a prospective customer's need and prepare an evidence-based sales qualification brief.", boundaries: ["Invent lead scores or assume purchase intent"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "support-triage", chassis_id: "role-support-triage", title: "Support Triage", summary: "Gather symptoms and impact, offer approved guidance, and prepare a support case for review.", boundaries: ["Invent a diagnosis or guarantee a fix"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "client-onboarding", chassis_id: "role-client-onboarding", title: "Client Onboarding", summary: "Guide a new client through an approved checklist and identify the next incomplete step.", boundaries: ["Claim an account was provisioned"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "product-service-guidance", chassis_id: "role-product-service-guidance", title: "Product & Service Guidance", summary: "Compare approved options against the customer's stated needs without inventing specifications or claims.", boundaries: ["Invent compatibility or prices"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "internal-knowledge", chassis_id: "role-internal-knowledge", title: "Internal Knowledge", summary: "Help staff find approved internal guidance and identify unanswered or conflicting policy questions.", boundaries: ["Expose unapproved personnel information"], capability_limits: ["Read-only hosted preview"] },
    { role_id: "operational-concierge", chassis_id: "operational-qa-concierge", title: "Operational Concierge", summary: "Answer approved questions, qualify service requests, preserve corrections, and prepare a staff handoff.", boundaries: ["Invent business facts", "Promise availability or perform external actions"], capability_limits: ["No live booking, messaging, account changes, payments, or system integrations"] }
  ];
  const modules = {
    included: chassis.modules.map((module_id) => ({ module_id, name: module_id.replace(/^CMP-/, "").replaceAll("-", " "), category: "core", status: "INCLUDED_LOCKED" })),
    optional: [
      { module_id: "CMP-CLIENT-KNOWLEDGE-PACK", name: "Approved client knowledge pack", category: "knowledge-option", description: "Build one immutable, owner-reviewed local package into a named candidate.", requires_knowledge_package: true, status: "AVAILABLE_FOR_COMMISSIONING" },
      { module_id: "CMP-APPOINTMENT-REQUEST-PACKET", name: "Appointment request packet", category: "handoff-option", description: "Collect preferred timing for staff review without booking or promising availability.", status: "AVAILABLE_FOR_COMMISSIONING" },
      { module_id: "CMP-LEAD-QUALIFICATION-SCORECARD", name: "Lead qualification scorecard", category: "qualification-option", description: "Structure explicit fit signals for human review.", status: "AVAILABLE_FOR_COMMISSIONING" }
    ],
    locked: [{ module_id: "CMP-EXTERNAL-ACTION-RUNTIME", name: "External action runtime", status: "PROHIBITED_IN_CONTAINED_FACTORY", reason: "Sending, booking, provider mutation, and production actions require a separately governed stage." }]
  };
  const memory = { ideas: new Map(), projects: new Map(), sessions: new Map(), missions: new Map() };
  const payload = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  const bodyOf = (init) => { try { return JSON.parse(init?.body || "{}"); } catch (_) { return {}; } };
  const hash = (value) => { let h = 2166136261; for (const c of String(value)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16).padStart(8, "0").repeat(8).slice(0, 64); };
  const id = (prefix, seed) => `${prefix}-${hash(`${seed}:${Date.now()}:${Math.random()}`).slice(0, 24)}`;
  const readOnly = () => payload({ error: "Hosted Mission Control is read-only. Use the local Factory for research, owner approval, build, and release.", mode: "HOSTED_READ_ONLY", local_url: "http://127.0.0.1:8877/" }, 405);
  const recommendation = (purpose = "") => payload({ schema_version: "0.1", recommended_by: "ATLAS_LOCAL_INTENT_MATCH", provider_calls: 0, fit_status: "RECOMMENDED", recommended: chassis, alternatives: roles.filter((role) => role.chassis_id !== chassis.chassis_id), role_recommendation: { recommended: roles.at(-1), ranked: roles.map((role, index) => ({ role, score: index === roles.length - 1 ? 2 : 0, reasons: index === roles.length - 1 ? [`The brief is a good fit for the contained Operational Concierge chassis${purpose ? `: ${purpose.slice(0, 120)}` : ""}.`] : [] })), capability_gaps: [] } });
  const source = (name) => ({ source_name: name, retrieved_at: new Date().toISOString(), interpretation: "EPHEMERAL_TEST_FIXTURE" });
  const decodeProject = (encoded) => {
    try { return JSON.parse(decodeURIComponent(escape(atob(encoded)))); } catch (_) { return null; }
  };
  const draftFrom = (input = {}) => {
    const seed = String(input.seed || "").trim();
    const purpose = String(input.purpose || seed || "A contained concierge that answers approved questions and prepares a structured handoff.").trim();
    const client = String(input.company_name || "Independent Bicycle Repair Shops").trim();
    const idea = { schema_version: "factory.idea.v0.1", idea_id: id("idea", seed), seed_kind: input.website ? "WEBSITE" : "IDEA", website: input.website || "", fields: { client_name: client, purpose, x_agent_name: "CycleGuide", target_users: "Customers and staff of independent bicycle repair shops", personality: "Clear, practical, and friendly", additional_requirements: "Ask one useful question at a time and prepare a concise staff handoff.", additional_boundaries: "Do not diagnose, quote prices, book appointments, or claim an external action was completed.", presence_mode: "TEXT_ONLY" }, missing_information: ["Owner-approved service list and hours", "Approved escalation route and handoff ownership"], notices: ["Ephemeral test mode: this draft is held in browser memory only."], recommendation: { recommended: chassis, selected_by: "ATLAS_LOCAL_INTENT_MATCH", role_recommendation: { recommended: roles.at(-1), ranked: roles.map((role, index) => ({ role, score: index === roles.length - 1 ? 2 : 0, reasons: index === roles.length - 1 ? ["Operational Concierge fits the requested intake and handoff job."] : [] })) } } };
    idea.draft_sha256 = hash(JSON.stringify(idea)); memory.ideas.set(idea.idea_id, idea); return idea;
  };
  const projectFor = (idea) => {
    const fields = { ...idea.fields, x_agent_name: idea.fields.x_agent_name || "CycleGuide" };
    const projectId = id("project", idea.idea_id);
    const knowledge = [
      { entry_id: "K-TEST-001", question: "What kind of help can this agent provide?", answer: "It can explain the approved services of the bicycle repair shop, gather the visitor's request, and prepare a structured handoff for staff review.", relevance: "Draft fixture for the ephemeral owner review; not a real client fact.", sources: [source("Owner test fixture")] },
      { entry_id: "K-TEST-002", question: "What should the agent do when a question is outside the approved information?", answer: "It should say the answer is not yet approved and prepare the question for human review instead of guessing.", relevance: "Boundary behavior for a safe local test.", sources: [source("Factory safety fixture")] },
      { entry_id: "K-TEST-003", question: "What actions are not available?", answer: "The agent cannot diagnose a bicycle, quote a final price, book a repair, take payment, or claim that a message was sent.", relevance: "Contained capability boundary.", sources: [source("Factory safety fixture")] }
    ];
    const prompt = `## Identity\nYou are ${fields.x_agent_name}, a text-only operational concierge for ${fields.client_name}.\n\n## Job\n${fields.purpose}\n\n## Behavior\nAnswer only from owner-approved Knowledge Bank facts. Ask one useful question at a time, separate known facts from unknowns, preserve corrections, and prepare a concise unsubmitted staff handoff.\n\n## Boundaries\nDo not diagnose, invent business facts, quote prices, promise availability, book appointments, take payment, or claim an external action was completed. Escalate unsupported questions for human review.`;
    const missionId = id("draft-cycle-guide", idea.idea_id);
    const candidateSha = hash(`${projectId}:${prompt}:${JSON.stringify(knowledge)}`);
    const project = { schema_version: "factory.prepared-agent.v0.1", project_id: projectId, idea_id: idea.idea_id, status: "NEEDS_REVIEW", message: "Draft prepared in ephemeral test mode. Review the proposed job, Knowledge Bank, and System Prompt before approving.", revision: 1, revision_sha256: hash(`${projectId}:1`), fields, design: { role_id: "operational-concierge", role_rationale: "Operational Concierge is the closest fit for a contained question-and-handoff experience.", audience: fields.target_users, boundaries: ["Do not diagnose or invent facts", "Do not perform external actions"], method: ["Answer approved questions", "Ask one useful question at a time", "Prepare an unsubmitted handoff"], outcomes: ["Grounded answer", "Clear uncertainty", "Structured staff handoff"] }, knowledge, gaps: idea.missing_information, stale: [], system_prompt: prompt, approval: null, dojo: null, mission_id: null, text_candidate: { candidate_sha256: candidateSha, mission_id: missionId, project_id: projectId, package_sha256: hash(`${projectId}:package`), knowledge_sha256: hash(JSON.stringify(knowledge)), system_prompt_sha256: hash(prompt), runtime: { provider: "openai-codex", model: "gpt-5.6-luna", reasoning: "low", tools: [], max_calls_per_session: 7, implementation: "EPHEMERAL_BROWSER_REHEARSAL" } }, stages: [{ actor: "atlas", execution_mode: "DETERMINISTIC_COMPILATION", usage: { model_calls: 0 } }, { actor: "aria", execution_mode: "EPHEMERAL_TEST_FIXTURE", usage: { model_calls: 0 } }, { actor: "omnara", execution_mode: "EPHEMERAL_TEST_FIXTURE", usage: { model_calls: 0 } }, { actor: "troy", execution_mode: "EPHEMERAL_TEST_FIXTURE", usage: { model_calls: 0 } }, { actor: "binding compiler", execution_mode: "DETERMINISTIC_COMPILE", usage: { model_calls: 0 } }] };
    memory.projects.set(projectId, project); return project;
  };
  const textResponse = (project, message) => {
    const lower = String(message).toLowerCase();
    if (/(guarantee|same-day|book|appointment|price|cost|quote|diagnos)/.test(lower)) return { text: "I can’t confirm a guarantee, appointment, price, or diagnosis from the approved test information. I would flag that request for staff review rather than guess.", handoff: { request_summary: message, known_unknowns: ["The requested guarantee, appointment, price, or diagnosis is not approved."], review_flags: ["OUT_OF_KNOWLEDGE_SERVICE_QUESTION"], recommended_queue: "HUMAN_REVIEW", status: "UNSUBMITTED" } };
    if (lower.includes("service") || lower.includes("repair")) return { text: "This test agent can explain approved bicycle-repair services, gather the visitor's needs, and prepare a structured handoff for staff review. It cannot diagnose the bicycle or promise a booking.", handoff: { request_summary: message, known: ["Approved service guidance is available in the local test package."], known_unknowns: [], recommended_queue: "HUMAN_REVIEW", status: "UNSUBMITTED" } };
    if (lower.includes("purpose") || lower.includes("what do you do")) return { text: `I’m ${project.fields.x_agent_name}, a contained concierge for ${project.fields.client_name}. I explain approved information, ask one useful question at a time, and prepare a structured handoff for staff review.`, handoff: { request_summary: "Visitor asked about the agent's purpose.", recommended_queue: "HUMAN_REVIEW", status: "UNSUBMITTED" } };
    return { text: "I don’t have an approved answer for that in this test package, so I would flag it for human review rather than guess.", handoff: { request_summary: message, known_unknowns: [message], recommended_queue: "HUMAN_REVIEW", status: "UNSUBMITTED" } };
  };
  if (TEST_MODE && query.get("data")) {
    const project = decodeProject(query.get("data"));
    if (project?.project_id) memory.projects.set(project.project_id, project);
  }
  const testFetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || (typeof input !== "string" && input?.method) || "GET").toUpperCase();
    if (!url.startsWith("/api/")) return originalFetch(input, init);
    const path = url.split("?")[0];
    const body = bodyOf(init);
    if (path === "/api/ideas/prepare" && method === "POST") return payload(draftFrom(body));
    if ((path === "/api/roles/recommend" || path === "/api/chassis/recommend") && method === "POST") return recommendation(body.purpose || "");
    if (path === "/api/prepared-agents" && method === "POST") { const idea = memory.ideas.get(body.idea_id); if (!idea) return payload({ error: "The ephemeral idea is not available in this tab." }, 404); return payload(projectFor(idea)); }
    const projectMatch = path.match(/^\/api\/prepared-agents\/(project-[a-f0-9]{24})(?:\/(.*))?$/);
    if (projectMatch) {
      const project = memory.projects.get(projectMatch[1]); if (!project) return payload({ error: "Ephemeral prepared agent not found. Start a fresh test." }, 404);
      const action = projectMatch[2] || "";
      if (method === "GET" && !action) return payload(project);
      if (method === "POST" && action === "edit") { if (body.fields) project.fields = { ...project.fields, ...body.fields }; if (body.system_prompt) project.system_prompt = body.system_prompt; if (body.knowledge) project.knowledge = body.knowledge.map((entry) => ({ ...entry, sources: entry.sources || [source("Owner test fixture")] })); project.revision += 1; project.revision_sha256 = hash(`${project.project_id}:${project.revision}`); project.text_candidate.candidate_sha256 = hash(`${project.project_id}:${project.revision}:${project.system_prompt}`); project.status = "NEEDS_REVIEW"; project.message = "Edits saved in this tab. Review the exact package before approving."; return payload(project); }
      if (method === "POST" && action === "approve") { project.status = "APPROVED"; project.approval = { owner_approved: true, scope: "EPHEMERAL_TEST_ONLY", approved_at: new Date().toISOString(), package_sha256: hash(`${project.project_id}:approved`) }; project.message = "Package approved for this ephemeral rehearsal only. No local or hosted files were changed."; return payload(project); }
      if (method === "POST" && action === "build") { project.status = "BUILT"; project.mission_id = id("draft-cycle-guide", project.project_id); project.text_candidate.mission_id = project.mission_id; project.message = "Ephemeral candidate built in browser memory. Nothing was written to a repository or provider."; memory.missions.set(project.mission_id, project); return payload(project); }
      if (method === "POST" && action === "refresh") { project.status = "NEEDS_REVIEW"; project.message = "No external refresh is available in ephemeral mode; the deterministic draft remains ready for review."; return payload(project); }
      if (method === "POST" && action === "portrait") { project.portrait = body.image || ""; return payload(project); }
      if (method === "POST" && action === "dojo") { project.dojo = { decision: "PASS", scope: "EPHEMERAL_BROWSER_REHEARSAL", run_id: id("dojo", project.project_id), candidate_sha256: project.text_candidate.candidate_sha256, failed_checks: [], findings: [], not_tested: ["Provider-backed evaluation", "ANAM channel", "Production integration"], message: "Deterministic rehearsal checks passed: package identity, text runtime, unsupported-question handling, handoff shape, and fresh-session isolation." }; return payload(project); }
      if (method === "POST" && action === "text-session") { const sessionId = id("text", project.project_id); memory.sessions.set(sessionId, { project_id: project.project_id, turn: 1 }); return payload({ session_id: sessionId, project_id: project.project_id, candidate_sha256: project.text_candidate.candidate_sha256 }); }
      if (method === "POST" && action === "text-turn") { const session = memory.sessions.get(body.session_id); if (!session || session.project_id !== project.project_id) return payload({ error: "Start a fresh test session for this candidate." }, 400); const result = textResponse(project, body.message || ""); session.turn += 1; return payload({ text: result.text, output: { handoff: result.handoff }, session_id: body.session_id, turn: session.turn, match_reason: "EPHEMERAL_DETERMINISTIC_TEST" }); }
      return payload({ error: "Unsupported ephemeral prepared-agent action." }, 404);
    }
    if (path === "/api/status") return payload({ status: "EPHEMERAL_TEST_MODE", provider_calls: 0, production_approved: false, source: "browser-memory rehearsal", warning: "All mutations are in-memory and disappear on refresh." });
    if (path === "/api/roles") return payload({ roles });
    if (path === "/api/chassis") return payload({ chassis: [chassis] });
    if (path === "/api/chassis/operational-qa-concierge") return payload(chassis);
    if (path === "/api/chassis/operational-qa-concierge/options") return payload({ schema_version: "0.1", chassis_id: chassis.chassis_id, chassis_version: chassis.version, ...modules });
    if (path === "/api/knowledge-packages") return payload({ packages: [] });
    if (path === "/api/missions") return payload({ missions: [...memory.missions.values()].map((p) => ({ mission_id: p.mission_id, status: "BUILT", agent: { agent_name: p.fields.x_agent_name, client_name: p.fields.client_name, purpose: p.fields.purpose } })) });
    if (path === "/api/hunter/prospects") return payload({ prospects: [], status: "EPHEMERAL_TEST_MODE" });
    if (path === "/api/hunter/inbox") return payload({ leads: [], status: "EPHEMERAL_TEST_MODE" });
    if (path === "/api/control-plane/registry") return payload({ status: "EPHEMERAL_TEST_MODE", registry: [], authority: "In-memory rehearsal only" });
    if (path.startsWith("/api/missions/")) { const missionId = path.split("/")[3]; const p = memory.missions.get(missionId); if (!p) return payload({ error: "Mission not found in this tab." }, 404); return payload({ mission_id: missionId, status: "BUILT", agent: { agent_name: p.fields.x_agent_name, client_name: p.fields.client_name, purpose: p.fields.purpose }, authority: { production_approved: false, hosted_test_mode: true } }); }
    if (method !== "GET") return payload({ error: "This mutation is not part of the ephemeral rehearsal. Continue through Prepare → Review → Build → Test." }, 405);
    if (path.startsWith("/api/chassis/")) return payload(chassis);
    return payload({ error: "This hosted preview does not expose that local endpoint.", mode: "EPHEMERAL_TEST" }, 404);
  };
  const readOnlyFetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || (typeof input !== "string" && input?.method) || "GET").toUpperCase();
    if (!url.startsWith("/api/")) return originalFetch(input, init);
    const path = url.split("?")[0];
    if (method !== "GET") { if (path === "/api/roles/recommend" || path === "/api/chassis/recommend") return recommendation(); return readOnly(); }
    if (path === "/api/status") return payload({ status: "HOSTED_READ_ONLY_PREVIEW", provider_calls: 0, production_approved: false, source: "committed X-Factory reference data" });
    if (path === "/api/roles") return payload({ roles });
    if (path === "/api/chassis") return payload({ chassis: [chassis] });
    if (path === "/api/chassis/operational-qa-concierge") return payload(chassis);
    if (path === "/api/chassis/operational-qa-concierge/options") return payload({ schema_version: "0.1", chassis_id: chassis.chassis_id, chassis_version: chassis.version, ...modules });
    if (path === "/api/knowledge-packages") return payload({ packages: [] });
    if (path === "/api/missions") return payload({ missions: [] });
    if (path === "/api/hunter/prospects") return payload({ prospects: [], status: "HOSTED_PREVIEW_ONLY" });
    if (path === "/api/hunter/inbox") return payload({ leads: [], status: "HOSTED_PREVIEW_ONLY" });
    if (path === "/api/control-plane/registry") return payload({ status: "HOSTED_READ_ONLY_PREVIEW", registry: [], authority: "No hosted mutations" });
    if (path.startsWith("/api/chassis/")) return payload(chassis);
    return payload({ error: "This hosted preview does not expose that local endpoint.", mode: "HOSTED_READ_ONLY" }, 404);
  };
  window.fetch = TEST_MODE ? testFetch : readOnlyFetch;
  const banner = document.createElement("div");
  banner.className = "hosted-mode-banner";
  banner.setAttribute("role", "status");
  banner.innerHTML = TEST_MODE
    ? "<strong>EPHEMERAL TEST MODE · IN-MEMORY ONLY</strong><span>Run the full owner journey here. The Factory tab resets its session on refresh; generated-app links carry a test-only snapshot. Do not use client secrets. No provider, repo, ANAM, or Vercel writes occur.</span><a href=\"?mode=readonly\">Return to read-only ↗</a><a href=\"http://127.0.0.1:8877/\">Open local Factory ↗</a>"
    : "<strong>HOSTED MISSION CONTROL · READ-ONLY PREVIEW</strong><span>Browse the workflow and validated chassis here. Use the local Factory for research, approval, builds, and releases.</span><a href=\"?mode=ephemeral-test\">Open ephemeral test mode ↗</a><a href=\"http://127.0.0.1:8877/\">Open local Factory ↗</a>";
  document.body.prepend(banner);
})();
