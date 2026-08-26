const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/readable-draft.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));
  await page.goto('http://127.0.0.1:8877/');
  await page.waitForLoadState('networkidle');

  const metrics = await page.evaluate(() => {
    const px = selector => Number.parseFloat(getComputedStyle(document.querySelector(selector)).fontSize);
    return {
      styleSheets: document.styleSheets.length,
      body: px('body'),
      formLabel: px('.form-body label'),
      formInput: px('.form-body input'),
      panelTitle: px('.panel-head strong'),
      stationTitle: px('.stations h2'),
      stationDescription: px('.stations p'),
      personaTitle: px('.persona-recommendation strong'),
      presenceTitle: px('.presence-head h2'),
      presenceFallback: px('.presence-script blockquote'),
      presenceConsole: px('.presence-console > p'),
      microcopy: px('.micro'),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    };
  });
  await page.screenshot({ path: screenshot, fullPage: true });
  await browser.close();

  const passed = metrics.styleSheets >= 1 && metrics.body >= 17 && metrics.formLabel >= 12 && metrics.formInput >= 17 && metrics.panelTitle >= 19 && metrics.stationTitle >= 30 && metrics.stationDescription >= 16 && metrics.personaTitle >= 21 && metrics.presenceTitle >= 40 && metrics.presenceFallback >= 25 && metrics.presenceConsole >= 15 && metrics.microcopy >= 11 && !metrics.horizontalOverflow && !consoleErrors.length && !pageErrors.length;
  console.log(JSON.stringify({ status: passed ? 'PASS' : 'FAIL', metrics, consoleErrors, pageErrors, screenshot }, null, 2));
  if (!passed) process.exitCode = 1;
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
