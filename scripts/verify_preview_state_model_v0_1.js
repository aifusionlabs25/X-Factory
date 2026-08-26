"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const model = require(path.resolve(__dirname, "../apps/mission-control/preview-state-model.js"));

const sequence = [
  ["Do you repair water heaters?", {outcome: "APPROVED_KNOWLEDGE_MATCH", match_reason: "APPROVED_SERVICE_ENTITY_WATERHEATER"}],
  ["How much will it cost to replace my water heater?", {outcome: "APPROVED_KNOWLEDGE_MATCH", match_reason: "APPROVED_PRICING_POLICY"}],
  ["Do you install swimming pool pumps?", {outcome: "UNKNOWN_ESCALATED", match_reason: "NO_APPROVED_MATCH"}],
  ["My AC isn't cooling. I'm in Mesa and it's urgent.", {outcome: "APPROVED_KNOWLEDGE_MATCH", match_reason: "APPROVED_SERVICE_ENTITY_AIRCONDITIONING"}],
  ["Correction: I'm actually in Gilbert.", null],
  ["Summarize this for the service team.", null],
];

let state = model.createState();
const observed = [];
for (const [message, result] of sequence) {
  const intent = model.classify(message, result);
  state = model.apply(state, message, intent, result);
  observed.push(intent);
  if (observed.length === 1) {
    assert.equal(state.request, "");
    assert.equal(state.service, "");
  }
  if (observed.length === 2) {
    assert.equal(state.request, "");
    assert.equal(state.service, "");
  }
  if (observed.length === 3) {
    assert.equal(state.request, "");
    assert.deepEqual(state.unknowns, ["Do you install swimming pool pumps?"]);
  }
}

assert.deepEqual(observed, [
  "INFORMATIONAL_QUERY",
  "INFORMATIONAL_QUERY",
  "UNKNOWN_REVIEW",
  "SERVICE_REQUEST",
  "CORRECTION",
  "HANDOFF_REQUEST",
]);
assert.equal(state.request, "Customer reports that their AC is not cooling.");
assert.ok(!state.request.includes("Mesa"));
assert.equal(state.service, "Air conditioning / HVAC");
assert.equal(state.city, "Gilbert");
assert.equal(state.urgency, "Urgent");
assert.deepEqual(state.unknowns, ["Do you install swimming pool pumps?"]);
assert.deepEqual(state.corrections, [{field: "service_city", previous_value: "Mesa", corrected_value: "Gilbert"}]);
assert.deepEqual(model.reviewFlags(state), ["OUT_OF_KNOWLEDGE_SERVICE_QUESTION"]);
assert.equal(model.recommendedQueue(state), "URGENT_HVAC");
assert.equal(model.routingNote(state), "Prioritize urgent AC service request. Pool-pump question requires separate confirmation.");
assert.equal(model.isQualified(state), true);

const fresh = model.createState();
assert.equal(fresh.request, "");
assert.equal(fresh.city, "");
assert.deepEqual(fresh.unknowns, []);
assert.deepEqual(fresh.turns, []);

const unsupportedMessage = "My AC isn't cooling. I'm in Mesa and it's urgent.";
const unsupportedResult = {outcome: "UNKNOWN_ESCALATED", match_reason: "NO_APPROVED_MATCH", matched_title: null};
let unsupported = model.createState();
const unsupportedIntent = model.classify(unsupportedMessage, unsupportedResult);
unsupported = model.apply(unsupported, unsupportedMessage, unsupportedIntent, unsupportedResult);
assert.equal(unsupportedIntent, "SERVICE_REQUEST");
assert.equal(unsupported.request, "Customer reports that their AC is not cooling.");
assert.equal(unsupported.service, "Air conditioning / HVAC");
assert.equal(unsupported.city, "Mesa");
assert.equal(unsupported.urgency, "Urgent");
assert.equal(unsupported.primary_review_required, true);
assert.deepEqual(unsupported.unknowns, []);
assert.deepEqual(model.reviewFlags(unsupported), ["PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE"]);
assert.equal(model.recommendedQueue(unsupported), "URGENT_HUMAN_REVIEW");
assert.match(model.routingNote(unsupported), /confirm coverage/i);
const unsupportedResponse = model.serviceRequestResponse(unsupported, "Summit Home Services");
assert.match(unsupportedResponse, /captured your request/i);
assert.match(unsupportedResponse, /Location: Mesa/);
assert.match(unsupportedResponse, /Urgency: Urgent/);
assert.match(unsupportedResponse, /does not confirm this service/i);
assert.doesNotMatch(unsupportedResponse, /approved answer for that yet/i);

console.log(JSON.stringify({status: "PASS", intents: observed, final_handoff: state, fresh_session: fresh, unsupported_primary: unsupported, unsupported_primary_response: unsupportedResponse}, null, 2));
