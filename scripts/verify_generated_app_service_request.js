const { chromium } = require('playwright');
const path = require('path');

const origin = process.env.X_AGENT_APP_ORIGIN || 'http://127.0.0.1:8787';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/generated-app-service-request.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));
  await page.goto(origin, {waitUntil: 'networkidle'});
  await page.locator('#message').fill("My AC isn't cooling. I'm in Mesa and it's urgent.");
  await page.locator('#message-form button').click();
  await page.waitForFunction(() => document.querySelector('#messages')?.textContent.includes('captured your request'));

  const messages = await page.locator('#messages').innerText();
  const handoff = {
    request: await page.locator('#note-summary').innerText(),
    service: await page.locator('#note-service').innerText(),
    location: await page.locator('#note-location').innerText(),
    urgency: await page.locator('#note-urgency').innerText(),
    queue: await page.locator('#note-routing').innerText(),
    flags: await page.locator('#note-flags').innerText(),
  };
  await page.screenshot({path: screenshot, fullPage: true});
  await browser.close();

  const passed = messages.includes('I captured your request')
    && messages.includes('Location: Mesa')
    && messages.includes('Urgency: Urgent')
    && messages.includes('does not confirm this service')
    && !messages.includes('I don’t have an approved answer for that yet')
    && handoff.request === 'Customer reports that their AC is not cooling.'
    && handoff.service === 'Air conditioning / HVAC'
    && handoff.location === 'Mesa'
    && handoff.urgency === 'Urgent'
    && handoff.queue === 'URGENT_HUMAN_REVIEW'
    && handoff.flags === 'Requested service needs human confirmation'
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({status: passed ? 'PASS' : 'FAIL', messages, handoff, consoleErrors, pageErrors, screenshot}, null, 2));
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
