const { chromium } = require('playwright');
const path = require('path');
const origin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8877';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/operational-draft.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.goto(`${origin}/`);
  await page.waitForLoadState('networkidle');
  const statusResponse = await page.request.get(`${origin}/api/status`);
  const status = await statusResponse.json();
  const initialPersonaVisible = await page.locator('#persona-card img').isVisible();
  const defaultPresence = await page.locator('[data-presence].selected').getAttribute('data-presence');

  await page.locator('#agent-or-client').fill('Operational QA Concierge');
  await page.locator('#purpose').fill('Create a contained operational concierge that answers approved questions and prepares a structured local review handoff.');
  await page.locator('.run-button').click();
  await page.locator('#result:not([hidden])').waitFor({ timeout: 15000 });
  await page.waitForFunction(() => document.querySelector('#progress')?.textContent === '100%', null, { timeout: 10000 });

  const resultName = await page.locator('#result-name').innerText();
  const missionId = await page.locator('#result-mission').innerText();
  const stageLabels = await page.locator('#stations article mark').allInnerTexts();
  const doneStages = await page.locator('#stations article.done').count();
  const moduleCount = await page.locator('#module-chips span').count();
  const artifactCount = await page.locator('#artifact-links a').count();
  const artifactLabels = await page.locator('#artifact-links a').allInnerTexts();
  const firstArtifactHref = await page.locator('#artifact-links a').first().getAttribute('href');
  const artifactResponse = await page.request.get(`${origin}${firstArtifactHref}`);
  const artifactBody = await artifactResponse.text();
  await page.locator('#meet-agent').click();
  await page.locator('#presence-preview:not([hidden])').waitFor();
  const staticPreviewFallback = await page.locator('#preview-fallback').innerText();
  const staticLaunchLocked = await page.locator('#launch-live-preview').isDisabled();
  await page.locator('#close-presence-preview').click();
  const recentIncludesMission = await page.locator('#recent-list').innerText().then(text => text.includes(missionId));
  await page.locator('#revise-agent').click();
  await page.waitForFunction(id => document.querySelector('#revision-note')?.textContent.includes(id), missionId);
  const revisionLoaded = (await page.locator('#agent-or-client').inputValue()) === 'Operational QA Concierge';
  const revisionNotice = await page.locator('#revision-note').innerText();

  const rejectedResponse = await page.request.post(`${origin}/api/missions`, {
    data: {
      purpose: 'Create a deliberately invalid test request that includes a secret-like value for rejection.',
      agent_or_client: 'Rejected QA Agent',
      personality: 'Careful and concise',
      must_accomplish: 'Reject unsafe input',
      never_do: 'Reveal credential: sk-this-should-never-pass-123456',
      target_users: 'QA reviewers',
      output_artifact: 'Rejected record',
      presence_mode: 'TEXT_ONLY',
      persona_catalog_id: null,
    },
  });
  const rejectedBody = await rejectedResponse.json();

  const certifiedMissionId = 'draft-operational-qa-concierge-20260821-064103-a3e197';
  const certifiedPreviewResponse = await page.request.get(`${origin}/api/missions/${certifiedMissionId}/presence-preview`);
  const certifiedPreview = await certifiedPreviewResponse.json();
  const certifiedRow = page.locator('#recent-list article').filter({ hasText: certifiedMissionId });
  if (await certifiedRow.count()) {
    await certifiedRow.getByRole('button', { name: 'OPEN' }).click();
    await page.locator('#meet-agent').click();
    await page.waitForFunction(() => document.querySelector('#preview-status')?.textContent === 'Preview packet ready');
  }
  const certifiedUiReady = !(await page.locator('#copy-preview-approval').isDisabled());
  const certifiedLiveLocked = await page.locator('#launch-live-preview').isDisabled();

  await page.screenshot({ path: screenshot, fullPage: true });
  await browser.close();

  const passed = statusResponse.ok() && status.status === 'READY' && status.factory_version === '0.3' && status.provider_calls === 0 && status.capabilities.includes('MISSION_PRESENCE_PREVIEW') && initialPersonaVisible && defaultPresence === 'EXISTING_ANAM' && resultName === 'Operational QA Concierge' && /^draft-operational-qa-concierge-/.test(missionId) && doneStages === 5 && stageLabels.every(label => label === 'PASS') && moduleCount >= 4 && artifactCount === 15 && artifactLabels.some(label => label.includes('X-Link candidate')) && artifactLabels.some(label => label.includes('X-Link agent entry')) && artifactLabels.some(label => label.includes('X-Link scenario pack')) && artifactLabels.some(label => label.includes('Hermes / Luna review')) && artifactResponse.ok() && artifactBody.includes('operational concierge') && staticPreviewFallback.includes('contained operational concierge') && staticLaunchLocked && recentIncludesMission && revisionLoaded && revisionNotice.includes('original is preserved') && rejectedResponse.status() === 400 && /credentials|tokens|passwords|private keys/i.test(rejectedBody.error || '') && certifiedPreviewResponse.ok() && certifiedPreview.status === 'LIVE_ACTIVATION_PREPARED' && certifiedPreview.activation?.canary_id === 'mia-mission-preview-009' && certifiedUiReady && certifiedLiveLocked && !consoleErrors.length && !pageErrors.length;
  const result = {
    status: passed ? 'PASS' : 'FAIL',
    systemStatus: status,
    initialPersonaVisible,
    defaultPresence,
    resultName,
    missionId,
    doneStages,
    stageLabels,
    moduleCount,
    artifactCount,
    artifactLabels,
    artifactResponseStatus: artifactResponse.status(),
    staticPreviewFallback,
    staticLaunchLocked,
    recentIncludesMission,
    revisionLoaded,
    revisionNotice,
    unsafeRequestStatus: rejectedResponse.status(),
    unsafeRequestError: rejectedBody.error,
    certifiedPreviewStatus: certifiedPreview.status,
    certifiedPreviewCanary: certifiedPreview.activation?.canary_id,
    certifiedUiReady,
    certifiedLiveLocked,
    consoleErrors,
    pageErrors,
    screenshot,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!passed) process.exitCode = 1;
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
