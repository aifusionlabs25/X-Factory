const { chromium } = require('playwright');
const path = require('path');

const origin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8892';
const expectedFactoryVersion = process.env.X_FACTORY_EXPECTED_VERSION || '1.9';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/website-knowledge-owner-flow.png');
  const disclosureScreenshot = path.resolve(__dirname, '../verification/mission-control/owner-progressive-disclosure-v1.9.png');
  const receiptScreenshot = path.resolve(__dirname, '../verification/mission-control/pre-build-knowledge-receipt-v1.9.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1536, height: 1100 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.route(`${origin}/api/website-knowledge`, async route => {
    const request = route.request();
    const body = request.postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        package_id: 'kp-summit-website-proof-001',
        label: body.label,
        effective_status: 'INGESTED_PENDING_OWNER_APPROVAL',
        files: [{original_name: 'website-01-home.md', stored_name: 'website-01-home.md', bytes: 420, sha256: 'a'.repeat(64)}],
        total_bytes: 420,
        manifest_sha256: 'b'.repeat(64),
        website_capture: {pages: [{url: body.url, title: 'Summit Home Services'}]},
      }),
    });
  });

  await page.goto(`${origin}/`, { waitUntil: 'networkidle' });
  await page.locator('#owner-purpose').fill('Answer approved home-service questions and prepare a structured request for staff review.');
  await page.locator('#recommend-chassis').click();
  await page.locator('#use-recommendation').waitFor({state: 'visible'});
  await page.locator('#use-recommendation').click();
  await page.locator('#commissioning-form').waitFor({state: 'visible'});
  const sourcesClosedByDefault = !(await page.locator('#knowledge-source-packages').evaluate(node => node.open));
  const extrasClosedByDefault = !(await page.locator('#module-options-bay').evaluate(node => node.open));
  await page.locator('#commission-client-name').fill('Summit Home Services');
  await page.locator('#global-factory-details').click();
  await page.locator('#knowledge-source-packages > summary').click();
  await page.locator('#knowledge-packages .knowledge-package button.select').click();
  await page.waitForFunction(() => document.querySelector('#build-knowledge-state')?.textContent === 'REVIEWED + BOUND');
  const readyReceiptSource = await page.locator('#build-knowledge-source').innerText();
  const readyReceiptReviewed = await page.locator('#build-knowledge-pages').innerText();
  const readyReceiptFacts = Number(await page.locator('#build-knowledge-facts').innerText());
  const readyReceiptExclusions = await page.locator('#build-knowledge-exclusions').innerText();
  const readyReceiptBinding = await page.locator('#build-knowledge-binding').textContent();
  await page.locator('#build-knowledge-receipt').screenshot({path: receiptScreenshot});
  await page.locator('#knowledge-source-packages > summary').click();
  await page.locator('#global-factory-details').click();
  await page.locator('#website-knowledge-url').fill('https://example.com');
  await page.locator('#capture-website-knowledge').click();
  await page.locator('#review-website-knowledge').waitFor({state: 'visible'});

  const status = await page.locator('#website-knowledge-status').innerText();
  const boundary = await page.locator('.website-boundary').innerText();
  const reviewText = await page.locator('#review-website-knowledge').innerText();
  const discardVisible = await page.locator('#discard-website-knowledge').isVisible();
  const buildTextWhilePending = await page.locator('#run-commissioning span').innerText();
  const buildDisabledWhilePending = await page.locator('#run-commissioning').isDisabled();
  const quickKnowledgeStatus = await page.locator('#quick-knowledge-status').innerText();
  const pendingReceiptState = await page.locator('#build-knowledge-state').innerText();
  const pendingReceiptSource = await page.locator('#build-knowledge-source').innerText();
  const pendingReceiptReviewed = await page.locator('#build-knowledge-pages').innerText();
  const pendingReceiptFacts = await page.locator('#build-knowledge-facts').innerText();
  const pendingReceiptExclusions = await page.locator('#build-knowledge-exclusions').innerText();
  const selectAllSafeText = await page.locator('#review-safe-defaults').innerText();
  const finalizeInTopToolbar = await page.locator('#finalize-knowledge-review').evaluate(button => button.parentElement?.classList.contains('review-toolbar'));
  const websiteBox = page.locator('.website-knowledge');
  await websiteBox.screenshot({path: screenshot});
  await page.locator('#global-factory-details').click();
  await page.locator('#knowledge-source-packages > summary').click();
  const compactPackageCount = await page.locator('#knowledge-packages .knowledge-package').count();
  const packageHistoryText = await page.locator('#toggle-package-history').innerText();
  await page.locator('#toggle-package-history').click();
  const expandedPackageCount = await page.locator('#knowledge-packages .knowledge-package').count();
  await page.locator('#toggle-package-history').click();
  const collapsedPackageCount = await page.locator('#knowledge-packages .knowledge-package').count();
  await page.locator('#knowledge-source-packages').screenshot({path: disclosureScreenshot});
  await page.locator('#discard-website-knowledge').click();
  await page.waitForFunction(() => document.querySelector('#run-commissioning span')?.textContent !== 'REVIEW WEBSITE BEFORE BUILD');
  const captureResultHiddenAfterDiscard = await page.locator('#website-capture-result').isHidden();
  const buildTextAfterDiscard = await page.locator('#run-commissioning span').innerText();
  const restoredReceiptState = await page.locator('#build-knowledge-state').innerText();
  const statusResponse = await page.request.get(`${origin}/api/status`);
  const factoryStatus = await statusResponse.json();
  await browser.close();

  const passed = status.includes('Captured 1 public page')
    && status.includes('Build is paused')
    && status.includes('Review these website facts next')
    && reviewText === 'REVIEW CAPTURED KNOWLEDGE →'
    && discardVisible
    && buildTextWhilePending === 'REVIEW WEBSITE BEFORE BUILD'
    && buildDisabledWhilePending
    && quickKnowledgeStatus.includes('Website review required')
    && readyReceiptSource.length > 0
    && readyReceiptReviewed.includes('reviewed')
    && readyReceiptFacts > 0
    && readyReceiptExclusions.includes('not included')
    && readyReceiptBinding.includes('package ')
    && readyReceiptBinding.includes('review hash ')
    && pendingReceiptState === 'REVIEW REQUIRED BEFORE BUILD'
    && pendingReceiptSource.includes('awaiting owner review')
    && pendingReceiptReviewed.includes('not finalized')
    && pendingReceiptFacts === '0 bound to this build'
    && pendingReceiptExclusions.includes('previously selected package')
    && selectAllSafeText === 'SELECT ALL SAFE ITEMS'
    && finalizeInTopToolbar
    && sourcesClosedByDefault
    && extrasClosedByDefault
    && compactPackageCount === 1
    && packageHistoryText.startsWith('SHOW PACKAGE HISTORY (')
    && expandedPackageCount > compactPackageCount
    && collapsedPackageCount === 1
    && captureResultHiddenAfterDiscard
    && buildTextAfterDiscard !== 'REVIEW WEBSITE BEFORE BUILD'
    && restoredReceiptState === 'REVIEWED + BOUND'
    && boundary.includes('same website only')
    && factoryStatus.factory_version === expectedFactoryVersion
    && factoryStatus.capabilities.includes('SCOPED_PUBLIC_WEBSITE_CAPTURE')
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({status: passed ? 'PASS' : 'FAIL', ownerStatus: status, boundary, reviewText, discardVisible, buildTextWhilePending, buildDisabledWhilePending, quickKnowledgeStatus, readyReceiptSource, readyReceiptReviewed, readyReceiptFacts, readyReceiptExclusions, readyReceiptBinding, pendingReceiptState, pendingReceiptSource, pendingReceiptReviewed, pendingReceiptFacts, pendingReceiptExclusions, selectAllSafeText, finalizeInTopToolbar, sourcesClosedByDefault, extrasClosedByDefault, compactPackageCount, packageHistoryText, expandedPackageCount, collapsedPackageCount, captureResultHiddenAfterDiscard, buildTextAfterDiscard, restoredReceiptState, factoryVersion: factoryStatus.factory_version, consoleErrors, pageErrors, screenshot, disclosureScreenshot, receiptScreenshot}, null, 2));
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
