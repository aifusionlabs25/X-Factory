const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const consoleErrors = [];
  const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  await page.goto('http://127.0.0.1:8877/', { waitUntil: 'networkidle' });
  if ((await page.locator('[data-stage="06"] h2').innerText()) !== 'OMNARA') throw new Error('OMNARA station missing');
  if (!(await page.locator('[data-stage="06"]').innerText()).includes('KNOWLEDGE ENGINEERING LEAD')) throw new Error('OMNARA role missing');
  await page.goto('http://127.0.0.1:8877/repo-preview/ava-home-services-concierge-a1c82707/', { waitUntil: 'networkidle' });
  if (!(await page.locator('#agent-name').innerText()).includes('Ava')) throw new Error('Ava identity missing');
  const checks = new Map([
    ['What services do you offer?', ['Central Mississippi', 'fixture and appliance installation']],
    ['What interior repairs do you handle?', ['Summit Home Services handles', 'TV mounting']],
    ['Where do you provide service?', ['greater Jackson area']],
    ['Do you install swimming pool pumps?', ['don’t have an approved answer']],
  ]);
  for (const [question, fragments] of checks) {
    await page.locator('#message').fill(question);
    await page.locator('#message-form button').click();
    const response = await page.locator('#messages .message.agent p').last().innerText();
    for (const fragment of fragments) {
      if (!response.toLowerCase().includes(fragment.toLowerCase())) throw new Error(`${question}: missing ${fragment}: ${response}`);
    }
  }
  const screenshot = path.resolve('verification/omnara-ava-browser-pass.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  await browser.close();
  if (consoleErrors.length) throw new Error(`Console errors: ${consoleErrors.join(' | ')}`);
  console.log(JSON.stringify({ status: 'PASS', mission_control_station: 'OMNARA', repo_id: 'ava-home-services-concierge-a1c82707', questions: checks.size, console_errors: 0, screenshot }, null, 2));
})().catch(error => { console.error(error); process.exit(1); });
