const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const previewStateModel = globalThis.PreviewStateModel;
let presenceMode = "EXISTING_ANAM";
let currentRecord = null;
let currentPresence = null;
let currentRepo = null;
let currentCompletion = null;
let currentOwnerControl = null;
let presencePoll = null;
let currentChassis = null;
let pendingRecommendation = null;
let commissioningPresenceMode = "EXISTING_ANAM";
let knowledgePackages = [];
let selectedKnowledgePackageId = null;
let showKnowledgePackageHistory = false;
let currentModuleOptions = null;
let selectedOptionalModules = new Set();
let currentCompilation = null;
let capturedWebsitePackageId = null;
let selectedBeforeWebsiteCaptureId = null;
let currentRuntimePlan = null;
let commissioningStartedAt = null;
let previewSession = previewStateModel.createState();
let previewChecks = {known: false, pricing: false, unknown: false, qualification: false, correction: false, handoff: false, fresh: false};

const artifactLabels = {
  owner_brief: "Owner brief",
  blueprint: "Aria blueprint",
  generator_blueprint: "Mason compatibility input",
  agent_instructions: "Agent instructions",
  agent_spec: "Agent specification",
  bundle_manifest: "Bundle manifest",
  build_test: "Generated test",
  certification: "Vera certification",
  persona_binding: "Persona binding",
  control_center_handoff: "Control Center handoff",
  x_link_package: "X-Link candidate package",
  x_link_agent_entry: "X-Link agent entry",
  x_link_scenario_pack: "X-Link scenario pack",
  x_link_canary_plan: "X-Link / ANAM canary plan",
  hermes_review_packet: "Hermes / Luna review packet",
  commissioning_record: "Commissioning record",
  knowledge_package_reference: "Knowledge package reference",
  instance_knowledge_bundle: "Approved knowledge bundle",
  instance_source_vault: "Immutable source vault",
  instance_knowledge_bank: "Client knowledge bank",
  knowledge_studio_package: "OMNARA Knowledge Studio package",
  knowledge_studio_traceability: "OMNARA source traceability",
  knowledge_index: "Knowledge Bank index",
  instance_system_prompt: "Personalized system prompt",
  prompt_forge_manifest: "Troy Prompt Forge manifest",
  prompt_assumptions: "Troy prompt assumptions",
  prompt_tests: "Troy prompt tests",
  prompt_owner_summary: "Troy owner summary",
  instance_traceability: "Knowledge traceability map",
  instance_knowledge_tests: "Knowledge tests",
  instance_knowledge_report: "Instance build report",
  runtime_foundry_plan: "Runtime Foundry plan",
  runtime_profile_blueprint: "Hermes profile blueprint",
  runtime_canary_prompt: "Exact Luna canary prompt",
  runtime_canary_payload: "Exact Luna canary payload",
  runtime_activation_packet: "Inactive runtime canary packet",
  instance_runtime_contract: "Locked instance runtime contract",
  runtime_behavior_plan: "Runtime behavior proof plan",
  local_behavior_certification: "Local multi-turn certification",
  independent_review: "Rook independent review",
};

function ownerFacingName(agent) {
  if (!agent?.derived_from_chassis) return agent?.display_name || agent?.agent_name || "X-Agent";
  return agent.public_role_title ? `${agent.agent_name} — ${agent.public_role_title}` : agent.agent_name;
}

function novaSyncMessage(record = currentRecord) {
  const identity = record ? ownerFacingName(record.agent) : "No commissioned X-Agent selected";
  const purpose = record?.agent?.purpose || "No active commissioned purpose";
  const mission = record?.mission_id || "none selected";
  const lifecycle = currentRepo ? "Local application repository created and verified" : record ? "Commissioned agent ready for local preview" : "Ready for the owner to describe a new X-Agent";
  const blocker = currentRepo && !currentRepo.authority?.runtime_approved
    ? "Official repository handoff still requires the governed Hermes multi-turn runtime proof"
    : "No blocker in the current local stage";
  const nextAction = currentRepo
    ? "Owner acceptance test of the generated local app, then the governed Hermes runtime proof"
    : record ? "Run the local preview and prepare the complete app repository" : "Describe the job in plain English";
  return `Nova — automated X-Factory milestone handoff from Mission Control 1.9.

Current owner mental model: Describe → Personalize → Build → Preview → Release.

Lifecycle state: ${lifecycle}
Unresolved blocker: ${blocker}
Next intended action: ${nextAction}

Latest repair:
- The internal chassis title is no longer exposed as the commissioned agent's customer-facing identity.
- Owner/runtime identity: ${identity}
- Commissioned purpose: ${purpose}
- Internal chassis metadata remains available only inside Factory Details and build governance.
- Existing mission views, presence previews, new commissioned builds, and Porter repo outputs use the safe identity boundary.
- Atlas remains a recommended fit; the owner may deliberately select another validated chassis.
- Personalize now includes one "Use the company website" intake. An explicit owner click captures at most six same-origin public pages, preserves URL/title/body hashes, and sends the result to the existing Owner Review Desk.
- Website capture blocks private/local targets, cross-site redirects, credentials, nonstandard ports, oversized/non-text pages, and never approves runtime knowledge automatically.
- Website review removes navigation/CTA boilerplate, groups related fragments, deduplicates repeated facts, labels relevance categories, and starts with every proposed website fact unselected.
- Website facts may enter only the approved Knowledge Bank. They do not become behavioral system-prompt instructions or alter identity, purpose, authority, tools, or boundaries.
- Legacy website compilations are blocked from finalization and must be recaptured through the relevance-aware pipeline.
- One owner build now continues automatically through Rook's provider-free independent review and Porter's verified local-repository packaging.
- The owner completion label is now "LOCAL X-AGENT BUILT" and explicitly directs preview before any governed runtime or release action.
- Hermes /review is prepared as a future governed audit option, but is not invoked and makes no provider call in this local route.

Current mission: ${mission}
Verification: identity isolation PASS; chassis commissioning PASS; website capture and safety boundaries PASS; knowledge/options/Porter regression PASS; owner browser flows PASS; syntax checks PASS.
Provider calls: 0. Deployment/production actions: 0.

Please treat this as the current implementation baseline and flag only concrete conflicts with the locked owner experience.`;
}

function refreshNovaSync(record = currentRecord) {
  const field = $("#nova-sync-message");
  if (field) field.value = novaSyncMessage(record);
  const status = $("#nova-sync-status");
  if (status) status.textContent = "Prepared locally · not sent";
}

function setOwnerJourney(activeId, completedIds = []) {
  const ids = ["define", "personalize", "build", "preview", "release"];
  ids.forEach((id) => {
    const card = $(`#journey-${id}`);
    card.classList.toggle("active", id === activeId);
    card.classList.toggle("done", completedIds.includes(id));
    card.querySelector("b").textContent = completedIds.includes(id) ? "DONE" : (id === activeId ? "NOW" : (id === "release" ? "LOCKED" : "WAITING"));
  });
}

function setCommissioningPresence(mode) {
  commissioningPresenceMode = mode;
  $$('[data-commission-presence]').forEach((button) => {
    const selected = button.dataset.commissionPresence === mode;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  if (mode === "EXISTING_ANAM" && !$("#commission-agent-name").value.trim()) {
    $("#commission-agent-name").value = "Mia";
  }
  updateCommissionButton();
}

function updateCommissionButton() {
  const name = $("#commission-agent-name").value.trim() || "THIS X-AGENT";
  const button = $("#run-commissioning");
  const websiteReviewPending = Boolean(capturedWebsitePackageId && selectedKnowledgePackageId !== capturedWebsitePackageId);
  button.disabled = websiteReviewPending;
  button.querySelector("span").textContent = websiteReviewPending ? "REVIEW WEBSITE BEFORE BUILD" : `BUILD ${name.toUpperCase()}`;
  button.title = websiteReviewPending ? "Finish or discard the captured website review before building." : "";
  updateKnowledgeReceipt();
}

function setQuickKnowledgeStatus(message, state = "") {
  const status = $("#quick-knowledge-status");
  status.textContent = message;
  status.className = state;
}

function resetPreviewSession(message = "Fresh local session. Nothing from the previous session was carried over.") {
  previewSession = previewStateModel.createState();
  $("#preview-handoff-request").textContent = "Waiting for a service request";
  $("#preview-handoff-service").textContent = "Not provided";
  $("#preview-handoff-location").textContent = "Not provided";
  $("#preview-handoff-urgency").textContent = "Not provided";
  $("#preview-handoff-routing").textContent = "HUMAN_REVIEW";
  $("#preview-handoff-unknowns").textContent = "None yet";
  $("#preview-handoff-flags").textContent = "None";
  $("#preview-handoff-corrections").textContent = "None yet";
  $("#preview-handoff-routing-note").textContent = "None";
  const transcript = $("#runtime-transcript");
  transcript.textContent = "";
  appendRuntimeMessage("PREVIEW", message, "system");
}

function humanReviewFlag(flag) {
  if (flag === "OUT_OF_KNOWLEDGE_SERVICE_QUESTION") return "Service question outside approved knowledge";
  if (flag === "PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE") return "Requested service needs human confirmation";
  return flag;
}

function renderPreviewHandoff() {
  $("#preview-handoff-request").textContent = previewSession.request || "Waiting for a service request";
  $("#preview-handoff-service").textContent = previewSession.service || "Not provided";
  $("#preview-handoff-location").textContent = previewSession.city || "Not provided";
  $("#preview-handoff-urgency").textContent = previewSession.urgency || "Not provided";
  $("#preview-handoff-routing").textContent = previewStateModel.recommendedQueue(previewSession);
  $("#preview-handoff-unknowns").textContent = previewSession.unknowns.length ? previewSession.unknowns.join(" · ") : "None yet";
  $("#preview-handoff-flags").textContent = previewStateModel.reviewFlags(previewSession).map(humanReviewFlag).join(" · ") || "None";
  $("#preview-handoff-corrections").textContent = previewSession.corrections.length ? previewSession.corrections.map((item) => `${item.field}: ${item.previous_value} → ${item.corrected_value}`).join(" · ") : "None yet";
  $("#preview-handoff-routing-note").textContent = previewStateModel.routingNote(previewSession) || "None";
}

function previewReady() {
  return Object.values(previewChecks).every(Boolean);
}

function syncPreviewChecks() {
  const labels = {known: "known answer", pricing: "pricing", unknown: "human review", qualification: "qualification", correction: "correction", handoff: "handoff summary", fresh: "fresh session"};
  const passed = Object.entries(previewChecks).filter(([, value]) => value).map(([key]) => labels[key]);
  const status = $("#preview-check-status");
  status.classList.toggle("ready", previewReady());
  status.textContent = previewReady()
    ? "Preview checks complete · repository packaging is now unlocked."
    : `Preview checks ${passed.length}/7 · completed: ${passed.join(", ") || "none"}.`;
  if (!currentRepo) {
    $("#create-local-repo").disabled = !previewReady();
    $("#create-local-repo").textContent = previewReady() ? "CREATE COMPLETE LOCAL APP →" : "FINISH PREVIEW CHECKS FIRST";
    $("#repo-status-title").textContent = previewReady() ? "Ready to package" : "Complete the preview checks";
    $("#repo-status-copy").textContent = previewReady()
      ? "Porter can now create a new staging repository and run its verification suite. It makes zero provider calls."
      : "Try one known answer, pricing, an unknown question, qualification details, a correction, a handoff summary, and a fresh session before packaging.";
  }
}

function resetPreviewVerification() {
  previewChecks = {known: false, pricing: false, unknown: false, qualification: false, correction: false, handoff: false, fresh: false};
  syncPreviewChecks();
}

function applyPreviewTurn(message, intent, result = null) {
  previewSession = previewStateModel.apply(previewSession, message, intent, result);
  if (previewStateModel.isQualified(previewSession)) previewChecks.qualification = true;
}

function handoffSummaryText() {
  const corrections = previewSession.corrections.length ? previewSession.corrections.map((item) => `${item.field}: ${item.previous_value} → ${item.corrected_value}`).join(" · ") : "None";
  const queue = previewStateModel.recommendedQueue(previewSession);
  const secondary = previewSession.unknowns.join(" · ") || "None";
  const note = previewStateModel.routingNote(previewSession);
  return `Request: ${previewSession.request || "Not provided"} Service: ${previewSession.service || "Not provided"}. Location: ${previewSession.city || "Not provided"}. Urgency: ${previewSession.urgency || "Not provided"}. Route: ${queue}. Secondary questions: ${secondary}. Corrections: ${corrections}.${note ? ` ${note}` : ""}`;
}

function setBlankWorkbench(open) {
  const form = $("#mission-form");
  const button = $("#toggle-blank-build");
  form.hidden = !open;
  $("#blank-factory").classList.toggle("blank-closed", !open);
  button.setAttribute("aria-expanded", String(open));
  button.textContent = open ? "CLOSE BLANK-BRIEF WORKBENCH" : "OPEN BLANK-BRIEF WORKBENCH";
}

function setFactoryDetails(open) {
  document.body.classList.toggle("factory-details-open", open);
  $("#global-factory-details").setAttribute("aria-expanded", String(open));
  $("#global-factory-details").textContent = open ? "Hide factory details" : "Factory details";
  $("#toggle-factory-details").setAttribute("aria-expanded", String(open));
  $("#toggle-factory-details").textContent = open ? "HIDE FACTORY DETAILS" : "FACTORY DETAILS";
  $("#factory-detail-body").hidden = !open;
}

function syncKnowledgeModule() {
  if (selectedKnowledgePackageId) selectedOptionalModules.add("CMP-CLIENT-KNOWLEDGE-PACK");
  else selectedOptionalModules.delete("CMP-CLIENT-KNOWLEDGE-PACK");
}

function updateKnowledgeReceipt() {
  const receipt = $("#build-knowledge-receipt");
  if (!receipt) return;
  const selected = knowledgePackages.find((item) => item.package_id === selectedKnowledgePackageId);
  const captured = knowledgePackages.find((item) => item.package_id === capturedWebsitePackageId);
  const reviewPending = Boolean(capturedWebsitePackageId && selectedKnowledgePackageId !== capturedWebsitePackageId);
  receipt.classList.toggle("ready", Boolean(selected && !reviewPending));
  receipt.classList.toggle("pending", reviewPending);
  if (reviewPending) {
    const pages = captured?.website_capture?.pages?.length || captured?.files?.length || 0;
    $("#build-knowledge-state").textContent = "REVIEW REQUIRED BEFORE BUILD";
    $("#build-knowledge-source").textContent = captured?.label || "Captured website awaiting owner review";
    $("#build-knowledge-pages").textContent = `${pages} public page${pages === 1 ? "" : "s"} captured · not finalized`;
    $("#build-knowledge-facts").textContent = "0 bound to this build";
    $("#build-knowledge-exclusions").textContent = "The previously selected package and all unapproved website content are excluded while review is pending.";
    $("#build-knowledge-binding").textContent = captured ? `Pending package ${captured.package_id} · manifest ${captured.manifest_sha256.slice(0, 12)}… · no finalized review binding` : "Captured package is still loading.";
    return;
  }
  if (!selected) {
    $("#build-knowledge-state").textContent = "NO APPROVED KNOWLEDGE";
    $("#build-knowledge-source").textContent = "No reviewed package selected";
    $("#build-knowledge-pages").textContent = "0 files reviewed";
    $("#build-knowledge-facts").textContent = "0";
    $("#build-knowledge-exclusions").textContent = "Unapproved website content, sample knowledge, and older packages are not included.";
    $("#build-knowledge-binding").textContent = "No package ID or review hash is bound.";
    return;
  }
  const pageCount = selected.website_capture?.pages?.length;
  const fileCount = selected.files?.length || 0;
  const approvedFacts = selected.compilation?.approved_entries || 0;
  $("#build-knowledge-state").textContent = "REVIEWED + BOUND";
  $("#build-knowledge-source").textContent = selected.label;
  $("#build-knowledge-pages").textContent = pageCount
    ? `${pageCount} public page${pageCount === 1 ? "" : "s"} reviewed`
    : `${fileCount} owner file${fileCount === 1 ? "" : "s"} reviewed`;
  $("#build-knowledge-facts").textContent = `${approvedFacts}`;
  $("#build-knowledge-exclusions").textContent = selected.website_capture
    ? "Prior sample knowledge, older packages, rejected facts, and unapproved website content are not included."
    : "Older packages and unapproved or rejected content are not included.";
  const binding = [
    `package ${selected.package_id}`,
    selected.compilation?.review_id ? `review ${selected.compilation.review_id}` : null,
    selected.manifest_sha256 ? `manifest ${selected.manifest_sha256.slice(0, 12)}…` : null,
    selected.compilation?.review_sha256 ? `review hash ${selected.compilation.review_sha256.slice(0, 12)}…` : null,
  ].filter(Boolean).join(" · ");
  $("#build-knowledge-binding").textContent = binding;
}

function renderKnowledgePackages() {
  const holder = $("#knowledge-packages");
  const summary = $("#knowledge-package-summary");
  const historyButton = $("#toggle-package-history");
  holder.textContent = "";
  if (!knowledgePackages.length) {
    const empty = document.createElement("p");
    empty.textContent = "No knowledge packages loaded yet.";
    holder.append(empty);
    summary.textContent = "No source packages yet.";
    historyButton.hidden = true;
    return;
  }
  const spotlight = knowledgePackages.find((item) => item.package_id === capturedWebsitePackageId)
    || knowledgePackages.find((item) => item.package_id === selectedKnowledgePackageId)
    || knowledgePackages[0];
  const visiblePackages = showKnowledgePackageHistory ? knowledgePackages : [spotlight];
  const hiddenCount = Math.max(knowledgePackages.length - 1, 0);
  summary.textContent = showKnowledgePackageHistory
    ? `Showing all ${knowledgePackages.length} source packages. The selected package remains highlighted.`
    : `Showing ${selectedKnowledgePackageId === spotlight.package_id ? "the selected" : "the newest"} package: ${spotlight.label}. ${hiddenCount ? `${hiddenCount} older package${hiddenCount === 1 ? " is" : "s are"} tucked away.` : ""}`;
  historyButton.hidden = hiddenCount === 0;
  historyButton.textContent = showKnowledgePackageHistory ? "HIDE PACKAGE HISTORY" : `SHOW PACKAGE HISTORY (${hiddenCount})`;
  historyButton.setAttribute("aria-expanded", String(showKnowledgePackageHistory));
  visiblePackages.forEach((item) => {
    const card = document.createElement("article");
    card.className = "knowledge-package";
    if (selectedKnowledgePackageId === item.package_id) card.classList.add("selected");
    const copy = document.createElement("div");
    const name = document.createElement("strong");
    const details = document.createElement("small");
    const fileLedger = document.createElement("div");
    fileLedger.className = "knowledge-file-ledger";
    name.textContent = item.label;
    const compilationStatus = item.compilation?.status || "NOT YET COMPILED";
    const sourceLabel = item.website_capture ? `WEBSITE CAPTURE · ${item.website_capture.pages.length} PUBLIC PAGE${item.website_capture.pages.length === 1 ? "" : "S"}` : "OWNER FILES";
    details.textContent = `${sourceLabel} · ${item.files.length} FILE${item.files.length === 1 ? "" : "S"} · ${item.total_bytes.toLocaleString()} BYTES · ${item.effective_status.replaceAll("_", " ")} · ${item.manifest_sha256.slice(0, 12)}…`;
    item.files.forEach((file) => {
      const row = document.createElement("span");
      row.textContent = `${file.original_name} · ${file.bytes.toLocaleString()} B · ${file.sha256.slice(0, 12)}…`;
      fileLedger.append(row);
    });
    const fileDetails = document.createElement("details");
    fileDetails.className = "knowledge-file-details";
    const fileSummary = document.createElement("summary");
    fileSummary.textContent = `VIEW ${item.files.length} SOURCE FILE${item.files.length === 1 ? "" : "S"}`;
    fileDetails.append(fileSummary, fileLedger);
    const status = document.createElement("span");
    status.className = "knowledge-package-status";
    if (compilationStatus === "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD") status.classList.add("ready");
    else if (compilationStatus !== "NOT YET COMPILED") status.classList.add("pending");
    status.textContent = compilationStatus.replaceAll("_", " ");
    copy.append(name, details, fileDetails, status);
    const actions = document.createElement("div");
    actions.className = "knowledge-package-actions";
    const actionButton = (text, className, handler) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = text;
      button.addEventListener("click", () => handler(button));
      actions.append(button);
    };
    if (item.effective_status !== "OWNER_APPROVED_FOR_COMMISSIONING") {
      actionButton("APPROVE EXACT PACKAGE", "approve", async (button) => {
        button.disabled = true;
        button.textContent = "RECHECKING HASHES…";
        try {
          const response = await fetch(`/api/knowledge-packages/${encodeURIComponent(item.package_id)}/approve`, {method: "POST"});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Knowledge approval stopped safely");
          await loadKnowledgePackages();
        } catch (error) {
          $("#knowledge-error").textContent = error instanceof Error ? error.message : String(error);
          button.disabled = false;
          button.textContent = "APPROVE EXACT PACKAGE";
        }
      });
    } else if (item.compilation?.requires_recapture) {
      actionButton("CAPTURE CLEAN COPY", "compile", async (button) => {
        button.disabled = true;
        button.textContent = "CAPTURING CLEAN COPY…";
        try {
          const response = await fetch("/api/website-knowledge", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({url: item.website_capture.requested_url, label: item.label})});
          const captured = await response.json();
          if (!response.ok) throw new Error(captured.error || "Clean website capture stopped safely");
          capturedWebsitePackageId = captured.package_id;
          await loadKnowledgePackages();
          const pageCount = captured.website_capture?.pages?.length || captured.files.length;
          $("#website-capture-result").hidden = false;
          $("#website-knowledge-status").textContent = `Captured a clean copy from ${pageCount} public page${pageCount === 1 ? "" : "s"}. Nothing is approved yet. Review the filtered facts next.`;
          $("#review-website-knowledge").hidden = false;
          $(".website-knowledge").scrollIntoView({behavior: "smooth", block: "center"});
        } catch (error) {
          $("#knowledge-error").textContent = error instanceof Error ? error.message : String(error);
          button.disabled = false;
          button.textContent = "CAPTURE CLEAN COPY";
        }
      });
    } else if (!item.compilation) {
      actionButton("COMPILE FOR REVIEW", "compile", async (button) => {
        button.disabled = true;
        button.textContent = "EXTRACTING SOURCES…";
        try {
          const response = await fetch(`/api/knowledge-packages/${encodeURIComponent(item.package_id)}/compile`, {method: "POST"});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Knowledge Compiler stopped safely");
          await loadKnowledgePackages();
          await openReviewDesk(item.package_id);
        } catch (error) {
          $("#knowledge-error").textContent = error instanceof Error ? error.message : String(error);
          button.disabled = false;
          button.textContent = "COMPILE FOR REVIEW";
        }
      });
    } else if (item.compilation.status === "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD") {
      actionButton(selectedKnowledgePackageId === item.package_id ? "SELECTED ✓" : "USE REVIEWED PACKAGE", "select", () => {
        selectedKnowledgePackageId = selectedKnowledgePackageId === item.package_id ? null : item.package_id;
        syncKnowledgeModule();
        renderKnowledgePackages();
        renderModuleOptions();
        updateCommissionButton();
      });
      actionButton("OPEN REVIEW", "review", () => openReviewDesk(item.package_id));
    } else {
      actionButton(item.compilation.status === "COMPILED_PENDING_OWNER_REVIEW" ? "REVIEW PROPOSALS" : "REVISE REVIEW", "review", () => openReviewDesk(item.package_id));
    }
    card.append(copy, actions);
    holder.append(card);
  });
}

async function loadKnowledgePackages() {
  const response = await fetch("/api/knowledge-packages", {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Knowledge Loading Dock is unavailable");
  knowledgePackages = data.packages;
  if (selectedKnowledgePackageId && !knowledgePackages.some((item) => item.package_id === selectedKnowledgePackageId && item.compilation?.status === "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD")) {
    selectedKnowledgePackageId = null;
    syncKnowledgeModule();
  }
  renderKnowledgePackages();
  updateKnowledgeReceipt();
}

function updateReviewCount() {
  const checked = $$("#knowledge-review-entries input[type=checkbox]:checked").length;
  const total = $$("#knowledge-review-entries input[type=checkbox]").length;
  $("#review-count").textContent = `${checked} SELECTED · ${total - checked} NOT SELECTED`;
}

function renderReviewDesk(compilation) {
  $("#knowledge-source-packages").open = true;
  currentCompilation = compilation;
  const packageRecord = knowledgePackages.find((item) => item.package_id === compilation.package_id);
  const websiteSource = Boolean(packageRecord?.website_capture);
  const staleWebsiteCompilation = websiteSource && compilation.quality_filter?.version !== "WEBSITE_RELEVANCE_V0_1";
  $("#review-package-title").textContent = packageRecord?.label || compilation.package_id;
  const quality = compilation.quality_filter;
  $("#review-desk-summary").textContent = quality
    ? `${compilation.entries.length} relevant proposals · ${quality.boilerplate_removed} boilerplate items removed · ${quality.grouped_fragments} related fragments grouped · ${quality.duplicates_removed} duplicates removed · knowledge-bank only · zero provider calls`
    : `${compilation.entries.length} source-linked proposals · ${compilation.conflicts.length} potential conflicts · deterministic extraction · zero provider calls`;
  const conflictBanner = $("#review-conflict-banner");
  conflictBanner.hidden = !staleWebsiteCompilation && compilation.conflicts.length === 0;
  conflictBanner.textContent = staleWebsiteCompilation
    ? "THIS WEBSITE REVIEW PREDATES THE RELEVANCE FILTER. It cannot be finalized. Close this desk and choose CAPTURE CLEAN COPY on the package."
    : compilation.conflicts.length ? `${compilation.conflicts.length} CONFLICT GROUP${compilation.conflicts.length === 1 ? "" : "S"}: select at most one entry in each red group, or leave all unselected.` : "";
  const decisionMap = new Map((compilation.latest_review?.decisions || []).map((item) => [item.entry_id, item.decision]));
  const holder = $("#knowledge-review-entries");
  holder.textContent = "";
  compilation.entries.forEach((entry) => {
    const row = document.createElement("label");
    row.className = `review-entry${entry.potential_conflict_group ? " conflict" : ""}`;
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.dataset.entryId = entry.entry_id;
    toggle.dataset.conflict = entry.potential_conflict_group || "";
    const recommendedWebsiteCategories = new Set(["FAQ", "SERVICE_OR_CAPABILITY", "BUSINESS_POLICY", "HOURS_OR_AVAILABILITY", "LOCATION_OR_CONTACT"]);
    toggle.dataset.recommended = entry.relevance
      ? String(recommendedWebsiteCategories.has(entry.relevance.category) && !entry.potential_conflict_group)
      : String(!entry.potential_conflict_group);
    toggle.checked = decisionMap.size ? decisionMap.get(entry.entry_id) === "APPROVE" : (!websiteSource && !entry.potential_conflict_group);
    toggle.disabled = staleWebsiteCompilation;
    toggle.addEventListener("change", () => {
      if (toggle.checked && toggle.dataset.conflict) {
        $$(`#knowledge-review-entries input[data-conflict="${toggle.dataset.conflict}"]`).forEach((other) => { if (other !== toggle) other.checked = false; });
      }
      updateReviewCount();
    });
    const copy = document.createElement("span");
    const head = document.createElement("span");
    head.className = "review-entry-head";
    const id = document.createElement("b");
    const kind = document.createElement("span");
    id.textContent = entry.entry_id;
    const category = entry.relevance?.category?.replaceAll("_", " ") || entry.kind;
    kind.textContent = entry.potential_conflict_group ? `${category} · ${entry.potential_conflict_group}` : category;
    head.append(id, kind);
    const title = document.createElement("strong");
    const statement = document.createElement("p");
    const source = document.createElement("small");
    title.textContent = entry.title;
    statement.textContent = entry.statement;
    const target = entry.relevance ? " · KNOWLEDGE BANK ONLY" : "";
    source.textContent = `${entry.source.file} · LINES ${entry.source.line_start}-${entry.source.line_end} · ${entry.source.file_sha256.slice(0, 12)}… · ${entry.extraction_method.replaceAll("_", " ")}${target}`;
    copy.append(head, title, statement, source);
    row.append(toggle, copy);
    holder.append(row);
  });
  $("#knowledge-review-desk").hidden = false;
  $("#review-error").textContent = "";
  $("#review-safe-defaults").disabled = staleWebsiteCompilation;
  $("#review-clear").disabled = staleWebsiteCompilation;
  $("#finalize-knowledge-review").disabled = staleWebsiteCompilation;
  updateReviewCount();
  $("#knowledge-review-desk").scrollIntoView({behavior: "smooth", block: "start"});
}

async function openReviewDesk(packageId) {
  try {
    const response = await fetch(`/api/knowledge-packages/${encodeURIComponent(packageId)}/compilation`, {cache: "no-store"});
    const compilation = await response.json();
    if (!response.ok) throw new Error(compilation.error || "Owner Review Desk is unavailable");
    renderReviewDesk(compilation);
  } catch (error) {
    $("#knowledge-error").textContent = error instanceof Error ? error.message : String(error);
  }
}

function moduleOptionRow(item, kind) {
  const row = document.createElement("label");
  row.className = `module-option ${kind}`;
  row.dataset.moduleId = item.module_id;
  const toggle = document.createElement("input");
  toggle.type = "checkbox";
  const copy = document.createElement("span");
  const name = document.createElement("strong");
  const description = document.createElement("small");
  const state = document.createElement("b");
  name.textContent = item.name;
  description.textContent = item.description || item.reason || item.category.replaceAll("-", " ");
  copy.append(name, description);
  if (kind === "included") {
    toggle.checked = true;
    toggle.disabled = true;
    state.textContent = "CORE · LOCKED";
  } else if (kind === "prohibited") {
    toggle.disabled = true;
    state.textContent = "PROHIBITED";
  } else {
    const knowledgeControlled = item.module_id === "CMP-CLIENT-KNOWLEDGE-PACK";
    toggle.checked = selectedOptionalModules.has(item.module_id);
    toggle.disabled = knowledgeControlled;
    state.textContent = knowledgeControlled ? (selectedKnowledgePackageId ? "PACKAGE ATTACHED" : "SELECT PACKAGE ABOVE") : "OPTIONAL";
    toggle.addEventListener("change", () => {
      if (toggle.checked) selectedOptionalModules.add(item.module_id);
      else selectedOptionalModules.delete(item.module_id);
    });
  }
  row.append(toggle, copy, state);
  return row;
}

function renderModuleOptions() {
  const holder = $("#module-options");
  if (!currentModuleOptions) return;
  holder.textContent = "";
  currentModuleOptions.included.forEach((item) => holder.append(moduleOptionRow(item, "included")));
  currentModuleOptions.optional.forEach((item) => holder.append(moduleOptionRow(item, "optional")));
  currentModuleOptions.locked.forEach((item) => holder.append(moduleOptionRow(item, "prohibited")));
}

async function loadModuleOptions(chassisId) {
  const response = await fetch(`/api/chassis/${encodeURIComponent(chassisId)}/options`, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Module Options Bay is unavailable");
  currentModuleOptions = data;
  renderModuleOptions();
}

function openCommissioning(chassis) {
  setOwnerJourney("personalize", ["define"]);
  commissioningStartedAt = Date.now();
  const changedChassis = currentChassis?.chassis_id !== chassis.chassis_id;
  currentChassis = chassis;
  if (changedChassis) {
    selectedKnowledgePackageId = null;
    selectedOptionalModules = new Set();
    $("#commission-client-name").value = "";
    $("#commission-client-context").value = "";
    $("#commission-requirements").value = "";
    $("#commission-boundaries").value = "";
    $("#quick-knowledge-text").value = "";
    $("#website-knowledge-url").value = "";
    $("#website-capture-result").hidden = true;
    capturedWebsitePackageId = null;
    selectedBeforeWebsiteCaptureId = null;
    $("#discard-website-knowledge").hidden = true;
    setQuickKnowledgeStatus("Knowledge: Missing — add approved facts before expecting grounded answers.");
  }
  $("#commissioning-chassis-id").value = chassis.chassis_id;
  $("#commission-role-title").value = chassis.role_title;
  $("#commissioning-form").hidden = false;
  setBlankWorkbench(false);
  setCommissioningPresence("EXISTING_ANAM");
  loadKnowledgePackages().catch((error) => { $("#knowledge-error").textContent = error instanceof Error ? error.message : String(error); });
  loadModuleOptions(chassis.chassis_id).catch((error) => { $("#module-options").textContent = error instanceof Error ? error.message : String(error); });
}

function recommendationReason(chassis) {
  const features = [];
  if (chassis.modules.includes("CMP-APPROVED-KNOWLEDGE-ANSWERS")) features.push("approved-question answers");
  if (chassis.invariants?.must_accomplish?.some((item) => item.toLowerCase().includes("qualify"))) features.push("request qualification");
  if (chassis.modules.includes("CMP-HUMAN-REVIEW-HANDOFF")) features.push("a structured staff handoff");
  const supported = features.length > 1 ? `${features.slice(0, -1).join(", ")}, and ${features.at(-1)}` : features[0] || "the core behavior you described";
  return `This proven foundation already supports ${supported}. Your wording remains the agent's authoritative job description.`;
}

function showRecommendation(chassis) {
  pendingRecommendation = chassis;
  $("#recommended-fit-title").textContent = "A strong starting point for this job";
  $("#recommended-fit-reason").textContent = recommendationReason(chassis);
  $("#recommended-fit").hidden = false;
}

function clearRecommendation() {
  pendingRecommendation = null;
  $("#recommended-fit").hidden = true;
}

async function recommendFromPurpose() {
  const purpose = $("#owner-purpose").value.trim();
  const button = $("#recommend-chassis");
  const error = $("#purpose-error");
  const status = $("#purpose-recommendation");
  error.textContent = "";
  if (!$("#owner-purpose").reportValidity()) return null;
  button.disabled = true;
  button.textContent = "ATLAS IS MATCHING THE JOB…";
  status.textContent = "Comparing your description with the proven roles in the Chassis Depot.";
  try {
    const response = await fetch("/api/chassis/recommend", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({purpose})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Atlas could not recommend a starting point");
    status.textContent = "Atlas found a recommended fit. Review the plain-English reason below—you are free to choose another.";
    showRecommendation(result.recommended);
    $("#recommended-fit").scrollIntoView({behavior: "smooth", block: "center"});
    return result;
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
    status.textContent = "Your description is unchanged. Fix the item below and try again.";
    return null;
  } finally {
    button.disabled = false;
    button.textContent = "FIND THE BEST STARTING POINT →";
  }
}

function renderChassisCard(chassis) {
  const card = document.createElement("article");
  card.className = "chassis-card";
  const kicker = document.createElement("small");
  kicker.textContent = "ROLE FOUNDATION · IDENTITY-FREE";
  const title = document.createElement("h3");
  title.textContent = chassis.role_title;
  const summary = document.createElement("p");
  summary.textContent = chassis.summary;
  const vin = document.createElement("div");
  vin.className = "chassis-vin";
  [["VERSION", chassis.version], ["STATUS", "VALIDATED"], ["MODULES", String(chassis.modules.length)]].forEach(([labelText, value]) => {
    const cell = document.createElement("span");
    const label = document.createElement("small");
    const strong = document.createElement("b");
    label.textContent = labelText;
    strong.textContent = value;
    cell.append(label, strong);
    vin.append(cell);
  });
  const modules = document.createElement("div");
  modules.className = "chassis-modules";
  chassis.modules.forEach((module) => {
    const chip = document.createElement("span");
    chip.textContent = module.replace("CMP-", "").replaceAll("-", " ");
    modules.append(chip);
  });
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "USE THIS PROVEN ROLE →";
  button.addEventListener("click", () => {
    if (!$("#owner-purpose").reportValidity()) {
      $("#owner-purpose").focus();
      return;
    }
    openCommissioning(chassis);
    $("#commissioning-form").scrollIntoView({behavior: "smooth", block: "center"});
  });
  card.append(kicker, title, summary, vin, modules, button);
  return card;
}

async function loadChassisDepot() {
  const response = await fetch("/api/chassis", {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Chassis Depot is unavailable");
  const holder = $("#chassis-list");
  holder.textContent = "";
  $("#chassis-count").textContent = String(data.chassis.length).padStart(2, "0");
  if (!data.chassis.length) {
    const empty = document.createElement("p");
    empty.textContent = "No validated chassis are stored yet.";
    holder.append(empty);
    return;
  }
  data.chassis.forEach((chassis) => holder.append(renderChassisCard(chassis)));
}

function setPresence(mode) {
  presenceMode = mode;
  $$('[data-presence]').forEach((button) => {
    const selected = button.dataset.presence === mode;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  const card = $("#persona-card");
  const image = card.querySelector("img");
  const small = card.querySelector("small");
  const strong = card.querySelector("strong");
  const copy = card.querySelector("p");
  const status = card.querySelector("b");
  card.classList.toggle("alt", mode !== "EXISTING_ANAM");
  image.hidden = mode === "TEXT_ONLY";
  if (mode === "EXISTING_ANAM") {
    small.textContent = "FACTORY RECOMMENDATION";
    strong.textContent = "Mia · Support Guide";
    copy.textContent = "ANAM stock persona · Dana voice · patient, upbeat support style";
    status.textContent = "READY";
  } else if (mode === "CREATE_NEW_ANAM") {
    small.textContent = "CREATION BRIEF";
    strong.textContent = "New ANAM persona";
    copy.textContent = "The Factory will prepare the brief; no provider creation occurs in this draft.";
    status.textContent = "GATED";
  } else if (mode === "STOCK_IMAGE") {
    small.textContent = "VISUAL FALLBACK";
    strong.textContent = "Owner-selected stock image";
    copy.textContent = "A stock image slot will be included without contacting an external provider.";
    status.textContent = "OPEN";
  } else {
    small.textContent = "TEXT-FIRST EXPERIENCE";
    strong.textContent = "No visual persona";
    copy.textContent = "The X-Agent remains fully usable without an avatar or image.";
    status.textContent = "READY";
  }
}

function resetFloor() {
  $$("#stations article").forEach((item) => {
    item.className = "";
    item.querySelector("mark").textContent = "QUEUED";
  });
  $("#progress").textContent = "0%";
  $("#rail-fill").style.width = "0%";
}

function setRunning() {
  document.body.classList.add("factory-building");
  setOwnerJourney("build", ["define", "personalize"]);
  resetFloor();
  const first = $('#stations article[data-stage="01"]');
  first.classList.add("active");
  first.querySelector("mark").textContent = "WORKING";
  $("#floor-summary").textContent = "Contained compiler is running";
  $("#progress").textContent = "10%";
  $("#rail-fill").style.width = "10%";
}

async function replayVerifiedStages(stages) {
  for (let index = 0; index < stages.length; index += 1) {
    const stage = stages[index];
    const item = $(`#stations article[data-stage="${stage.stage_id}"]`);
    $$("#stations article").forEach((row) => row.classList.remove("active"));
    item.classList.add(stage.status === "PASS" ? "done" : "failed");
    item.querySelector("mark").textContent = stage.status;
    item.querySelector("p").textContent = stage.detail;
    const percent = Math.round(((index + 1) / stages.length) * 100);
    $("#progress").textContent = `${percent}%`;
    $("#rail-fill").style.width = `${percent}%`;
    await new Promise((resolve) => window.setTimeout(resolve, 180));
  }
}

function artifactUrl(record, relative) {
  return `/api/missions/${encodeURIComponent(record.mission_id)}/files/${relative.split("/").map(encodeURIComponent).join("/")}`;
}

function repoArtifactUrl(repo, relative) {
  return `/api/repos/${encodeURIComponent(repo.repo_id)}/files/${relative.split("/").map(encodeURIComponent).join("/")}`;
}

function resetRuntimeFoundry() {
  currentRuntimePlan = null;
  $("#runtime-foundry").hidden = false;
  $("#runtime-status-title").textContent = "Knowledge Core required";
  $("#runtime-status-copy").textContent = "Attach and approve client knowledge to build a personalized runtime package.";
  $("#runtime-profile").textContent = "Not created";
  $("#runtime-plan").textContent = "Waiting for reviewed knowledge";
  $("#runtime-contract").textContent = "Waiting for reviewed knowledge";
  $("#runtime-canary").textContent = "Inactive";
  $("#runtime-plan-hash").textContent = "No runtime plan yet";
  $("#runtime-live-state").textContent = "INACTIVE";
  $("#runtime-test-message").disabled = true;
  $("#runtime-test-submit").disabled = true;
  $("#runtime-test-submit").textContent = "KNOWLEDGE REQUIRED";
  resetPreviewSession("Preview will unlock after reviewed knowledge is attached and the local build passes.");
  resetPreviewVerification();
}

function appendRuntimeMessage(label, copy, kind, technical = "") {
  const holder = $("#runtime-transcript");
  const message = document.createElement("div");
  message.className = `runtime-message ${kind}`;
  const small = document.createElement("small");
  small.textContent = label;
  const paragraph = document.createElement("p");
  paragraph.textContent = copy;
  message.append(small, paragraph);
  if (technical) {
    const detail = document.createElement("small");
    detail.className = "factory-technical runtime-technical";
    detail.textContent = technical;
    message.append(detail);
  }
  holder.append(message);
  holder.scrollTop = holder.scrollHeight;
}

function renderRuntimeFoundry(plan) {
  currentRuntimePlan = plan.status === "LOCAL_RUNTIME_PACKAGE_READY_CANARY_INACTIVE" ? plan : null;
  const ready = Boolean(currentRuntimePlan);
  const locallyCertified = plan.local_behavior_status === "LOCAL_BEHAVIOR_HARNESS_PASS";
  $("#runtime-status-title").textContent = ready ? (locallyCertified ? "Knowledge package sealed + provider-free checks passed" : "Knowledge package sealed") : "Knowledge Core required";
  $("#runtime-status-copy").textContent = ready
    ? (locallyCertified
      ? "Seven provider-free checks passed, including natural-language retrieval, safe unknown handling, and fresh-session isolation. No model or Hermes session is active in this preview."
      : "The named profile blueprint, system prompt, knowledge binding, and exact one-call canary are ready. Nothing has been installed or transmitted.")
    : "Attach and approve client knowledge to build a personalized runtime package.";
  $("#runtime-harness").textContent = "Provider-free matcher";
  $("#runtime-model").textContent = "NOT ACTIVE";
  $("#runtime-profile").textContent = ready ? `${plan.profile_blueprint.profile_id} · NOT INSTALLED` : "Not created";
  $("#runtime-plan").textContent = ready ? plan.plan_id : "Waiting for reviewed knowledge";
  $("#runtime-contract").textContent = ready ? `${plan.runtime_contract_status.replaceAll("_", " ")} · ${plan.runtime_contract_sha256.slice(0, 12)}…` : "Waiting for reviewed knowledge";
  $("#runtime-canary").textContent = ready ? (locallyCertified ? "LOCAL 7/7 PASS · HERMES PROOF INACTIVE" : `${plan.canary.canary_id} · INACTIVE`) : "Inactive";
  $("#runtime-plan-hash").textContent = ready ? `PLAN ${plan.plan_sha256}` : "No runtime plan yet";
  $("#runtime-live-state").textContent = ready ? "SEALED · OFF" : "GATED";
  $("#runtime-test-message").disabled = !ready;
  $("#runtime-test-submit").disabled = !ready;
  $("#runtime-test-submit").textContent = ready ? "TEST QUESTION →" : "KNOWLEDGE REQUIRED";
  const suggestions = $("#runtime-suggestions");
  suggestions.textContent = "";
  if (ready) {
    const cases = plan.suggested_questions || [];
    $("#runtime-test-message").placeholder = cases[0]?.question || plan.canary.question;
    cases.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `APPROVED · ${item.question}`;
      button.title = "This question is confirmed by the selected owner-approved knowledge package.";
      button.addEventListener("click", () => {
        $("#runtime-test-message").value = item.question;
        $("#runtime-test-message").focus();
      });
      suggestions.append(button);
    });
    resetPreviewSession(`Provider-free preview ready for ${plan.identity.agent_name}. No language model is active; answers come only from exact owner-approved statements.`);
    resetPreviewVerification();
  }
}

async function loadRuntimeFoundry(record) {
  const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/runtime-foundry`, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Runtime Foundry status is unavailable");
  renderRuntimeFoundry(data);
}

function resetRepoFoundry() {
  currentRepo = null;
  $("#repo-status-title").textContent = "Ready to package";
  $("#repo-status-copy").textContent = "After Rook's independent check, Porter automatically creates a new staging repository and runs its verification suite. It makes zero provider calls.";
  $("#repo-path").hidden = true;
  $("#repo-path").textContent = "";
  $("#open-repo-preview").hidden = true;
  $("#repo-artifacts").textContent = "";
  $("#copy-repo-path").hidden = true;
  $("#create-local-repo").disabled = true;
  $("#create-local-repo").textContent = "FACTORY WILL PACKAGE AFTER REVIEW";
  $("#prepare-repo-promotion").disabled = true;
  $("#prepare-repo-promotion").textContent = "CREATE LOCAL REPO FIRST";
}

function resetCompletionRunner() {
  currentCompletion = null;
  $("#mission-runner").hidden = false;
  $("#runner-status").textContent = "WAITING";
  $("#runner-review").textContent = "Prepared after certification";
  $("#runner-copy").innerHTML = "Rook checks the complete evidence chain without model calls. Hermes <code>/review</code> remains prepared but inactive until separately requested.";
  $("#retry-completion").hidden = true;
  $$("#runner-route article").forEach((item) => {
    item.classList.remove("working", "done", "failed");
    item.querySelector("b").textContent = "WAITING";
  });
}

function setCompletionWorking() {
  $("#mission-runner").hidden = false;
  $("#runner-status").textContent = "REVIEWING";
  $("#runner-review").textContent = "Rook is checking the certified candidate";
  $("#runner-copy").textContent = "The eight Factory stations are already complete, including Troy's System Prompt and Vera's certification. Rook is independently rerunning tests and checking the evidence boundary before Porter may package anything.";
  $("#retry-completion").hidden = true;
  $$("#runner-route article").forEach((item, index) => {
    item.classList.remove("working", "done", "failed");
    if (index < 5) {
      item.classList.add("done");
      item.querySelector("b").textContent = "PASS";
    } else if (index === 5) {
      item.classList.add("working");
      item.querySelector("b").textContent = "CHECKING";
    } else {
      item.querySelector("b").textContent = "WAITING";
    }
  });
}

function renderCompletion(completion, repo, options = {}) {
  if (!currentRecord || completion.mission_id !== currentRecord.mission_id) return;
  currentCompletion = completion;
  $("#mission-runner").hidden = false;
  $("#runner-status").textContent = "LOCAL X-AGENT BUILT";
  $("#runner-review").textContent = "Rook passed it to Porter";
  $("#runner-copy").textContent = `All ${completion.route.length} stations passed. Rook independently reran the tests; Porter packaged the local X-Agent. Open and preview it before requesting any governed runtime or release action. Hermes /review remains prepared, not invoked.`;
  $("#retry-completion").hidden = true;
  $$("#runner-route article").forEach((item) => {
    item.classList.remove("working", "failed");
    item.classList.add("done");
    item.querySelector("b").textContent = "PASS";
  });
  $("#result-summary").textContent = `${currentRecord.agent.agent_name} passed the build, independent review, and complete local-app packaging checks.`;
  renderRepoFoundry(repo);
  if (options.scroll !== false) $("#mission-runner").scrollIntoView({behavior: "smooth", block: "start"});
}

function renderCompletionFailure(message) {
  $("#mission-runner").hidden = false;
  $("#runner-status").textContent = "STOPPED SAFELY";
  $("#runner-review").textContent = "The candidate is intact";
  $("#runner-copy").textContent = message;
  const active = $("#runner-route article.working") || $$("#runner-route article")[5];
  active.classList.remove("working", "done");
  active.classList.add("failed");
  active.querySelector("b").textContent = "BLOCKED";
  $("#retry-completion").hidden = false;
}

async function loadCompletionStatus(record) {
  const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/completion`, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Completion status is unavailable");
  if (!data.completion || currentRecord?.mission_id !== record.mission_id) return false;
  const repoResponse = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/repo`, {cache: "no-store"});
  const repoData = await repoResponse.json();
  if (!repoResponse.ok || !repoData.repo) throw new Error(repoData.error || "Porter's completed repository is unavailable");
  renderCompletion(data.completion, repoData.repo, {scroll: false});
  return true;
}

async function completeMission(record, options = {}) {
  if (!record || currentCompletion?.mission_id === record.mission_id) return;
  setCompletionWorking();
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/complete`, {method: "POST"});
    const completion = await response.json();
    if (!response.ok) throw new Error(completion.error || "The automatic local finish stopped safely");
    const repoResponse = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/repo`, {cache: "no-store"});
    const repoData = await repoResponse.json();
    if (!repoResponse.ok || !repoData.repo) throw new Error(repoData.error || "Porter completed, but the repository record could not be read");
    renderCompletion(completion, repoData.repo, options);
  } catch (error) {
    renderCompletionFailure(error instanceof Error ? error.message : String(error));
  }
}

function resetOwnerControl() {
  currentOwnerControl = null;
  $("#governed-run-hash").hidden = true;
  $("#governed-run-hash").textContent = "";
  $("#governed-run-status").textContent = "Preparation is local and makes zero provider calls.";
  $("#prepare-governed-run").disabled = false;
  $("#prepare-governed-run").textContent = "PREPARE GOVERNED REVIEW";
  $("#request-governed-run").hidden = true;
  $("#request-governed-run").disabled = false;
  $("#request-governed-run").textContent = "REQUEST REVIEW EXECUTION";
  $("#semantic-result").hidden = true;
  $("#semantic-result").textContent = "";
  $("#promotion-target").hidden = true;
  $("#promotion-target").textContent = "";
  $("#promotion-status").textContent = "Create and verify the local repo before preparing this handoff.";
  $("#prepare-repo-promotion").disabled = true;
  $("#prepare-repo-promotion").textContent = "CREATE LOCAL REPO FIRST";
  $("#request-repo-promotion").hidden = true;
  $("#request-repo-promotion").disabled = false;
  $("#request-repo-promotion").textContent = "REQUEST OFFICIAL REPO CREATION";
}

function renderGovernedRunPlan(plan, request = null, semanticResult = null) {
  $("#governed-run-hash").hidden = false;
  $("#governed-run-hash").textContent = `PLAN ${plan.plan_sha256}`;
  $("#prepare-governed-run").disabled = true;
  $("#prepare-governed-run").textContent = "REVIEW PLAN PREPARED";
  const requestButton = $("#request-governed-run");
  if (semanticResult?.status === "HERMES_SEMANTIC_REVIEW_PASS") {
    requestButton.hidden = true;
    $("#semantic-result").hidden = false;
    $("#semantic-result").textContent = `CERTIFIED · ${semanticResult.calls} Luna calls · Atlas, Aria, and Vera passed · ${semanticResult.review_id}`;
    $("#governed-run-status").textContent = "This exact mission is already semantically certified. Mission Control will not request duplicate provider work.";
  } else if (request) {
    requestButton.hidden = false;
    requestButton.disabled = true;
    requestButton.textContent = "REVIEW EXECUTION REQUESTED";
    $("#governed-run-status").textContent = "Owner request recorded locally. A separate guarded executor must still validate the exact plan before any provider call.";
  } else {
    requestButton.hidden = false;
    requestButton.disabled = false;
    requestButton.textContent = "REQUEST REVIEW EXECUTION";
    $("#governed-run-status").textContent = "Plan prepared locally. Requesting records your decision; it does not make provider calls.";
  }
}

function renderPromotionPlan(plan, request = null, execution = null) {
  $("#promotion-target").hidden = false;
  $("#promotion-target").textContent = plan.target.path;
  $("#prepare-repo-promotion").disabled = true;
  $("#prepare-repo-promotion").textContent = plan.status === "BLOCKED_TARGET_EXISTS" ? "TARGET ALREADY EXISTS" : "HANDOFF PLAN PREPARED";
  const requestButton = $("#request-repo-promotion");
  if (execution?.status === "OFFICIAL_LOCAL_REPO_CREATED") {
    requestButton.hidden = false;
    requestButton.disabled = true;
    requestButton.textContent = "OFFICIAL REPO CREATED · TESTS PASS";
    $("#promotion-status").textContent = `Created and verified at ${execution.target}. X-Link installation, deployment, and production remain locked.`;
  } else if (plan.status === "BLOCKED_TARGET_EXISTS") {
    requestButton.hidden = true;
    $("#promotion-status").textContent = "Porter found an existing destination and blocked the handoff before any write.";
  } else if (request) {
    requestButton.hidden = false;
    requestButton.disabled = true;
    requestButton.textContent = "OFFICIAL REPO CREATION REQUESTED";
    $("#promotion-status").textContent = "Owner request recorded locally. The separate guarded executor still must recheck every hash, boundary, and target before copying.";
  } else {
    requestButton.hidden = false;
    requestButton.disabled = false;
    requestButton.textContent = "REQUEST OFFICIAL REPO CREATION";
    $("#promotion-status").textContent = "Plan prepared locally. Requesting records your decision; it does not copy files.";
  }
}

async function loadOwnerControl(record) {
  const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/owner-control`, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Owner Control is unavailable");
  currentOwnerControl = data;
  if (data.governed_run) renderGovernedRunPlan(data.governed_run, data.governed_run_request, data.semantic_result);
  if (data.repo_promotion) renderPromotionPlan(data.repo_promotion, data.repo_promotion_request, data.repo_promotion_execution);
}

function renderRepoFoundry(repo) {
  currentRepo = repo;
  setOwnerJourney(null, ["define", "personalize", "build", "preview", "release"]);
  $("#repo-status-title").textContent = "Complete local app ready";
  $("#repo-status-copy").textContent = `${Object.keys(repo.files || {}).length} application files were created and the local tests passed. You can open the app now; official release remains a later controlled step.`;
  $("#repo-path").hidden = false;
  $("#repo-path").textContent = repo.local_path;
  const preview = $("#open-repo-preview");
  preview.hidden = false;
  preview.href = repo.preview_url;
  $("#copy-repo-path").hidden = false;
  $("#create-local-repo").disabled = true;
  $("#create-local-repo").textContent = "COMPLETE APP READY ✓";
  refreshNovaSync();
  if (!currentOwnerControl?.repo_promotion) {
    $("#prepare-repo-promotion").disabled = !repo.authority?.runtime_approved;
    $("#prepare-repo-promotion").textContent = repo.authority?.runtime_approved ? "PREPARE OFFICIAL HANDOFF" : "OFFICIAL HANDOFF · RUNTIME TEST REQUIRED";
    $("#promotion-status").textContent = repo.authority?.runtime_approved ? "Preparation is local and does not copy or install anything." : "This is a staging repo. Official creation unlocks only after the guarded multi-turn runtime proof passes.";
  }
  const holder = $("#repo-artifacts");
  holder.textContent = "";
  const labels = {readme: "README", porter_handoff: "Porter handoff", independent_review: "Rook independent review", agent_instructions: "Agent instructions", agent_spec: "Agent specification", knowledge_bank: "Client Knowledge Bank", system_prompt: "Troy System Prompt", prompt_forge_manifest: "Troy Prompt Forge manifest", prompt_assumptions: "Troy assumptions", prompt_tests: "Troy prompt tests", prompt_owner_summary: "Troy build receipt", knowledge_traceability: "Knowledge traceability", knowledge_tests: "Knowledge tests", runtime_plan: "Runtime plan", runtime_profile_blueprint: "Hermes profile blueprint", runtime_canary_prompt: "Exact Luna canary prompt", runtime_canary_payload: "Exact Luna canary payload", runtime_activation_packet: "Inactive runtime canary packet", instance_runtime_contract: "Locked instance contract", runtime_behavior_plan: "Behavior proof plan", local_behavior_certification: "Local multi-turn certification", repo_manifest: "Repo manifest"};
  Object.entries(repo.artifacts || {}).forEach(([key, relative]) => {
    const link = document.createElement("a");
    link.href = repoArtifactUrl(repo, relative);
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = `${labels[key] || key} ↗`;
    holder.append(link);
  });
}

async function loadRepoStatus(record) {
  const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/repo`, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Repo Foundry status is unavailable");
  if (data.repo) renderRepoFoundry(data.repo);
}

function gateClass(status) {
  return status === "PASS" ? "pass" : "pending";
}

function setResultPresenceGates(descriptor) {
  const gates = descriptor.gates;
  [["#gate-local", gates.local_build], ["#gate-semantic", gates.semantic_review], ["#gate-anam", gates.anam_transport], ["#gate-activation", gates.activation_packet]].forEach(([selector, gate]) => {
    $(selector).className = gateClass(gate.status);
  });
  const ready = descriptor.status === "LIVE_ACTIVATION_PREPARED";
  $("#presence-gate-title").textContent = "Try your agent";
  $("#presence-gate-copy").textContent = ready
    ? "The safe local conversation and the selected visual identity are ready. Nothing will be deployed or published."
    : "Use the safe local conversation below. Live avatar activation remains a later controlled step.";
  $("#meet-agent").textContent = "START PREVIEW →";
}

async function fetchPresence(record) {
  const response = await fetch(`/api/missions/${encodeURIComponent(record.mission_id)}/presence-preview`, {cache: "no-store"});
  const descriptor = await response.json();
  if (!response.ok) throw new Error(descriptor.error || "Presence preview is unavailable");
  return descriptor;
}

function renderPresenceGates(gates) {
  const labels = {
    local_build: "LOCAL BUILD",
    semantic_review: "HERMES / LUNA",
    anam_transport: "ANAM TRANSPORT",
    activation_packet: "ACTIVATION PACKET",
  };
  const holder = $("#preview-gates");
  holder.textContent = "";
  Object.entries(gates).forEach(([key, gate]) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const status = document.createElement("b");
    label.textContent = labels[key] || key.replaceAll("_", " ").toUpperCase();
    status.textContent = gate.status;
    status.className = gateClass(gate.status);
    row.append(label, status);
    holder.append(row);
  });
}

async function pollPresenceRuntime() {
  if (!currentRecord || !currentPresence?.activation) return;
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/presence-runtime`, {cache: "no-store"});
    const runtime = await response.json();
    const launch = $("#launch-live-preview");
    launch.disabled = !runtime.launch_enabled;
    launch.textContent = runtime.launch_enabled ? `OPEN LIVE ${currentPresence.agent.persona.toUpperCase()} ↗` : "LIVE SESSION NOT ARMED";
    $("#preview-mode").textContent = runtime.launch_enabled ? "GOVERNED RUNTIME READY" : "STATIC LOCAL PREVIEW";
    $("#preview-runtime-copy").textContent = runtime.launch_enabled
      ? "The exact approved canary server is ready. Opening it does not start the provider session; Start remains a separate visible action."
      : "The live control remains locked until its exact activation packet is approved and running.";
  } catch {
    // The static preview remains usable if the runtime health check is unavailable.
  }
}

function renderPresencePreview(descriptor) {
  currentPresence = descriptor;
  $("#preview-persona").textContent = descriptor.agent.persona;
  $("#preview-agent-name").textContent = `${descriptor.agent.display_name} · ${descriptor.agent.presence_mode.replaceAll("_", " ")}`;
  $("#preview-persona-label").textContent = `${descriptor.agent.persona} · Support Guide`;
  $("#preview-voice").textContent = descriptor.persona.voice_style || "Text-first fallback";
  $("#preview-question").textContent = descriptor.speech.question;
  $("#preview-fallback").textContent = descriptor.speech.text_fallback;
  const portrait = $("#preview-portrait");
  portrait.hidden = !descriptor.persona.portrait_url;
  if (descriptor.persona.portrait_url) portrait.src = descriptor.persona.portrait_url;
  renderPresenceGates(descriptor.gates);
  const ready = descriptor.status === "LIVE_ACTIVATION_PREPARED";
  $("#preview-status").textContent = ready ? "Preview packet ready" : "Static preview only";
  const copy = $("#copy-preview-approval");
  copy.disabled = !descriptor.activation;
  copy.textContent = descriptor.activation ? "COPY ACTIVATION APPROVAL" : "ACTIVATION PACKET NOT READY";
  $("#launch-live-preview").disabled = true;
  $("#launch-live-preview").textContent = "LIVE SESSION NOT ARMED";
  $("#presence-preview").hidden = false;
  $("#presence-preview").scrollIntoView({behavior: "smooth", block: "start"});
  window.clearInterval(presencePoll);
  if (descriptor.activation) {
    pollPresenceRuntime();
    presencePoll = window.setInterval(pollPresenceRuntime, 1800);
  }
}

async function loadPresencePreview(show = true) {
  if (!currentRecord) return;
  const descriptor = await fetchPresence(currentRecord);
  setResultPresenceGates(descriptor);
  if (show) renderPresencePreview(descriptor);
}

function renderResult(record, options = {}) {
  document.body.classList.remove("factory-building");
  setOwnerJourney("preview", ["define", "personalize", "build"]);
  currentRecord = record;
  refreshNovaSync(record);
  resetRepoFoundry();
  resetCompletionRunner();
  resetOwnerControl();
  resetRuntimeFoundry();
  $("#result-name").textContent = ownerFacingName(record.agent);
  $("#result-purpose").textContent = record.agent.purpose;
  $("#result-mission").textContent = record.mission_id;
  $("#result-digest").textContent = record.build.root_digest;
  $("#result-summary").textContent = `${record.agent.agent_name} passed the local build checks. Try the preview below, then prepare the complete local application when you are happy with it.`;
  const knowledgeReady = record.knowledge?.status === "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED";
  const knowledgeCard = $("#instance-knowledge-status");
  knowledgeCard.classList.toggle("ready", knowledgeReady);
  knowledgeCard.classList.toggle("gated", !knowledgeReady);
  $("#instance-knowledge-title").textContent = knowledgeReady ? "Knowledge: Ready" : "Knowledge: Missing";
  $("#instance-knowledge-copy").textContent = knowledgeReady
    ? "Your approved information was built into this agent and passed the local knowledge checks."
    : "This agent will honestly hand unknown company questions to a person.";
  $("#instance-knowledge-count").textContent = knowledgeReady ? "READY" : "MISSING";
  $("#result-persona").textContent = record.agent.presence_mode === "EXISTING_ANAM" ? `${record.agent.persona.toUpperCase()} · FACTORY RECOMMENDED` : record.agent.presence_mode.replaceAll("_", " ");
  $("#result-avatar").hidden = record.agent.presence_mode === "TEXT_ONLY";

  const chips = $("#module-chips");
  chips.textContent = "";
  const friendlyCapabilities = {
    "CMP-APPROVED-KNOWLEDGE-ANSWERS": "FAQ answers",
    "CMP-STRUCTURED-SESSION-SNAPSHOT": "Visible notes",
    "CMP-HUMAN-REVIEW-HANDOFF": "Staff handoff",
    "CMP-ANAM-PRESENCE-SHELL": "Avatar",
    "CMP-CLIENT-KNOWLEDGE-PACK": "Client knowledge",
    "CMP-APPOINTMENT-REQUEST-PACKET": "Appointment request",
    "CMP-LEAD-QUALIFICATION-SCORECARD": "Qualification",
  };
  record.modules.filter((module) => friendlyCapabilities[module.component_id]).forEach((module) => {
    const chip = document.createElement("span");
    chip.textContent = friendlyCapabilities[module.component_id];
    chips.append(chip);
  });

  const links = $("#artifact-links");
  links.textContent = "";
  Object.entries(record.artifacts).forEach(([key, relative]) => {
    const anchor = document.createElement("a");
    anchor.href = artifactUrl(record, relative);
    anchor.target = "_blank";
    anchor.rel = "noopener";
    anchor.textContent = `${artifactLabels[key] || key} ↗`;
    links.append(anchor);
  });
  $("#result").hidden = false;
  $("#repo-foundry").hidden = false;
  $("#owner-control").hidden = false;
  loadRepoStatus(record).catch(() => {
    $("#repo-status-copy").textContent = "The candidate is intact, but Porter could not read the local repo yard.";
  });
  loadCompletionStatus(record).catch((error) => {
    renderCompletionFailure(error instanceof Error ? error.message : String(error));
  });
  loadOwnerControl(record).catch(() => {
    $("#governed-run-status").textContent = "Owner Control could not read its local plan store.";
  });
  loadRuntimeFoundry(record).catch(() => {
    $("#runtime-status-title").textContent = "Runtime package unavailable";
    $("#runtime-status-copy").textContent = "The candidate remains intact, but the Runtime Foundry package did not pass its local read check.";
  });
  loadPresencePreview(false).catch(() => {
    $("#presence-gate-copy").textContent = "The static candidate is intact, but its presence descriptor could not be loaded.";
  });
  if (options.scroll !== false) $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function missionPayload() {
  return {
    purpose: $("#purpose").value.trim(),
    agent_or_client: $("#agent-or-client").value.trim(),
    x_agent_name: $("#x-agent-name").value.trim() || null,
    client_name: $("#client-name").value.trim() || null,
    role_title: $("#agent-or-client").value.trim(),
    personality: $("#personality").value.trim(),
    must_accomplish: $("#must-accomplish").value.trim(),
    never_do: $("#never-do").value.trim(),
    target_users: $("#target-users").value.trim(),
    output_artifact: $("#output-artifact").value.trim(),
    presence_mode: presenceMode,
    persona_catalog_id: presenceMode === "EXISTING_ANAM" ? "ANAM-STOCK-MIA-SUPPORT-GUIDE" : null,
  };
}

function applyBrief(brief, sourceMission = null) {
  $("#owner-purpose").value = brief.purpose || "";
  $("#purpose-recommendation").textContent = brief.purpose ? "Loaded the original owner intent. You can revise it before recommissioning." : "Tell us the job first. Atlas will recommend the closest proven starting point.";
  if (brief.commissioning) {
    const commissioning = brief.commissioning;
    selectedKnowledgePackageId = commissioning.knowledge_package?.package_id || null;
    selectedOptionalModules = new Set(commissioning.selected_optional_modules || []);
    syncKnowledgeModule();
    renderKnowledgePackages();
    renderModuleOptions();
    $("#commission-agent-name").value = commissioning.x_agent_name || brief.agent_name || "";
    $("#commission-client-name").value = commissioning.client_name || brief.client_name || "";
    $("#commission-role-title").value = commissioning.role_title || brief.role_title || "";
    $("#commission-personality").value = brief.personality || "";
    $("#commission-target-users").value = Array.isArray(brief.target_users) ? brief.target_users.join("; ") : (brief.target_users || "");
    $("#commission-client-context").value = commissioning.client_context || "";
    $("#commission-requirements").value = "";
    $("#commission-boundaries").value = "";
    $("#commissioning-form").hidden = false;
    setBlankWorkbench(false);
    setCommissioningPresence(brief.presence_mode || "TEXT_ONLY");
    updateCommissionButton();
    const commissioningNote = $("#commissioning-note");
    commissioningNote.hidden = !sourceMission;
    commissioningNote.textContent = sourceMission ? `Commissioning revision loaded from ${sourceMission}. Recommissioning creates a new immutable mission; the original remains preserved.` : "";
    $("#commissioning-form").scrollIntoView({behavior: "smooth", block: "start"});
    $("#commission-agent-name").focus({preventScroll: true});
    return;
  }
  setBlankWorkbench(true);
  $("#purpose").value = brief.purpose || "";
  $("#agent-or-client").value = brief.role_title || brief.agent_or_client || brief.display_name || "";
  $("#x-agent-name").value = brief.agent_name && brief.agent_name !== brief.role_title ? brief.agent_name : "";
  $("#client-name").value = brief.client_name || brief.agent_or_client || "";
  $("#personality").value = brief.personality || "";
  $("#must-accomplish").value = Array.isArray(brief.must_accomplish) ? brief.must_accomplish.join("; ") : (brief.must_accomplish || "");
  $("#never-do").value = Array.isArray(brief.never_do) ? brief.never_do.join("; ") : (brief.never_do || "");
  $("#target-users").value = Array.isArray(brief.target_users) ? brief.target_users.join("; ") : (brief.target_users || "");
  $("#output-artifact").value = brief.output_artifact || "";
  setPresence(brief.presence_mode || "TEXT_ONLY");
  const note = $("#revision-note");
  note.hidden = !sourceMission;
  note.textContent = sourceMission ? `Revision loaded from ${sourceMission}. Running creates a new immutable mission; the original is preserved.` : "";
  $("#mission-form").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#purpose").focus({ preventScroll: true });
}

async function loadBriefForRevision(missionId) {
  const response = await fetch(`/api/missions/${encodeURIComponent(missionId)}/brief`);
  const brief = await response.json();
  if (!response.ok) throw new Error(brief.error || "Could not load owner brief");
  if (brief.commissioning && currentChassis?.chassis_id !== brief.commissioning.chassis_id) {
    const chassisResponse = await fetch(`/api/chassis/${encodeURIComponent(brief.commissioning.chassis_id)}`, {cache: "no-store"});
    const chassis = await chassisResponse.json();
    if (!chassisResponse.ok) throw new Error(chassis.error || "The source chassis is unavailable");
    openCommissioning(chassis);
  }
  applyBrief(brief, missionId);
}

async function loadRecent() {
  try {
    const response = await fetch("/api/missions");
    if (!response.ok) return;
    const data = await response.json();
    const list = $("#recent-list");
    list.textContent = "";
    if (!data.missions.length) {
      const empty = document.createElement("p");
      empty.textContent = "No interactive missions yet.";
      list.append(empty);
      return;
    }
    data.missions.forEach((record) => {
      const row = document.createElement("article");
      const copy = document.createElement("div");
      const name = document.createElement("strong");
      const detail = document.createElement("small");
      const code = document.createElement("code");
      const actions = document.createElement("div");
      const open = document.createElement("button");
      const revise = document.createElement("button");
      const link = document.createElement("a");
      name.textContent = ownerFacingName(record.agent);
      detail.textContent = record.agent.derived_from_chassis
        ? `COMMISSIONED FROM ${record.agent.derived_from_chassis.chassis_id.replaceAll("-", " ").toUpperCase()} · ${record.modules.length} modules`
        : `${record.status.replaceAll("_", " ")} · ${record.modules.length} modules`;
      code.textContent = record.mission_id;
      link.href = `/api/missions/${encodeURIComponent(record.mission_id)}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "RECORD ↗";
      revise.type = "button";
      revise.textContent = "REVISE";
      open.type = "button";
      open.textContent = "OPEN";
      open.addEventListener("click", () => renderResult(record));
      revise.addEventListener("click", async () => {
        try { await loadBriefForRevision(record.mission_id); }
        catch (error) { $("#form-error").textContent = error instanceof Error ? error.message : String(error); }
      });
      copy.append(name, detail);
      actions.className = "ledger-actions";
      actions.append(open, revise, link);
      row.append(copy, code, actions);
      list.append(row);
    });
  } catch {
    // The status banner already communicates server connectivity.
  }
}

async function connectStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("status unavailable");
    const status = await response.json();
    $("#system-state").textContent = `${status.status} · LOCAL ONLY`;
  } catch {
    $("#system-state").textContent = "SERVER NOT CONNECTED";
  }
}

$$('[data-presence]').forEach((button) => button.addEventListener("click", () => setPresence(button.dataset.presence)));

$("#mission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $(".run-button");
  const error = $("#form-error");
  error.textContent = "";
  button.disabled = true;
  button.querySelector("span").textContent = "BUILDING CONTAINED CANDIDATE";
  setRunning();
  try {
    const response = await fetch("/api/missions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(missionPayload()) });
    const record = await response.json();
    if (!response.ok) throw new Error(record.error || "Factory build failed");
    await replayVerifiedStages(record.specialists);
    $("#floor-summary").textContent = "Verified local candidate ready";
    renderResult(record, {scroll: false});
    await completeMission(record);
    await loadRecent();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
    $("#floor-summary").textContent = "Build stopped safely";
    const active = $("#stations article.active");
    if (active) {
      active.classList.remove("active");
      active.classList.add("failed");
      active.querySelector("mark").textContent = "BLOCKED";
    }
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "BUILD BLANK-SLATE X-AGENT";
  }
});

$("#copy-record").addEventListener("click", async () => {
  if (!currentRecord) return;
  await navigator.clipboard.writeText(JSON.stringify(currentRecord, null, 2));
  $("#copy-record").textContent = "COPIED";
  window.setTimeout(() => { $("#copy-record").textContent = "COPY BUILD RECORD"; }, 900);
});

$("#revise-agent").addEventListener("click", async () => {
  if (!currentRecord) return;
  try { await loadBriefForRevision(currentRecord.mission_id); }
  catch (error) { $("#form-error").textContent = error instanceof Error ? error.message : String(error); }
});

$("#meet-agent").addEventListener("click", async () => {
  try {
    if (!currentRuntimePlan && currentRecord) await loadRuntimeFoundry(currentRecord);
    $("#runtime-foundry").scrollIntoView({behavior: "smooth", block: "start"});
    if (currentRuntimePlan) $("#runtime-test-message").focus({preventScroll: true});
  } catch (error) {
    $("#presence-gate-copy").textContent = error instanceof Error ? error.message : String(error);
  }
});

$("#close-presence-preview").addEventListener("click", () => {
  $("#presence-preview").hidden = true;
  window.clearInterval(presencePoll);
});

$("#copy-preview-approval").addEventListener("click", async () => {
  if (!currentPresence?.activation) return;
  await navigator.clipboard.writeText(currentPresence.activation.approval_text);
  $("#copy-preview-approval").textContent = "APPROVAL COPIED";
  window.setTimeout(() => { $("#copy-preview-approval").textContent = "COPY ACTIVATION APPROVAL"; }, 1200);
});

$("#launch-live-preview").addEventListener("click", () => {
  if (!currentPresence?.activation || $("#launch-live-preview").disabled) return;
  window.open(currentPresence.activation.runtime_url, "_blank", "noopener");
});

$("#create-local-repo").addEventListener("click", async () => {
  if (!currentRecord || currentRepo || !previewReady()) return;
  const button = $("#create-local-repo");
  button.disabled = true;
  button.textContent = "PORTER IS PACKAGING…";
  $("#repo-status-title").textContent = "Building the repo";
  $("#repo-status-copy").textContent = "Copying only certified artifacts, creating the runnable shell, checking for credentials, and running repository tests.";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/repo`, {method: "POST"});
    const repo = await response.json();
    if (!response.ok) throw new Error(repo.error || "Repo Foundry failed");
    renderRepoFoundry(repo);
    $("#repo-foundry").scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    button.disabled = false;
    button.textContent = "TRY REPO FOUNDRY AGAIN";
    $("#repo-status-title").textContent = "Porter stopped safely";
    $("#repo-status-copy").textContent = error instanceof Error ? error.message : String(error);
  }
});

$("#retry-completion").addEventListener("click", async () => {
  if (!currentRecord) return;
  await completeMission(currentRecord);
});

$("#copy-repo-path").addEventListener("click", async () => {
  if (!currentRepo) return;
  await navigator.clipboard.writeText(currentRepo.local_path);
  $("#copy-repo-path").textContent = "PATH COPIED";
  window.setTimeout(() => { $("#copy-repo-path").textContent = "COPY REPO PATH"; }, 1000);
});

$("#prepare-governed-run").addEventListener("click", async () => {
  if (!currentRecord) return;
  const button = $("#prepare-governed-run");
  button.disabled = true;
  button.textContent = "HASHING REVIEW INPUTS…";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/owner-control/governed-run`, {method: "POST"});
    const plan = await response.json();
    if (!response.ok) throw new Error(plan.error || "Could not prepare governed review");
    currentOwnerControl = {...(currentOwnerControl || {}), governed_run: plan};
    renderGovernedRunPlan(plan, null, currentOwnerControl?.semantic_result);
  } catch (error) {
    button.disabled = false;
    button.textContent = "PREPARE GOVERNED REVIEW";
    $("#governed-run-status").textContent = error instanceof Error ? error.message : String(error);
  }
});

$("#prepare-repo-promotion").addEventListener("click", async () => {
  if (!currentRecord || !currentRepo) return;
  const button = $("#prepare-repo-promotion");
  button.disabled = true;
  button.textContent = "CHECKING OFFICIAL TARGET…";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/owner-control/repo-promotion`, {method: "POST"});
    const plan = await response.json();
    if (!response.ok) throw new Error(plan.error || "Could not prepare repository handoff");
    currentOwnerControl = {...(currentOwnerControl || {}), repo_promotion: plan};
    renderPromotionPlan(plan, null);
  } catch (error) {
    button.disabled = false;
    button.textContent = "PREPARE OFFICIAL HANDOFF";
    $("#promotion-status").textContent = error instanceof Error ? error.message : String(error);
  }
});

$("#request-governed-run").addEventListener("click", async () => {
  if (!currentRecord || !currentOwnerControl?.governed_run) return;
  const button = $("#request-governed-run");
  button.disabled = true;
  button.textContent = "RECORDING OWNER REQUEST…";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/owner-control/governed-run/request`, {method: "POST"});
    const request = await response.json();
    if (!response.ok) throw new Error(request.error || "Could not record review request");
    currentOwnerControl.governed_run_request = request;
    renderGovernedRunPlan(currentOwnerControl.governed_run, request, currentOwnerControl.semantic_result);
  } catch (error) {
    button.disabled = false;
    button.textContent = "REQUEST REVIEW EXECUTION";
    $("#governed-run-status").textContent = error instanceof Error ? error.message : String(error);
  }
});

$("#request-repo-promotion").addEventListener("click", async () => {
  if (!currentRecord || !currentOwnerControl?.repo_promotion) return;
  const button = $("#request-repo-promotion");
  button.disabled = true;
  button.textContent = "RECORDING OWNER REQUEST…";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/owner-control/repo-promotion/request`, {method: "POST"});
    const request = await response.json();
    if (!response.ok) throw new Error(request.error || "Could not record repository request");
    currentOwnerControl.repo_promotion_request = request;
    renderPromotionPlan(currentOwnerControl.repo_promotion, request);
  } catch (error) {
    button.disabled = false;
    button.textContent = "REQUEST OFFICIAL REPO CREATION";
    $("#promotion-status").textContent = error instanceof Error ? error.message : String(error);
  }
});

$$('[data-commission-presence]').forEach((button) => button.addEventListener("click", () => setCommissioningPresence(button.dataset.commissionPresence)));

$("#toggle-blank-build").addEventListener("click", () => {
  const open = $("#mission-form").hidden;
  setBlankWorkbench(open);
  if (open) $("#mission-form").scrollIntoView({behavior: "smooth", block: "start"});
});

$("#toggle-factory-details").addEventListener("click", () => {
  setFactoryDetails(!document.body.classList.contains("factory-details-open"));
});

$("#global-factory-details").addEventListener("click", () => {
  setFactoryDetails(!document.body.classList.contains("factory-details-open"));
});

$("#purpose-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await recommendFromPurpose();
});

$("#owner-purpose").addEventListener("input", () => {
  clearRecommendation();
  if (!currentChassis) return;
  currentChassis = null;
  $("#commissioning-form").hidden = true;
  $("#purpose-recommendation").textContent = "Your job description changed. Ask Atlas to match it again before personalizing.";
  setOwnerJourney("define");
});

$("#load-morning-example").addEventListener("click", async () => {
  $("#owner-purpose").value = "Answer approved questions about XYZ Data, qualify customer inquiries, maintain visible notes, and prepare a structured handoff for staff review.";
  const recommendation = await recommendFromPurpose();
  if (!recommendation) return;
  openCommissioning(recommendation.recommended);
  $("#commission-agent-name").value = "Ava";
  $("#commission-client-name").value = "XYZ Data";
  $("#commission-personality").value = "Friendly, smart, concise, and transparent";
  $("#commission-target-users").value = "Prospective and existing XYZ Data customers";
  $("#commission-client-context").value = "XYZ Data uses this local example to answer approved questions and prepare staff handoffs.";
  $("#commission-boundaries").value = "Never invent pricing; never promise availability; never send or book anything";
  $("#quick-knowledge-text").value = "Q: What can you help with?\nA: I can answer approved questions about XYZ Data, qualify an inquiry, and prepare a clean handoff for staff.\n\nQ: Can you provide final pricing?\nA: No. Final pricing requires staff review after the request details are confirmed.\n\nQ: Can you promise availability?\nA: No. Staff confirms availability after reviewing the request.";
  updateCommissionButton();
  $("#commissioning-form").scrollIntoView({behavior: "smooth", block: "start"});
  $("#commission-agent-name").focus({preventScroll: true});
});

$("#use-recommendation").addEventListener("click", () => {
  if (!pendingRecommendation) return;
  openCommissioning(pendingRecommendation);
  $("#commissioning-form").scrollIntoView({behavior: "smooth", block: "start"});
  $("#commission-agent-name").focus({preventScroll: true});
});

$("#choose-another").addEventListener("click", () => {
  setFactoryDetails(true);
  $("#purpose-recommendation").textContent = "Choose any validated starting point below. Your job description remains in control.";
  $("#chassis-list").scrollIntoView({behavior: "smooth", block: "center"});
});

$("#fill-sample-knowledge").addEventListener("click", () => {
  $("#quick-knowledge-text").value = "Q: What can you help with?\nA: I can answer approved questions, qualify an inquiry, and prepare a clean handoff for staff.\n\nQ: Can you provide final pricing?\nA: No. Final pricing requires staff review after request details are confirmed.\n\nQ: Can you promise availability?\nA: No. Staff confirms availability after reviewing the request.";
  $("#quick-knowledge-text").focus();
});

$("#prepare-quick-knowledge").addEventListener("click", async () => {
  const button = $("#prepare-quick-knowledge");
  const content = $("#quick-knowledge-text").value.trim();
  if (content.length < 20) {
    setQuickKnowledgeStatus("Knowledge: Needs your input — add at least one approved fact or question and answer.", "needs-review");
    return;
  }
  button.disabled = true;
  button.textContent = "PREPARING…";
  setQuickKnowledgeStatus("Knowledge: Preparing and checking your approved notes…");
  try {
    const label = `${$("#commission-client-name").value.trim() || $("#commission-agent-name").value.trim() || "X Agent"} approved knowledge`;
    const createResponse = await fetch("/api/knowledge-packages", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({label, files: [{name: "owner-approved-notes.md", content}]})});
    const created = await createResponse.json();
    if (!createResponse.ok) throw new Error(created.error || "Could not prepare the knowledge notes");
    const approveResponse = await fetch(`/api/knowledge-packages/${encodeURIComponent(created.package_id)}/approve`, {method: "POST"});
    const approved = await approveResponse.json();
    if (!approveResponse.ok) throw new Error(approved.error || "Could not approve the exact knowledge package");
    const compileResponse = await fetch(`/api/knowledge-packages/${encodeURIComponent(created.package_id)}/compile`, {method: "POST"});
    const compilation = await compileResponse.json();
    if (!compileResponse.ok) throw new Error(compilation.error || "Could not prepare the knowledge review");
    await loadKnowledgePackages();
    if (compilation.conflicts?.length) {
      currentCompilation = compilation;
      renderReviewDesk(compilation);
      setFactoryDetails(true);
      setQuickKnowledgeStatus("Knowledge: Needs review — we found conflicting information. Choose the correct version below.", "needs-review");
      return;
    }
    if (!compilation.entries?.length) throw new Error("No usable facts or question-and-answer pairs were found");
    const decisions = compilation.entries.map((entry) => ({entry_id: entry.entry_id, decision: "APPROVE"}));
    const reviewResponse = await fetch(`/api/knowledge-packages/${encodeURIComponent(created.package_id)}/compilation/review`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({compilation_id: compilation.compilation_id, decisions})});
    const reviewed = await reviewResponse.json();
    if (!reviewResponse.ok) throw new Error(reviewed.error || "Could not finish the knowledge review");
    selectedKnowledgePackageId = created.package_id;
    syncKnowledgeModule();
    await loadKnowledgePackages();
    renderModuleOptions();
    setQuickKnowledgeStatus(`Knowledge: Ready — ${reviewed.latest_review.approved_count} approved item${reviewed.latest_review.approved_count === 1 ? "" : "s"} will be built into ${$("#commission-agent-name").value.trim() || "this agent"}.`, "ready");
    updateCommissionButton();
  } catch (error) {
    setQuickKnowledgeStatus(`Knowledge: Needs your input — ${error instanceof Error ? error.message : String(error)}`, "needs-review");
  } finally {
    button.disabled = false;
    button.textContent = "ADD THIS KNOWLEDGE →";
  }
});

$("#capture-website-knowledge").addEventListener("click", async () => {
  const input = $("#website-knowledge-url");
  const button = $("#capture-website-knowledge");
  const resultBox = $("#website-capture-result");
  const status = $("#website-knowledge-status");
  if (!input.reportValidity()) return;
  button.disabled = true;
  button.textContent = "CAPTURING PUBLIC PAGES…";
  resultBox.hidden = false;
  $("#review-website-knowledge").hidden = true;
  status.textContent = "Checking the public website within the six-page, same-site boundary…";
  try {
    const ownerLabel = $("#commission-client-name").value.trim() || $("#commission-agent-name").value.trim() || "X-Agent";
    const response = await fetch("/api/website-knowledge", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({url: input.value.trim(), label: `${ownerLabel} website knowledge`}),
    });
    const captured = await response.json();
    if (!response.ok) throw new Error(captured.error || "Website capture stopped safely");
    selectedBeforeWebsiteCaptureId = selectedKnowledgePackageId;
    capturedWebsitePackageId = captured.package_id;
    selectedKnowledgePackageId = null;
    syncKnowledgeModule();
    await loadKnowledgePackages();
    renderModuleOptions();
    const pageCount = captured.website_capture?.pages?.length || captured.files.length;
    status.textContent = `Captured ${pageCount} public page${pageCount === 1 ? "" : "s"}. Build is paused so older sample knowledge cannot be used by mistake. Review these website facts next.`;
    $("#review-website-knowledge").hidden = false;
    $("#discard-website-knowledge").hidden = false;
    setQuickKnowledgeStatus("Knowledge: Website review required — the previously selected pack is paused until you finish or discard this capture.", "needs-review");
    updateCommissionButton();
  } catch (error) {
    capturedWebsitePackageId = null;
    status.textContent = `Capture stopped safely — ${error instanceof Error ? error.message : String(error)}`;
  } finally {
    button.disabled = false;
    button.textContent = "CAPTURE FOR REVIEW →";
  }
});

$("#discard-website-knowledge").addEventListener("click", async () => {
  const previous = selectedBeforeWebsiteCaptureId;
  capturedWebsitePackageId = null;
  selectedBeforeWebsiteCaptureId = null;
  selectedKnowledgePackageId = knowledgePackages.some((item) => item.package_id === previous && item.compilation?.status === "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD") ? previous : null;
  syncKnowledgeModule();
  $("#website-capture-result").hidden = true;
  $("#review-website-knowledge").hidden = true;
  $("#discard-website-knowledge").hidden = true;
  await loadKnowledgePackages();
  renderModuleOptions();
  setQuickKnowledgeStatus(selectedKnowledgePackageId ? "Knowledge: Previous reviewed package restored for this build." : "Knowledge: Missing — add or select reviewed knowledge before expecting grounded answers.", selectedKnowledgePackageId ? "ready" : "needs-review");
  updateCommissionButton();
});

$("#review-website-knowledge").addEventListener("click", async () => {
  if (!capturedWebsitePackageId) return;
  const button = $("#review-website-knowledge");
  const status = $("#website-knowledge-status");
  button.disabled = true;
  button.textContent = "PREPARING REVIEW…";
  try {
    const approveResponse = await fetch(`/api/knowledge-packages/${encodeURIComponent(capturedWebsitePackageId)}/approve`, {method: "POST"});
    const approved = await approveResponse.json();
    if (!approveResponse.ok) throw new Error(approved.error || "Could not approve the captured source package for review");
    const compileResponse = await fetch(`/api/knowledge-packages/${encodeURIComponent(capturedWebsitePackageId)}/compile`, {method: "POST"});
    const compilation = await compileResponse.json();
    if (!compileResponse.ok) throw new Error(compilation.error || "Could not extract reviewable website knowledge");
    await loadKnowledgePackages();
    setFactoryDetails(true);
    renderReviewDesk(compilation);
    status.textContent = "Review every extracted item below. Only checked items can become approved knowledge.";
    button.hidden = true;
  } catch (error) {
    status.textContent = `Review preparation stopped safely — ${error instanceof Error ? error.message : String(error)}`;
    button.disabled = false;
    button.textContent = "REVIEW CAPTURED KNOWLEDGE →";
  }
});

$("#commission-agent-name").addEventListener("input", updateCommissionButton);

$("#close-review-desk").addEventListener("click", () => {
  $("#knowledge-review-desk").hidden = true;
});

$("#toggle-package-history").addEventListener("click", () => {
  showKnowledgePackageHistory = !showKnowledgePackageHistory;
  renderKnowledgePackages();
});

$("#review-safe-defaults").addEventListener("click", () => {
  $$("#knowledge-review-entries input[type=checkbox]").forEach((toggle) => { toggle.checked = toggle.dataset.recommended === "true" && !toggle.dataset.conflict; });
  updateReviewCount();
});

$("#review-clear").addEventListener("click", () => {
  $$("#knowledge-review-entries input[type=checkbox]").forEach((toggle) => { toggle.checked = false; });
  updateReviewCount();
});

$("#finalize-knowledge-review").addEventListener("click", async () => {
  if (!currentCompilation) return;
  const button = $("#finalize-knowledge-review");
  const error = $("#review-error");
  error.textContent = "";
  const decisions = $$("#knowledge-review-entries input[type=checkbox]").map((toggle) => ({entry_id: toggle.dataset.entryId, decision: toggle.checked ? "APPROVE" : "REJECT"}));
  button.disabled = true;
  button.textContent = "HASHING OWNER REVIEW…";
  try {
    const response = await fetch(`/api/knowledge-packages/${encodeURIComponent(currentCompilation.package_id)}/compilation/review`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({compilation_id: currentCompilation.compilation_id, decisions})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Owner review stopped safely");
    if (result.latest_review?.status === "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD") {
      selectedKnowledgePackageId = result.package_id;
      syncKnowledgeModule();
      $("#knowledge-review-desk").hidden = true;
      $("#knowledge-error").textContent = `${result.latest_review.approved_count} entries approved and ${result.latest_review.rejected_count} rejected. The reviewed package is selected for this commissioned build.`;
      setQuickKnowledgeStatus(`Knowledge: Ready — ${result.latest_review.approved_count} approved item${result.latest_review.approved_count === 1 ? "" : "s"} selected for this build.`, "ready");
      if (result.package_id === capturedWebsitePackageId) {
        $("#website-knowledge-status").textContent = `Website knowledge ready — ${result.latest_review.approved_count} owner-approved item${result.latest_review.approved_count === 1 ? "" : "s"} selected for this build.`;
        $("#review-website-knowledge").hidden = true;
        $("#discard-website-knowledge").hidden = true;
        selectedBeforeWebsiteCaptureId = null;
      }
    } else {
      error.textContent = "Review recorded, but no entries were approved. Revise the review before commissioning with this package.";
    }
    await loadKnowledgePackages();
    renderModuleOptions();
    updateCommissionButton();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
  } finally {
    button.disabled = false;
    button.textContent = "FINALIZE OWNER REVIEW →";
  }
});

$("#knowledge-files").addEventListener("change", () => {
  const files = [...$("#knowledge-files").files];
  $("#knowledge-file-summary").textContent = files.length
    ? `${files.length} SELECTED · ${files.map((file) => file.name).join(" · ")}`
    : "TXT · MD · JSON · CSV · YAML";
});

$("#ingest-knowledge").addEventListener("click", async () => {
  const button = $("#ingest-knowledge");
  const error = $("#knowledge-error");
  const label = $("#knowledge-label").value.trim();
  const files = [...$("#knowledge-files").files];
  error.textContent = "";
  if (label.length < 2 || !files.length) {
    error.textContent = "Add a package label and choose at least one supported text file.";
    return;
  }
  if (files.length > 8 || files.some((file) => file.size > 262144) || files.reduce((sum, file) => sum + file.size, 0) > 524288) {
    error.textContent = "Use no more than 8 files, 256 KB each, and 512 KB total.";
    return;
  }
  button.disabled = true;
  button.textContent = "INSPECTING + HASHING…";
  try {
    const payload = {label, files: await Promise.all(files.map(async (file) => ({name: file.name, content: await file.text()})))};
    const response = await fetch("/api/knowledge-packages", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Knowledge Loading Dock stopped safely");
    $("#knowledge-label").value = "";
    $("#knowledge-files").value = "";
    $("#knowledge-file-summary").textContent = "TXT · MD · JSON · CSV · YAML";
    error.textContent = "Package sealed locally. Review the label and file count, then approve the exact package below.";
    await loadKnowledgePackages();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
  } finally {
    button.disabled = false;
    button.textContent = "SEAL LOCAL PACKAGE →";
  }
});

$("#close-commissioning").addEventListener("click", () => {
  $("#commissioning-form").hidden = true;
});

$("#commissioning-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentChassis) return;
  const button = $("#run-commissioning");
  const error = $("#commissioning-error");
  error.textContent = "";
  const payload = {
    purpose: $("#owner-purpose").value.trim(),
    x_agent_name: $("#commission-agent-name").value.trim(),
    client_name: $("#commission-client-name").value.trim(),
    personality: $("#commission-personality").value.trim(),
    target_users: $("#commission-target-users").value.trim(),
    client_context: $("#commission-client-context").value.trim(),
    additional_requirements: $("#commission-requirements").value.trim(),
    additional_boundaries: $("#commission-boundaries").value.trim(),
    presence_mode: commissioningPresenceMode,
    knowledge_package_id: selectedKnowledgePackageId,
    optional_module_ids: [...selectedOptionalModules],
    owner_active_input_ms: commissioningStartedAt ? Math.max(0, Date.now() - commissioningStartedAt) : 0,
  };
  if (capturedWebsitePackageId && selectedKnowledgePackageId !== capturedWebsitePackageId) {
    error.textContent = "Finish reviewing the captured website—or choose Use previous knowledge instead—before building. This prevents an older sample pack from being packaged accidentally.";
    $(".website-knowledge").scrollIntoView({behavior: "smooth", block: "center"});
    updateCommissionButton();
    return;
  }
  if (!$("#owner-purpose").reportValidity()) {
    button.disabled = false;
    updateCommissionButton();
    setOwnerJourney("define");
    $("#owner-purpose").scrollIntoView({behavior: "smooth", block: "center"});
    $("#owner-purpose").focus({preventScroll: true});
    return;
  }
  button.disabled = true;
  button.querySelector("span").textContent = "COMMISSIONING LOCAL X-AGENT";
  setRunning();
  try {
    const response = await fetch(`/api/chassis/${encodeURIComponent(currentChassis.chassis_id)}/commission`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const record = await response.json();
    if (!response.ok) throw new Error(record.error || "Commissioning stopped safely");
    await replayVerifiedStages(record.specialists);
    $("#floor-summary").textContent = `${ownerFacingName(record.agent)} is ready`;
    renderResult(record, {scroll: false});
    await completeMission(record);
    await loadRecent();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
    $("#floor-summary").textContent = "Commissioning stopped safely";
  } finally {
    button.disabled = false;
    updateCommissionButton();
  }
});

$("#runtime-test-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentRecord || !currentRuntimePlan) return;
  const input = $("#runtime-test-message");
  const button = $("#runtime-test-submit");
  const message = input.value.trim();
  if (message.length < 2) return;
  appendRuntimeMessage("YOU · LOCAL", message, "user");
  input.value = "";
  const correctionMatch = message.match(/^(?:correction|update|actually)\s*:?\s*(.+)$/i);
  if (correctionMatch) {
    const correction = correctionMatch[1].trim();
    if (correction) {
      applyPreviewTurn(message, previewStateModel.INTENTS.CORRECTION);
      previewChecks.correction = true;
    }
    appendRuntimeMessage(`${currentRuntimePlan.identity.agent_name.toUpperCase()} · CAPTURED CORRECTION`, "I updated the visible handoff for this session. A fresh session will not remember this correction.", "agent", "CORRECTION · SESSION_CORRECTION_RECORDED");
    renderPreviewHandoff();
    syncPreviewChecks();
    input.focus();
    return;
  }
  if (/\b(?:summarize|summary)\b.*\b(?:team|handoff|service)\b/i.test(message)) {
    applyPreviewTurn(message, previewStateModel.INTENTS.HANDOFF_REQUEST);
    previewChecks.handoff = Boolean(previewSession.request || previewSession.service || previewSession.unknowns.length || previewSession.corrections.length);
    appendRuntimeMessage(`${currentRuntimePlan.identity.agent_name.toUpperCase()} · PREPARED HANDOFF`, handoffSummaryText(), "agent", "HANDOFF_REQUEST · LOCAL_STRUCTURED_HANDOFF");
    renderPreviewHandoff();
    syncPreviewChecks();
    input.focus();
    return;
  }
  input.disabled = true;
  button.disabled = true;
  button.textContent = "CHECKING SEALED KB…";
  try {
    const response = await fetch(`/api/missions/${encodeURIComponent(currentRecord.mission_id)}/runtime-foundry/simulate`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Local boundary test stopped safely");
    const intent = previewStateModel.classify(message, result);
    applyPreviewTurn(message, intent, result);
    const unknownEscalated = result.outcome === "UNKNOWN_ESCALATED";
    const serviceRequest = intent === previewStateModel.INTENTS.SERVICE_REQUEST;
    const label = serviceRequest
      ? (previewSession.primary_review_required ? "REQUEST CAPTURED · COVERAGE UNCONFIRMED" : "REQUEST CAPTURED")
      : unknownEscalated ? "SAFETY CHECK PASSED" : "ANSWERED FROM APPROVED KNOWLEDGE";
    const technical = [intent, result.outcome, ...(result.supporting_entry_ids || []), result.match_reason, result.matcher_version].filter(Boolean).join(" · ");
    const customerResponse = serviceRequest
      ? previewStateModel.serviceRequestResponse(previewSession, currentRecord.agent.client_name)
      : result.response;
    const visibleResponse = serviceRequest && previewSession.primary_review_required
      ? `This was a service request, not a knowledge question. ${currentRuntimePlan.identity.agent_name} captured the operational details, but the sealed knowledge package does not confirm that ${currentRecord.agent.client_name} provides this service.\n\nCustomer-facing response: ${customerResponse}`
      : unknownEscalated
        ? `No approved evidence matched that question. ${currentRuntimePlan.identity.agent_name} routed it for human review instead of guessing.\n\nCustomer-facing response: ${customerResponse}`
        : customerResponse;
    appendRuntimeMessage(`${currentRuntimePlan.identity.agent_name.toUpperCase()} · ${label}`, visibleResponse, "agent", technical);
    if (unknownEscalated) {
      previewChecks.unknown = true;
    } else {
      previewChecks.known = true;
      if (result.match_reason === "APPROVED_PRICING_POLICY") previewChecks.pricing = true;
    }
    renderPreviewHandoff();
    syncPreviewChecks();
  } catch (error) {
    appendRuntimeMessage("FACTORY · SAFE STOP", error instanceof Error ? error.message : String(error), "system");
  } finally {
    input.disabled = false;
    button.disabled = false;
    button.textContent = "CHECK APPROVED KB →";
    input.focus();
  }
});

$("#fresh-preview-session").addEventListener("click", () => {
  const hadSessionState = Boolean(previewSession.turns.length);
  resetPreviewSession(`Fresh session started with ${currentRuntimePlan?.identity?.agent_name || "this agent"}. Previous corrections and handoff notes were cleared.`);
  if (hadSessionState) previewChecks.fresh = true;
  syncPreviewChecks();
  $("#runtime-test-message").focus();
});

$("#copy-preview-handoff").addEventListener("click", async () => {
  if (!currentRecord) return;
  const handoff = {
    agent_name: currentRecord.agent.agent_name,
    client_name: currentRecord.agent.client_name,
    request_summary: previewSession.request || "Not provided",
    service_category: previewSession.service || "Not provided",
    service_city: previewSession.city || "Not provided",
    urgency: previewSession.urgency || "Not provided",
    secondary_questions: previewSession.unknowns,
    review_flags: previewStateModel.reviewFlags(previewSession),
    session_corrections: previewSession.corrections,
    recommended_queue: previewStateModel.recommendedQueue(previewSession),
    routing_note: previewStateModel.routingNote(previewSession),
  };
  await navigator.clipboard.writeText(JSON.stringify(handoff, null, 2));
  $("#copy-preview-handoff").textContent = "HANDOFF COPIED";
  window.setTimeout(() => { $("#copy-preview-handoff").textContent = "COPY HANDOFF"; }, 1000);
});

$("#copy-nova-sync").addEventListener("click", async () => {
  refreshNovaSync();
  await navigator.clipboard.writeText($("#nova-sync-message").value);
  $("#nova-sync-status").textContent = "Copied · still not sent";
});

setPresence("EXISTING_ANAM");
refreshNovaSync();
connectStatus();
loadRecent();
loadChassisDepot().catch((error) => {
  $("#chassis-list").textContent = error instanceof Error ? error.message : String(error);
});
