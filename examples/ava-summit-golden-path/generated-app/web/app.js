let agent;
const $ = (selector) => document.querySelector(selector);
function createHandoff() { return {request_summary: "", service_category: "", service_city: "", urgency: "", primary_review_required: false, known_unknowns: [], session_corrections: [], turn_intents: []}; }
let handoff = createHandoff();

function detectedFacts(message) {
  const city = message.match(/\b(Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\b/i);
  const services = [[/\b(?:A\/?C|air conditioning|HVAC)\b/i, "Air conditioning / HVAC"], [/\bwater[ -]?heater\b/i, "Water heater"], [/\bplumb(?:ing|er)?\b/i, "Plumbing"], [/\belectri(?:cal|cian)\b/i, "Electrical"], [/\bheating|\bheater\b/i, "Heating"]];
  const service = services.find(([pattern]) => pattern.test(message));
  return {city: city ? city[1][0].toUpperCase() + city[1].slice(1).toLowerCase() : "", urgency: /\b(emergency|urgent|asap|immediately|right away|tonight)\b/i.test(message) ? "Urgent" : /\b(not urgent|routine|whenever|this week)\b/i.test(message) ? "Routine" : "", service: service ? service[1] : ""};
}

function requestSummary(message) {
  const sentences = message.match(/[^.!?]+[.!?]?/g) || [message];
  const issue = sentences.find((sentence) => {
    const facts = detectedFacts(sentence);
    return facts.service && /\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\b/i.test(sentence);
  }) || message;
  const summary = issue
    .replace(/\s+(?:i(?:'m| am)\s+)?in\s+(?:Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\b/ig, "")
    .replace(/(?:,?\s+(?:and\s+)?)(?:it(?:'s| is)\s+)?(?:urgent|an? emergency|asap|routine)\b.*$/i, "")
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
  if (/\b(?:summarize|summary)\b.*\b(?:team|handoff|service)\b/i.test(message)) return "HANDOFF_REQUEST";
  const query = XAgentGroundedMatcher.normalized(message);
  if (["pricing", "hours", "availability"].some((marker) => query.includes(marker))) return "INFORMATIONAL_QUERY";
  const facts = detectedFacts(message);
  const groundedService = matchResult?.entry?.title;
  if ((facts.service || groundedService) && /\b(?:I|I'm|I am|my|mine|we|our)\b/i.test(message) && /\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\b/i.test(message)) return "SERVICE_REQUEST";
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
    if (intent === "CORRECTION" && facts.service && /\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\b/i.test(content)) handoff.request_summary = requestSummary(content);
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
    button.textContent = item.question;
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
