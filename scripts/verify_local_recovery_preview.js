const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const preview = path.resolve(__dirname, '../runs/contained/phase4-governed-draft-001-local-recovery-005/preview/index.html');
  const screenshot = path.resolve(__dirname, '../runs/contained/phase4-governed-draft-001-local-recovery-005/preview-verified.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));
  await page.goto('file:///' + preview.replace(/\\/g, '/'));
  await page.waitForLoadState('networkidle');

  const title = await page.title();
  const agentName = await page.locator('#agent-name').innerText();
  const stationCount = await page.locator('#stations article').count();
  const faqCount = await page.locator('#faq-buttons button').count();
  const presenceCount = await page.locator('[data-presence]').count();
  const defaultPresence = await page.locator('[data-presence].selected').getAttribute('data-presence');
  await page.locator('button[data-tab=concierge]').click();
  const avatarImageVisible = await page.locator('#avatar-reference').isVisible();
  const avatarMode = await page.locator('#avatar-mode').innerText();
  const personaReference = await page.locator('#persona-reference').innerText();
  await page.locator('[data-presence=TEXT_ONLY]').click();
  const avatarHiddenInTextMode = !(await page.locator('#avatar-reference').isVisible());
  await page.locator('[data-presence=EXISTING_ANAM]').click();
  const selectedPresence = await page.locator('[data-presence].selected').getAttribute('data-presence');
  await page.locator('#mission-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#progress')?.textContent === '100%', null, { timeout: 6000 });
  const passedStations = await page.locator('#stations article.done').count();
  const stationLabels = await page.locator('#stations article mark').allInnerTexts();
  await page.locator('button[data-tab=concierge]').click();
  await page.locator('#faq-buttons button').first().click();
  await page.waitForTimeout(350);
  const messages = await page.locator('#messages .message').count();
  await page.screenshot({ path: screenshot, fullPage: true });
  await browser.close();

  const result = {
    status: title && agentName && stationCount === 4 && faqCount === 5 && presenceCount === 4 && defaultPresence === 'EXISTING_ANAM' && selectedPresence === 'EXISTING_ANAM' && avatarImageVisible && avatarHiddenInTextMode && avatarMode.includes('MIA') && avatarMode.includes('FACTORY RECOMMENDED') && personaReference.includes('ANAM stock persona') && passedStations === 4 && stationLabels.join('|') === 'SOURCE|SOURCE|REMEDIATED|BUILT' && messages === 2 && !consoleErrors.length && !pageErrors.length ? 'PASS' : 'FAIL',
    title, agentName, stationCount, faqCount, presenceCount, defaultPresence, selectedPresence, avatarImageVisible, avatarHiddenInTextMode, avatarMode, personaReference, passedStations, stationLabels, messages,
    consoleErrors, pageErrors, screenshot,
  };
  console.log(JSON.stringify(result, null, 2));
  if (result.status !== 'PASS') process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
