/*
 * Hosted Mission Control is intentionally a safe, read-only cockpit.
 * The local Factory remains the authoring/build surface because its filesystem
 * state and owner gates must not be faked on an ephemeral web runtime.
 */
(() => {
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
    authority: { provider_calls: 0, client_data_attached: false, credentials_attached: false, deployment_authorized: false, production_approved: false, claim: "Hosted read-only view of a locally validated role chassis" },
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
    { role_id: "operational-concierge", chassis_id: "operational-qa-concierge", title: "Operational Concierge", summary: "Answer approved questions, qualify service requests, preserve corrections, and prepare a staff handoff.", boundaries: ["Invent business facts", "Promise availability or perform external actions"], capability_limits: ["Read-only hosted preview", "No live booking, messaging, account changes, payments, or system integrations"] }
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
  const payload = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  const readOnly = () => payload({ error: "Hosted Mission Control is read-only. Use the local Factory for research, owner approval, build, and release.", mode: "HOSTED_READ_ONLY", local_url: "http://127.0.0.1:8877/" }, 405);
  const recommendation = () => payload({ schema_version: "0.1", recommended_by: "ATLAS_LOCAL_INTENT_MATCH", provider_calls: 0, fit_status: "RECOMMENDED", recommended: chassis, alternatives: roles.filter((role) => role.chassis_id !== chassis.chassis_id), role_recommendation: { recommended: roles.at(-1), ranked: roles.map((role, index) => ({ role, score: index === roles.length - 1 ? 2 : 0, reasons: index === roles.length - 1 ? ["This hosted preview exposes the validated Operational Concierge chassis."] : [] })), capability_gaps: [] } });
  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || (typeof input !== "string" && input?.method) || "GET").toUpperCase();
    if (!url.startsWith("/api/")) return originalFetch(input, init);
    const path = url.split("?")[0];
    if (method !== "GET") {
      if (path === "/api/roles/recommend" || path === "/api/chassis/recommend") return recommendation();
      return readOnly();
    }
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
    if (path.startsWith("/api/missions/")) return payload({ error: "No local mission state is exposed in the hosted preview.", mode: "HOSTED_READ_ONLY" }, 404);
    return payload({ error: "This hosted preview does not expose that local endpoint.", mode: "HOSTED_READ_ONLY" }, 404);
  };
  const banner = document.createElement("div");
  banner.className = "hosted-mode-banner";
  banner.setAttribute("role", "status");
  banner.innerHTML = "<strong>HOSTED MISSION CONTROL · READ-ONLY PREVIEW</strong><span>Browse the workflow and validated chassis here. Use the local Factory for research, approval, builds, and releases.</span><a href=\"http://127.0.0.1:8877/\">Open local Factory ↗</a>";
  document.body.prepend(banner);
})();
