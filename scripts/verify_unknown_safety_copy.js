const { chromium } = require('playwright');
const path = require('path');

const origin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8877';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/unknown-safety-copy.png');
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
  const latestOpen = page.locator('#recent-list article').first().getByRole('button', {name: 'OPEN'});
  await latestOpen.click();
  await page.locator('#runtime-test-message').waitFor({state: 'visible'});
  await page.waitForFunction(() => !document.querySelector('#runtime-test-message')?.disabled);
  await page.locator('#runtime-test-message').fill('Do you install swimming pool pumps?');
  await page.locator('#runtime-test-submit').click();
  await page.waitForFunction(() => document.querySelector('#runtime-transcript')?.textContent.includes('SAFETY CHECK PASSED'));
  const transcript = await page.locator('#runtime-transcript').innerText();
  await page.locator('#runtime-foundry').screenshot({path: screenshot});
  await browser.close();

  const passed = transcript.includes('SAFETY CHECK PASSED')
    && transcript.includes('No approved evidence matched that question')
    && transcript.includes('routed it for human review instead of guessing')
    && transcript.includes('Customer-facing response:')
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({status: passed ? 'PASS' : 'FAIL', transcript, consoleErrors, pageErrors, screenshot}, null, 2));
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
