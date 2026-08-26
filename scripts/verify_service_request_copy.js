const { chromium } = require('playwright');
const path = require('path');

const origin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8877';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/service-request-capture.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({viewport: {width: 1536, height: 1100}, deviceScaleFactor: 1});
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.goto(`${origin}/`, {waitUntil: 'networkidle'});
  await page.locator('#global-factory-details').click();
  await page.locator('#recent-list article').first().getByRole('button', {name: 'OPEN'}).click();
  await page.locator('#runtime-test-message').waitFor({state: 'visible'});
  await page.waitForFunction(() => !document.querySelector('#runtime-test-message')?.disabled);
  await page.locator('#runtime-test-message').fill("My AC isn't cooling. I'm in Mesa and it's urgent.");
  await page.locator('#runtime-test-submit').click();
  await page.waitForFunction(() => document.querySelector('#runtime-transcript')?.textContent.includes('REQUEST CAPTURED · COVERAGE UNCONFIRMED'));

  const transcript = await page.locator('#runtime-transcript').innerText();
  const handoff = {
    request: await page.locator('#preview-handoff-request').innerText(),
    service: await page.locator('#preview-handoff-service').innerText(),
    location: await page.locator('#preview-handoff-location').innerText(),
    urgency: await page.locator('#preview-handoff-urgency').innerText(),
    queue: await page.locator('#preview-handoff-routing').innerText(),
    flags: await page.locator('#preview-handoff-flags').innerText(),
  };
  await page.locator('#runtime-foundry').screenshot({path: screenshot});
  await browser.close();

  const passed = transcript.includes('This was a service request, not a knowledge question')
    && transcript.includes('captured your request')
    && transcript.includes('Location: Mesa')
    && transcript.includes('Urgency: Urgent')
    && transcript.includes('does not confirm this service')
    && !transcript.includes('SAFETY CHECK PASSED')
    && handoff.request === 'Customer reports that their AC is not cooling.'
    && handoff.service === 'Air conditioning / HVAC'
    && handoff.location === 'Mesa'
    && handoff.urgency === 'Urgent'
    && handoff.queue === 'URGENT_HUMAN_REVIEW'
    && handoff.flags === 'Requested service needs human confirmation'
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({status: passed ? 'PASS' : 'FAIL', transcript, handoff, consoleErrors, pageErrors, screenshot}, null, 2));
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
