const { chromium } = require('playwright');
const path = require('path');

const origin = process.env.X_FACTORY_ORIGIN || 'http://127.0.0.1:8891';

(async () => {
  const screenshot = path.resolve(__dirname, '../verification/mission-control/automatic-owner-finish.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1536, height: 1050 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.goto(`${origin}/`, { waitUntil: 'networkidle' });
  const statusResponse = await page.request.get(`${origin}/api/status`);
  const status = await statusResponse.json();

  await page.locator('#global-factory-details').click();
  await page.locator('#toggle-blank-build').click();
  await page.locator('#agent-or-client').waitFor({state: 'visible'});
  await page.locator('#agent-or-client').fill('Employee Policy Guide');
  await page.locator('#purpose').fill('Help employees find approved workplace policy information and prepare a clarification request when the approved material does not answer them.');
  await page.locator('#x-agent-name').fill('Nora');
  await page.locator('#client-name').fill('Apex People Operations');
  await page.locator('#personality').fill('Calm, neutral, private, and concise');
  await page.locator('#must-accomplish').fill('Answer approved questions; preserve the employee question; prepare a structured clarification handoff');
  await page.locator('#never-do').fill('Invent policy; provide legal advice; approve leave or benefits; send information externally');
  await page.locator('#target-users').fill('Employees and People Operations staff');
  await page.locator('#output-artifact').fill('Structured policy clarification handoff');
  await page.locator('[data-presence="TEXT_ONLY"]').click();
  await page.locator('.run-button').click();

  await page.waitForFunction(() => document.querySelector('#runner-status')?.textContent === 'LOCAL X-AGENT BUILT', null, { timeout: 30000 });
  const missionId = await page.locator('#result-mission').innerText();
  const resultName = await page.locator('#result-name').innerText();
  const runnerPasses = await page.locator('#runner-route article.done').count();
  const runnerNames = await page.locator('#runner-route article strong').allInnerTexts();
  const runnerReview = await page.locator('#runner-review').innerText();
  const repoStatus = await page.locator('#repo-status-title').innerText();
  const repoPath = await page.locator('#repo-path').innerText();
  const repoHref = await page.locator('#open-repo-preview').getAttribute('href');

  const completionResponse = await page.request.get(`${origin}/api/missions/${missionId}/completion`);
  const completionBody = await completionResponse.json();
  const repoResponse = await page.request.get(`${origin}/api/missions/${missionId}/repo`);
  const repoBody = await repoResponse.json();
  const previewResponse = await page.request.get(`${origin}${repoHref}`);
  const previewAgentResponse = await page.request.get(`${origin}${repoHref}agent.json`);
  const previewAgent = await previewAgentResponse.json();

  await page.locator('#mission-runner').screenshot({ path: screenshot });
  await browser.close();

  const passed = statusResponse.ok()
    && status.status === 'READY'
    && status.factory_version === '1.9'
    && status.provider_calls === 0
    && status.capabilities.includes('AUTOMATIC_LOCAL_COMPLETION')
    && resultName === 'Nora — Employee Policy Guide'
    && /^draft-nora-/.test(missionId)
    && runnerPasses === 7
    && runnerNames.join('|') === 'Atlas|Aria|Vera|Mason|Vera|Rook|Porter'
    && runnerReview === 'Rook passed it to Porter'
    && repoStatus === 'Complete local app ready'
    && repoPath.includes('nora-employee-policy-guide')
    && completionResponse.ok()
    && completionBody.completion?.status === 'LOCAL_DRAFT_COMPLETE'
    && completionBody.completion?.authority?.provider_calls === 0
    && completionBody.completion?.authority?.network_attempts === 0
    && repoResponse.ok()
    && repoBody.repo?.status === 'LOCAL_REPO_READY'
    && repoBody.repo?.verification?.status === 'PASS'
    && repoBody.repo?.independent_review?.verdict === 'READY_FOR_PORTER_PACKAGING'
    && previewResponse.ok()
    && previewAgentResponse.ok()
    && previewAgent.display_name === 'Nora — Employee Policy Guide'
    && previewAgent.agent_name === 'Nora'
    && previewAgent.client_name === 'Apex People Operations'
    && !consoleErrors.length
    && !pageErrors.length;

  console.log(JSON.stringify({
    status: passed ? 'PASS' : 'FAIL',
    missionId,
    resultName,
    runnerPasses,
    runnerNames,
    runnerReview,
    repoStatus,
    repoPath,
    completionStatus: completionBody.completion?.status,
    independentReview: repoBody.repo?.independent_review?.verdict,
    repoTests: repoBody.repo?.verification?.status,
    providerCalls: completionBody.completion?.authority?.provider_calls,
    networkAttempts: completionBody.completion?.authority?.network_attempts,
    consoleErrors,
    pageErrors,
    screenshot,
  }, null, 2));
  if (!passed) process.exitCode = 1;
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
