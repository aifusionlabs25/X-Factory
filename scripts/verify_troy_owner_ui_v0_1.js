const { chromium } = require('playwright');

(async () => {
  const base = process.env.X_FACTORY_BASE_URL || 'http://127.0.0.1:8877';
  const executablePath = process.env.PLAYWRIGHT_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await chromium.launch({headless: true, executablePath});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errors = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(base, {waitUntil: 'networkidle'});
  const purposeLabel = await page.locator('label[for="owner-purpose"]').textContent();
  const purposeHelp = await page.locator('#owner-purpose-help').textContent();
  const knowledgeTitle = await page.locator('#quick-knowledge-title').textContent();
  const troy = page.locator('#stations article[data-stage="06"]');
  if (!purposeLabel.includes('System Prompt Brief')) throw new Error(`Missing System Prompt Brief label: ${purposeLabel}`);
  if (!purposeHelp.includes('Troy turns this short brief')) throw new Error(`Missing Troy helper text: ${purposeHelp}`);
  if (!knowledgeTitle.includes('What should this agent know?')) throw new Error(`Missing Knowledge Bank owner label: ${knowledgeTitle}`);
  if ((await troy.locator('h2').textContent()).trim() !== 'Troy') throw new Error('Troy is missing from station 06');
  if (!(await troy.locator('p').textContent()).includes('complete System Prompt')) throw new Error('Troy station does not explain its output');
  const status = await page.evaluate(async () => (await fetch('/api/status', {cache: 'no-store'})).json());
  if (!status.capabilities.includes('TROY_PROMPT_FORGE')) throw new Error('Server does not advertise TROY_PROMPT_FORGE');
  if (!status.capabilities.includes('EIGHT_INTERNAL_STATIONS')) throw new Error('Server does not advertise eight stations');
  if (errors.length) throw new Error(`Browser errors: ${errors.join(' | ')}`);
  console.log(JSON.stringify({
    status: 'PASS',
    owner_label: purposeLabel.trim(),
    station: '06 · Troy · Prompt Engineering Lead',
    capabilities: ['TROY_PROMPT_FORGE', 'EIGHT_INTERNAL_STATIONS'],
    browser_errors: 0,
  }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
