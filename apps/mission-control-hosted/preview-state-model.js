(function attachPreviewStateModel(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PreviewStateModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createPreviewStateModel() {
  "use strict";

  const INTENTS = Object.freeze({
    INFORMATIONAL_QUERY: "INFORMATIONAL_QUERY",
    SERVICE_REQUEST: "SERVICE_REQUEST",
    QUALIFICATION_DETAIL: "QUALIFICATION_DETAIL",
    CORRECTION: "CORRECTION",
    UNKNOWN_REVIEW: "UNKNOWN_REVIEW",
    HANDOFF_REQUEST: "HANDOFF_REQUEST",
  });

  const CITY = /\b(Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\b/i;
  const URGENT = /\b(emergency|urgent|asap|immediately|right away|tonight)\b/i;
  const ROUTINE = /\b(not urgent|routine|whenever|this week)\b/i;
  const FIRST_PERSON = /\b(?:I|I'm|I am|my|mine|we|our)\b/i;
  const PROBLEM = /\b(?:isn't|not|broken|leak(?:ing)?|stopped|won't|need|needs|issue|problem|cooling|heating|repair|replace)\b/i;
  const SERVICES = [
    [/\b(?:A\/?C|air conditioning|HVAC)\b/i, "Air conditioning / HVAC"],
    [/\bwater[ -]?heater\b/i, "Water heater"],
    [/\bplumb(?:ing|er)?\b/i, "Plumbing"],
    [/\belectri(?:cal|cian)\b/i, "Electrical"],
    [/\bheating|\bheater\b/i, "Heating"],
  ];

  function createState() {
    return {request: "", service: "", city: "", urgency: "", primary_review_required: false, unknowns: [], corrections: [], turns: []};
  }

  function detectedFacts(message) {
    const city = message.match(CITY);
    const service = SERVICES.find(([pattern]) => pattern.test(message));
    return {
      city: city ? city[1][0].toUpperCase() + city[1].slice(1).toLowerCase() : "",
      urgency: URGENT.test(message) ? "Urgent" : ROUTINE.test(message) ? "Routine" : "",
      service: service ? service[1] : "",
    };
  }

  function requestSummary(message) {
    const sentences = message.match(/[^.!?]+[.!?]?/g) || [message];
    const issue = sentences.find((sentence) => {
      const facts = detectedFacts(sentence);
      return facts.service && PROBLEM.test(sentence);
    }) || message;
    const summary = issue
      .replace(/\s+(?:i(?:'m| am)\s+)?in\s+(?:Phoenix|Mesa|Gilbert|Scottsdale|Tempe|Chandler|Glendale|Peoria|Jackson|Brandon|Pearl|Ridgeland|Flowood|Madison|Clinton)\b/ig, "")
      .replace(/(?:,?\s+(?:and\s+)?)(?:it(?:'s| is)\s+)?(?:urgent|an? emergency|asap|routine)\b.*$/i, "")
      .trim();
    if (/^my\s+(?:a\/?c|air conditioning)\s+is(?:n't| not)\s+cooling[.!?]?$/i.test(summary)) {
      return "Customer reports that their AC is not cooling.";
    }
    return summary;
  }

  function recommendedQueue(state) {
    if (state.urgency === "Urgent" && state.primary_review_required) return "URGENT_HUMAN_REVIEW";
    if (state.urgency === "Urgent" && state.service === "Air conditioning / HVAC") return "URGENT_HVAC";
    return "HUMAN_REVIEW";
  }

  function reviewFlags(state) {
    return [
      state.primary_review_required && "PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE",
      state.unknowns.length && "OUT_OF_KNOWLEDGE_SERVICE_QUESTION",
    ].filter(Boolean);
  }

  function routingNote(state) {
    if (state.primary_review_required && state.urgency === "Urgent") {
      return "Prioritize the urgent service request and confirm coverage before making a promise.";
    }
    if (state.primary_review_required) return "Confirm the requested service is covered before making a promise.";
    if (recommendedQueue(state) === "URGENT_HVAC" && state.unknowns.length) {
      return "Prioritize urgent AC service request. Pool-pump question requires separate confirmation.";
    }
    return state.unknowns.length ? "Primary request may proceed; secondary question requires separate confirmation." : "";
  }

  function classify(message, result = null) {
    if (/^(?:correction|update|actually)\s*:?/i.test(message)) return INTENTS.CORRECTION;
    if (/\b(?:summarize|summary)\b.*\b(?:team|handoff|service)\b/i.test(message)) return INTENTS.HANDOFF_REQUEST;
    if (["APPROVED_PRICING_POLICY", "APPROVED_HOURS_POLICY", "APPROVED_AVAILABILITY_POLICY"].includes(result?.match_reason)) return INTENTS.INFORMATIONAL_QUERY;
    const facts = detectedFacts(message);
    const groundedService = result?.outcome === "APPROVED_KNOWLEDGE_MATCH" && result?.matched_title;
    if ((facts.service || groundedService) && FIRST_PERSON.test(message) && PROBLEM.test(message)) return INTENTS.SERVICE_REQUEST;
    if (facts.city || facts.urgency) return INTENTS.QUALIFICATION_DETAIL;
    if (result?.outcome === "UNKNOWN_ESCALATED") return INTENTS.UNKNOWN_REVIEW;
    return INTENTS.INFORMATIONAL_QUERY;
  }

  function apply(state, message, intent, result = null) {
    const next = {
      ...state,
      unknowns: [...state.unknowns],
      corrections: [...state.corrections],
      turns: [...state.turns, {message, intent}],
    };
    if (intent === INTENTS.UNKNOWN_REVIEW) {
      if (!next.unknowns.includes(message)) next.unknowns.push(message);
      return next;
    }
    if (![INTENTS.SERVICE_REQUEST, INTENTS.QUALIFICATION_DETAIL, INTENTS.CORRECTION].includes(intent)) return next;
    const content = intent === INTENTS.CORRECTION ? message.replace(/^(?:correction|update|actually)\s*:?\s*/i, "").trim() : message;
    if (intent === INTENTS.SERVICE_REQUEST) next.request = requestSummary(message);
    const facts = detectedFacts(content);
    if (intent === INTENTS.SERVICE_REQUEST) {
      next.primary_review_required = result?.outcome === "UNKNOWN_ESCALATED";
      if (!facts.service && result?.matched_title) next.service = result.matched_title.replace(/[?.]+$/, "");
    }
    if (intent === INTENTS.CORRECTION) {
      const corrections = [
        facts.city && {field: "service_city", previous_value: state.city || "Not provided", corrected_value: facts.city},
        facts.service && {field: "service_category", previous_value: state.service || "Not provided", corrected_value: facts.service},
        facts.urgency && {field: "urgency", previous_value: state.urgency || "Not provided", corrected_value: facts.urgency},
      ].filter(Boolean);
      corrections.forEach((correction) => {
        if (!next.corrections.some((existing) => existing.field === correction.field && existing.corrected_value === correction.corrected_value)) next.corrections.push(correction);
      });
    }
    if (intent === INTENTS.CORRECTION && facts.service && PROBLEM.test(content)) next.request = requestSummary(content);
    if (facts.service) next.service = facts.service;
    if (facts.city) next.city = facts.city;
    if (facts.urgency) next.urgency = facts.urgency;
    return next;
  }

  function isQualified(state) {
    return Boolean(state.request && state.service && state.city && state.urgency);
  }

  function serviceRequestResponse(state, clientName = "the company") {
    const request = state.request || "I captured your service request.";
    const details = [
      state.city && `Location: ${state.city}.`,
      state.urgency && `Urgency: ${state.urgency}.`,
    ].filter(Boolean).join(" ");
    const coverage = state.primary_review_required
      ? `The approved ${clientName} information does not confirm this service, so I marked it for prompt team review instead of promising coverage.`
      : "I added these details to the visible handoff for the service team.";
    return `I captured your request: ${request}${details ? ` ${details}` : ""} ${coverage}`;
  }

  return {INTENTS, createState, detectedFacts, requestSummary, recommendedQueue, reviewFlags, routingNote, classify, apply, isQualified, serviceRequestResponse};
});
