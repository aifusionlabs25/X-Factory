const { chromium } = require('playwright');
const path = require('path');

const factoryOrigin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8877';
const repoId = process.env.X_AGENT_REPO_ID;

if (!repoId) throw new Error('X_AGENT_REPO_ID is required');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1536, height: 1100 } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.goto(`${factoryOrigin}/`, { waitUntil: 'networkidle' });
  await page.locator('#global-factory-details').click();
  await page.locator('#recent-list article').first().getByRole('button', { name: 'OPEN' }).click();
  await page.locator('#runtime-test-message').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('#runtime-test-message')?.disabled);
  const factoryGuide = await page.locator('.runtime-test-guide').innerText();
  const factoryApproved = page.locator('#runtime-suggestions button').first();
  const factoryApprovedLabel = await factoryApproved.innerText();
  await factoryApproved.click();
  const factoryQuestion = await page.locator('#runtime-test-message').inputValue();
  await page.locator('#runtime-test-submit').click();
  await page.waitForFunction(() => document.querySelectorAll('#runtime-transcript .runtime-message.agent').length > 0);
  const factoryTranscript = await page.locator('#runtime-transcript').innerText();
  await page.locator('#runtime-foundry').screenshot({
    path: path.resolve(__dirname, '../verification/mission-control/owner-testing-guidance-factory.png'),
  });

  await page.goto(`${factoryOrigin}/repo-preview/${repoId}/`, { waitUntil: 'networkidle' });
  const repoGuide = await page.locator('.test-guide').innerText();
  const repoApproved = page.locator('#suggested-questions button').first();
  const repoApprovedLabel = await repoApproved.innerText();
  await repoApproved.click();
  const repoQuestion = await page.locator('#message').inputValue();
  await page.locator('#message-form button').click();
  await page.waitForFunction(() => document.querySelectorAll('#messages .message.agent').length > 0);
  const repoApprovedResponse = await page.locator('#messages .message.agent').last().innerText();

  await page.locator('#message').fill('Do you repair water heaters?');
  await page.locator('#message-form button').click();
  await page.waitForFunction(() => document.querySelectorAll('#messages .message.agent').length > 1);
  const repoUnknownResponse = await page.locator('#messages .message.agent').last().innerText();
  await page.screenshot({
    path: path.resolve(__dirname, '../verification/mission-control/owner-testing-guidance-generated-app.png'),
    fullPage: true,
  });
  await browser.close();

  const passed = factoryGuide.includes('KNOWN-ANSWER TEST')
    && factoryGuide.includes('SAFETY TEST')
    && factoryApprovedLabel.startsWith('APPROVED · ')
    && factoryQuestion.length > 3
    && !factoryQuestion.startsWith('APPROVED · ')
    && !factoryTranscript.includes('No approved evidence matched that question')
    && repoGuide.includes('KNOWN-ANSWER TEST')
    && repoGuide.includes('SAFETY TEST')
    && repoApprovedLabel.startsWith('APPROVED · ')
    && repoQuestion.length > 3
    && !repoQuestion.startsWith('APPROVED · ')
    && !repoApprovedResponse.includes('I don’t have an approved answer')
    && repoUnknownResponse.includes('I don’t have an approved answer')
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({
    status: passed ? 'PASS' : 'FAIL',
    factoryApprovedLabel,
    factoryQuestion,
    repoApprovedLabel,
    repoQuestion,
    repoApprovedResponse,
    repoUnknownResponse,
    consoleErrors,
    pageErrors,
  }, null, 2));
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
