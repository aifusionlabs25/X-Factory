"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

const origin = process.env.X_FACTORY_ORIGIN || "http://127.0.0.1:8877";
const repoId = process.env.X_FACTORY_REPO_ID || "ava-home-services-concierge-ae28eb41";

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"});
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}, deviceScaleFactor: 1});
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => pageErrors.push(String(error)));
  await page.goto(`${origin}/repo-preview/${repoId}/`, {waitUntil: "networkidle"});

  assert.match(await page.locator("#opening").innerText(), /No language model is active/i);
  assert.ok(await page.locator("#suggested-questions button").count() >= 3);

  async function ask(question) {
    await page.locator("#message").fill(question);
    await page.locator("#message-form button").click();
    return page.locator("#messages .message.agent p").last().innerText();
  }

  assert.match(await ask("What home repair services do you offer?"), /home repairs|homeowners|maintenance/i);
  assert.match(await ask("Can you install a ceiling fan?"), /Ceiling fan installation/i);
  assert.match(await ask("Can you repair my kitchen cabinets?"), /cabinet/i);
  assert.match(await ask("Do you work in Jackson?"), /Jackson|Central Mississippi/i);
  assert.match(await ask("Do you install swimming pool pumps?"), /approved answer|team for review/i);
  assert.match(await ask("My AC isn't cooling. I'm in Mesa and it's urgent."), /approved answer|team for review/i);

  assert.equal(await page.locator("#note-summary").innerText(), "Customer reports that their AC is not cooling.");
  assert.equal(await page.locator("#note-service").innerText(), "Air conditioning / HVAC");
  assert.equal(await page.locator("#note-location").innerText(), "Mesa");
  assert.equal(await page.locator("#note-urgency").innerText(), "Urgent");
  assert.equal(await page.locator("#note-routing").innerText(), "URGENT_HUMAN_REVIEW");
  assert.match(await page.locator("#known-unknowns").innerText(), /pool pumps/i);
  assert.match(await page.locator("#note-flags").innerText(), /Requested service needs human confirmation/i);

  await page.locator("#fresh-session").click();
  assert.equal(await page.locator("#note-summary").innerText(), "Waiting for a service request");
  assert.equal(await page.locator("#note-location").innerText(), "Not provided");
  assert.equal(await page.locator("#known-unknowns").innerText(), "None yet");

  const screenshot = path.resolve(__dirname, "../verification/ava-summit-grounded-app-v0.2.png");
  await page.screenshot({path: screenshot, fullPage: true});
  const control = await browser.newPage();
  await control.goto(origin, {waitUntil: "networkidle"});
  assert.equal(await control.locator("#runtime-harness").innerText(), "Provider-free matcher");
  assert.equal(await control.locator("#runtime-model").innerText(), "NOT ACTIVE");
  assert.equal(await control.locator("#runtime-suggestions").count(), 1);
  await browser.close();
  assert.deepEqual(consoleErrors, []);
  assert.deepEqual(pageErrors, []);
  console.log(JSON.stringify({status: "PASS", repoId, screenshot, checks: ["grounded natural language", "safe unknown", "unsupported primary handoff", "fresh session", "honest Mission Control preview labels"]}, null, 2));
})().catch(error => { console.error(error); process.exit(1); });
